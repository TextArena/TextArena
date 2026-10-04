import re
from typing import Any, Dict, Optional, Tuple, List, Union
import textarena as ta
from textarena.envs.Diplomacy.game_engine import DiplomacyGameEngine
from textarena.envs.Diplomacy.prompts.prompt import get_state_specific_prompt
import os

# A bare command section runs until the next line that starts a new command,
# or the end of the action string.
_BARE_NEXT_CMD = (
    r"(?=\n[ \t]*(?:Broadcast[ \t]*:|Whisper[ \t]+(?:to[ \t]+)?(?:Player[ \t]+)?\d+"
    r"|Submit[ \t]+Orders)|\Z)"
)


class DiplomacyEnv(ta.GameEnv):
    """Environment for Diplomacy with negotiation support"""

    min_players = 3
    max_players = 7

    # Legacy bracketed forms - still accepted as input, but no longer taught in prompts
    broadcast_pattern = re.compile(
        r"(?:"
        r"\s*\[Broadcast\s*:\s*(.*?)\]"            # [Broadcast: message]
        r"|"
        r"\s*\[Broadcast((?:\s+).*?)\]"            # [Broadcast message]
        r"|"
        r"\s*\[Broadcast\](\s+.*?)(?=\s*\[|$)"     # [Broadcast] message
        r")",
        re.IGNORECASE | re.DOTALL
    )
    
    # Whisper to another player (legacy bracketed form)
    whisper_pattern = re.compile(
        r"\s*\[Whisper\s+(?:to\s+)?(?:Player\s+)?(\d+)(?:\s+\(([A-Z]+)\))?\s*:\s*(.*?)\]",
        re.IGNORECASE | re.DOTALL
    )
    
    # Submit orders for the current phase (legacy bracketed form)
    submit_orders_pattern = re.compile(
        r"\[Submit\s+Orders\]([\s\S]*?)(?=\[|$)",
        re.IGNORECASE
    )

    # Canonical bare, line-oriented grammar. Each command starts at the
    # beginning of a line; several commands can be stacked in one action.
    #   Broadcast: message
    bare_broadcast_pattern = re.compile(
        r"^[ \t]*Broadcast[ \t]*:[ \t]*([\s\S]*?)" + _BARE_NEXT_CMD,
        re.IGNORECASE | re.MULTILINE
    )
    #   Whisper to 2: message      /      Whisper to 3 (ITALY): message
    bare_whisper_pattern = re.compile(
        r"^[ \t]*Whisper[ \t]+(?:to[ \t]+)?(?:Player[ \t]+)?(\d+)[ \t]*(?:\(([A-Z]+)\))?[ \t]*:[ \t]*([\s\S]*?)"
        + _BARE_NEXT_CMD,
        re.IGNORECASE | re.MULTILINE
    )
    #   Submit Orders:   followed by one order per line
    bare_submit_orders_pattern = re.compile(
        r"^[ \t]*Submit[ \t]+Orders[ \t]*:?[ \t]*\n?([\s\S]*?)" + _BARE_NEXT_CMD,
        re.IGNORECASE | re.MULTILINE
    )

    def __init__(self, max_turns: int = 30, 
                negotiations_per_phase: int = 3):
        """
        Initialize the Diplomacy game environment

        Args:
            max_turns (int): Maximum number of game years before ending in a draw
            negotiations_per_phase (int): How many negotiation rounds per game phase
        """
        if max_turns < 1:
            raise ValueError("max_turns must be at least one game year")
        if negotiations_per_phase < 1:
            raise ValueError("negotiations_per_phase must be at least one")
        # NOTE: `max_turns` counts game YEARS and is enforced by DiplomacyGameEngine;
        # it is NOT an engine-step limit, so it must not be stored as self.max_turns.
        self.max_game_years = max_turns
        self.negotiations_per_phase = negotiations_per_phase
        
        # Game state
        self.engine = None
        self.player_power_map = {}
        self.power_player_map = {}
        self.current_negotiation_round = 0
        self.orders_submitted = set()  # Track which players submitted orders
        self.pending_orders = {}       # Store orders until processing
        self.current_season = None
        self.current_year = None
        self.current_phase = None
        self.chat_history: List[Dict[str, Any]] = []

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # The raw action is echoed to its author (with chat_history bookkeeping) in apply().
        return None

    def setup(self) -> Dict[str, Any]:
        """ Set up a new game """
        num_players = self.state.num_players

        # Initialize game engine
        self.engine = DiplomacyGameEngine(max_turns=self.max_game_years)
        self.player_power_map = self.engine.setup_game(num_players, rng=self.rng)
        self.power_player_map = {power: player for player, power in self.player_power_map.items()}
        
        # Reset game state tracking
        self.current_negotiation_round = 0
        self.orders_submitted = set()
        self.pending_orders = {}
        self.current_season = self.engine.season
        self.current_year = self.engine.year
        self.current_phase = self.engine.phase
        self.offers = {}
        self.next_offer_id = 1
        self.agreements = {}
        self.chat_history: List[Dict[str, Any]] = []

        return self._build_game_state()

    def _build_game_state(
        self, engine_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Return the stable public state schema used at setup and resolution."""
        game_state = dict(engine_state or self.engine.get_state())
        game_state["player_power_map"] = dict(self.player_power_map)
        game_state["powers_info"] = {
            power: {
                "home_centers": list(self.engine.powers[power].home_centers),
                "controlled_centers": list(
                    self.engine.powers[power].controlled_centers
                ),
                "units": [str(unit) for unit in self.engine.powers[power].units],
            }
            for power in self.player_power_map.values()
        }
        game_state["current_negotiation_round"] = self.current_negotiation_round
        game_state["total_negotiation_rounds"] = self.negotiations_per_phase
        return game_state

    def roles(self) -> Dict[int, str]:
        return dict(self.player_power_map)

    def prompt(self, player_id: int) -> str:
        return self._generate_player_prompt(player_power_map=self.player_power_map, player_id=player_id, game_state=self.game_state, start_of_game=True)

    def on_start(self):
        # Send initial game state announcement to all players
        self._announce_game_state()

    def _generate_player_prompt(self, player_power_map: Dict[str, str], player_id: int, game_state: Dict[str, Any], start_of_game: bool = False) -> str:
        """
        Generate a comprehensive prompt for the player at the beginning of the game
        
        Args:
            player_id (int): ID of the player
            game_state (Dict): Current game state
                
        Returns:
            str: Prompt for the player
        """
        power_name = player_power_map.get(player_id)
        if not power_name:
            return "You are not an active player in this game."
            
        power_state = game_state['powers_info'].get(power_name, {})
        
        # Build the comprehensive prompt
        prompt = [
            f"# DIPLOMACY GAME - YOU ARE {power_name} (PLAYER {player_id})",
            "",
            "## GAME OVERVIEW",
            "Diplomacy is a strategic board game of negotiation, alliance-building, and tactical warfare set in pre-WWI Europe.",
            "The game revolves around diplomatic relations, military maneuvers, and territorial control.",
            "",
            "### GAME STRUCTURE",
            "- Each game year consists of Spring and Fall seasons, plus a Winter adjustment phase",
            "- Each season has a Movement phase and possibly a Retreat phase",
            "- After Fall, there's an Adjustment phase where you build new units or disband excess units",
            "- The game lasts until one power controls 18+ supply centers or until the maximum number of turns",
            f"- This game will last at most {self.max_game_years} years",
            "",
            "### YOUR OBJECTIVE",
            "To win, you must control the majority of supply centers (currently 18 out of 34). This requires:",
            "1. Forming strategic alliances with other powers",
            "2. Coordinating attacks against common enemies",
            "3. Eventually outmaneuvering your allies to claim victory",
        ]
        
        prompt.extend([
            "",
            "## GAME MECHANICS",
            "",
            "### UNITS",
            "- Armies (A): Move on land, can be convoyed across water by fleets",
            "- Fleets (F): Move on water and coastal provinces, can convoy armies",
            "",
            "### ORDERS",
            "During Movement phases, you can issue these orders:",
            "- Hold: A unit from your power stays in place (e.g., 'A PAR H')",
            "- Move: A unit from your power moves to an adjacent territory (e.g., 'A PAR - BUR')",
            "- Support: A unit from your power supports another unit's position or move (e.g., 'A PAR S A MAR' or 'A PAR S A MAR - BUR')",
            "- Convoy: A fleet transports an army across water (e.g., 'F NTH C A LON - BEL')",
            "",
            "During Retreat phases, you can:",
            "- Retreat: Move a dislodged unit to an empty adjacent territory (e.g., 'A PAR R BUR')",
            "- Disband: Remove a dislodged unit from play (e.g., 'A PAR D')",
            "",
            "During Adjustment phases, depending on your center count vs. unit count (Build count = center count - unit count):",
            "- Build: Create new units in your unoccupied home centers (e.g., 'A PAR B')",
            "- Disband: Remove existing units if you have too many (e.g., 'A PAR D')",
            "- Waive: Choose not to build an allowed unit (e.g., 'WAIVE')",
            "",
            "### COMBAT RESOLUTION",
            "- All units have equal strength (1)",
            "- Support adds +1 strength per supporting unit",
            "- The unit with highest strength wins; equal strength units bounce (no movement)",
            "- A unit supporting a move is cut if attacked (unless the attack comes from the unit being supported)",
            "- A dislodged unit must retreat or be disbanded",
            "",
            f"## NEGOTIATION PROCESS ({self.negotiations_per_phase} ROUNDS PER PHASE)",
            f"Each game phase has {self.negotiations_per_phase} negotiation rounds before orders are submitted.",
            "Use these rounds to coordinate with other players through messages and form agreements.",
            "In the final negotiation round, you must submit your orders.",
            "",
            "## COMMUNICATION OPTIONS",
            "You can interact in the following ways:",
            "",
            "Each command must start at the beginning of its own line.",
            "",
            "1. **Broadcast messages** - Send a message to all players",
            "   Example: Broadcast: I propose we all focus on containing Russia this turn",
            "",
            "2. **Whisper messages** - Send a private message to another player",
            "   Example: Whisper to 2: Would you be interested in coordinating against Germany?",
            "   Alternative: Whisper to 3 (ITALY): I can support your move to Trieste",
            "",
            "3. **Submit orders** (final negotiation round only) - Send your orders for the current phase,",
            "   one order per line after the 'Submit Orders:' line",
            "   Example:",
            "   ```",
            "   Submit Orders:",
            "   A PAR - BUR",
            "   A MAR S A PAR - BUR",
            "   F BRE - MAO",
            "   ```",
            "",
            "You can combine multiple communication types in a single response, each on its own line/section:",
            "",
            "```",
            "Broadcast: I'm looking to form alliances this turn",
            "Whisper to 1: I noticed England is threatening your northern border. I could help you against them if you agree not to attack me.",
            "Whisper to 3: Let's coordinate our fleets in the Mediterranean",
            "```",
            "",
            "## STRATEGY TIPS",
            "1. Diplomacy is primarily a game of negotiation - communicate actively",
            "2. Form mutually beneficial alliances, but be prepared to break them when necessary",
            "3. Try to coordinate attacks with allies to ensure successful movements",
            "4. Defend your supply centers while looking for opportunities to capture others",
            "5. Balance short-term tactical gains with long-term strategic positioning",
            "",
            "### STATE SPECIFIC INSTRUCTIONS",
            f"{get_state_specific_prompt(power_name)}",
            "",
        ])
        
        if start_of_game:
            prompt.extend([
                "## CURRENT GAME STATE",
                f"It is {game_state['season']} {game_state['year']}, {game_state['phase']} phase.",
                f"This is negotiation round 1 of {game_state['total_negotiation_rounds']}.",
                "",
                "The game has just begun. Use this first negotiation round to establish initial diplomacy.",
                "",
                "Good luck, and may your diplomacy be successful!"
            ])
        
        return "\n".join(prompt)

    def format_power_units_and_centers(self, player_id: int):
        """
        Show a detailed view of a given power's units and supply centers.
        Includes location expansions and strength summary.
        
        Args:
            player_id (int): The player ID to format information for, -1 mean neutral
            
        Returns:
            str: Formatted string with units and centers information
        """
        if player_id == -1:
            # NEUTRAL POWER
            all_controlled_centers = set()
            for power in self.engine.powers.values():
                all_controlled_centers.update(power.controlled_centers)
            neutral_centers = []
            for center in self.engine.map.get_supply_centers():
                if center not in all_controlled_centers:
                    neutral_centers.append(center)
            return f"{len(neutral_centers)} SUPPLY CENTERS: " + ", ".join(neutral_centers)
        else:
            power_name = self.player_power_map[player_id]
            power = self.engine.powers[power_name]
            
            # Start building the output
            output = []
            power_str = f"{power_name} FORCES"
            # Format units with more detail
            if power.units:
                units_str = f"{len(power.units)} UNITS: "
                unit_details = []
                for unit in power.units:
                    # Assuming unit string format like "A PAR" or "F BRE"
                    unit_str = str(unit)
                    unit_type = unit_str[0]  # 'A' or 'F'
                    location = unit_str[2:]  # Location code
                    # You could add location expansion here if you have a mapping
                    unit_details.append(f"{unit_type} {location}")
                units_str += "(" + ", ".join(unit_details) + ")"
            else:
                units_str = "0 units"
            
            # Format supply centers with more detail
            if power.controlled_centers:
                centers_str = f"{len(power.controlled_centers)} SUPPLY CENTERS: "
                # You could add location expansion here if you have a mapping
                centers_str += "(" + ", ".join(power.controlled_centers) + ")"
            else:
                centers_str = "0 supply centers"
            
            # Add strength summary
            strength_summary = f"Current strength: {len(power.controlled_centers)} centers, {len(power.units)} units"
            
            # Combine all parts
            return f"{power_str}\n{units_str}\n{centers_str}\n{strength_summary}\n\n"
    
    def format_possible_orders(self, possible_orders):
        """
        Format possible orders by categorizing them into strategic groups
        with helpful descriptions.
        
        Args:
            possible_orders (dict): Dictionary of possible orders by location
            
        Returns:
            str: Formatted string of possible orders
        """
        # Categorize orders by strategic purpose
        strategic_orders = {
            "OFFENSIVE": [],  # Orders that can capture centers or threaten enemy units
            "DEFENSIVE": [],  # Orders that protect your centers or units
            "TACTICAL": [],   # Orders that improve position without immediate captures
            "SUPPORT": []     # Support orders
        }

        # Get supply centers for context
        supply_centers = set(self.engine.map.get_supply_centers())
        
        # Get current supply center ownership
        power_centers = {}
        for power_name, power in self.engine.powers.items():
            for center in power.controlled_centers:
                power_centers[center] = power_name
        
        # Process each order
        for loc, orders in possible_orders.items():
            for order in orders:
                order_type = None
                
                # Determine order type based on order syntax
                if " H" in order:
                    order_type = "DEFENSIVE"
                elif " S " in order:
                    order_type = "SUPPORT"
                elif " - " in order:
                    # Get destination
                    dest = order.split(" - ")[1].split(" VIA")[0] if " VIA" in order else order.split(" - ")[1]
                    
                    # Check if destination is a supply center
                    if dest in supply_centers:
                        # If center is neutral or enemy-owned, it's offensive
                        if dest not in power_centers or power_centers[dest] != self.player_power_map[self.state.current_player_id]:
                            order_type = "OFFENSIVE"
                        else:
                            order_type = "DEFENSIVE"  # Moving to own supply center
                    else:
                        order_type = "TACTICAL"  # Non-center destination
                elif " C " in order:
                    order_type = "SUPPORT"  # Classify convoy as support
                else:
                    order_type = "TACTICAL"  # Default for other orders
                
                # Add to appropriate category
                if order_type:
                    strategic_orders[order_type].append(order)
        
        # Generate formatted output
        output = "POSSIBLE ORDERS:\n\n"
        
        # Add offensive moves first - these are highest priority
        if strategic_orders["OFFENSIVE"]:
            output += "Offensive Moves (capture territory):\n"
            for order in strategic_orders["OFFENSIVE"]:
                output += f"  {order}\n"
            output += "\n"
        
        # Add defensive moves
        if strategic_orders["DEFENSIVE"]:
            output += "Defensive Moves (protect territory):\n"
            for order in strategic_orders["DEFENSIVE"]:
                output += f"  {order}\n"
            output += "\n"
        
        # Add tactical positioning moves
        if strategic_orders["TACTICAL"]:
            output += "Tactical Moves (improve position):\n"
            for order in strategic_orders["TACTICAL"]:
                output += f"  {order}\n"
            output += "\n"
        
        # Add support moves
        if strategic_orders["SUPPORT"]:
            output += "Support Options (strengthen attacks/defense):\n"
            for order in strategic_orders["SUPPORT"]:
                output += f"  {order}\n"
        
        return output

    def get_prompt(self, player_id: int, history_text: str):
        # 1) Load the template
        template_path = os.path.join(
            os.path.dirname(__file__), "prompts", "context_prompt.txt"
        )
        with open(template_path, "r") as prompt_file:
            template = prompt_file.read()

        # 2) Expand the phase info
        phase_info = self.expand_phase_info()

        # 3) Get the game state
        game_state = self._build_game_state()

        # 4) Get the state summaries
        game_state['our_state_summary_text'] = self.format_power_units_and_centers(player_id)
        
        # 5) Summaries for enemies
        enemies_forces_summary = ""
        for pwr_id, pwr in self.player_power_map.items():
            if pwr_id != player_id:
                enemies_forces_summary += self.format_power_units_and_centers(pwr_id)
        game_state['other_state_summary_text'] = enemies_forces_summary

        # 6) Neutral state summary
        neutral_supply_centers_summary = self.format_power_units_and_centers(-1)
        game_state['neutral_state_summary_text'] = neutral_supply_centers_summary

        # 6) Possible orders
        possible_orders = self.engine.get_possible_orders(self.player_power_map[player_id])
        possible_orders_text = self.format_possible_orders(possible_orders)
        game_state['possible_orders_text'] = possible_orders_text

        # 7) Prompt
        prompt = template.format(
            phase_info=phase_info,
            history_text=history_text,
            our_state_summary_text=game_state['our_state_summary_text'],
            other_state_summary_text=game_state['other_state_summary_text'],
            neutral_state_summary_text=game_state['neutral_state_summary_text'],
            possible_orders_text=game_state['possible_orders_text'],
        )

        game_settings_prompt = self._generate_player_prompt(player_power_map=self.player_power_map, player_id=player_id, game_state=game_state, start_of_game=False)

        return game_settings_prompt + "\n\n" + prompt

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """
        Process a player's action (a multi-line string of communications and orders).
        """
        power_name = self.player_power_map.get(player_id)

        if not power_name:
            # Failsafe - every player is mapped to a power
            self.message(player_id, "You are not an active player in this game.", ta.ObservationType.GAME_ADMIN)
            return None

        communication_error = self._validate_communications(player_id, action)
        if communication_error:
            return self.invalid(communication_error)

        # In the final round, validate the complete order section before
        # emitting any part of the action. Invalid actions must be atomic.
        if (
            self.current_negotiation_round == self.negotiations_per_phase - 1
            and player_id not in self.orders_submitted
        ):
            _, validation_error = self._validate_orders_submission(
                power_name, action
            )
            if validation_error:
                return self.invalid(validation_error)

        # Always add the player's full action as an observation to themselves
        self.add_observation(from_id=player_id, to_id=player_id, message=action)

        # Process communications and orders
        actions, game_state_changed = self._process_player_action(player_id, power_name, action)

        # In the final negotiation round every (still alive) player must submit orders
        if (not game_state_changed and self.current_negotiation_round == self.negotiations_per_phase - 1
                and player_id not in self.orders_submitted):
            return self.invalid("You must submit orders in the final negotiation round using the 'Submit Orders:' format (one order per line).")

        if game_state_changed: # Meaning all players have submitted orders
            # Check if game is over
            if self.engine.game_over:
                return self._game_over_outcome()

        # Add detailed game state info
        self.step_info.update({
            'current_player': player_id,
            'current_power': power_name,
            'actions': actions
        })

        # Default round-robin rotation moves to the next alive player; if the
        # rotation wraps around, a full round of negotiations has completed.
        if not game_state_changed:
            next_pid = self.state.next_alive_player()
            if next_pid is not None and next_pid <= player_id:
                self._advance_negotiation_round()
        return None

    def _validate_communications(
        self, player_id: int, action: str
    ) -> Optional[str]:
        """Validate directed messages before emitting any part of an action."""
        for pattern in (self.bare_whisper_pattern, self.whisper_pattern):
            for match in pattern.finditer(action):
                target_id = int(match.group(1))
                target_power = match.group(2)
                message = (match.group(3) or "").strip()
                if target_id not in self.player_power_map:
                    return f"Unknown whisper target: Player {target_id}."
                if target_id == player_id:
                    return "You cannot whisper to yourself."
                if not self.state.is_player_alive(target_id):
                    return f"Player {target_id} is no longer active."
                if (
                    target_power
                    and self.player_power_map[target_id] != target_power.upper()
                ):
                    return (
                        f"Player {target_id} is not {target_power.upper()}."
                    )
                if not message:
                    return "Whisper messages cannot be empty."
        return None

    def _required_order_players(self) -> set:
        """Players still participating in the current engine phase."""
        return {
            pid
            for pid, power_name in self.player_power_map.items()
            if (
                self.state.is_player_alive(pid)
                and not self.engine.powers[power_name].is_defeated
            )
        }

    def _all_required_orders_submitted(self) -> bool:
        return self._required_order_players() <= self.orders_submitted

    def _extract_order_sections(self, action: str) -> List[str]:
        """Extract canonical or legacy order sections without side effects."""
        sections: List[str] = []
        for pattern in (self.bare_submit_orders_pattern, self.submit_orders_pattern):
            sections.extend(match.group(1) or "" for match in pattern.finditer(action))
        return sections

    @staticmethod
    def _parse_order_lines(orders_text: str) -> List[str]:
        return [
            line.strip()
            for line in orders_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _validate_orders_submission(
        self, power_name: str, action: str
    ) -> Tuple[List[str], Optional[str]]:
        sections = self._extract_order_sections(action)
        if not sections:
            return [], (
                "You must submit orders in the final negotiation round using "
                "the 'Submit Orders:' format (one order per line)."
            )
        if len(sections) != 1:
            return [], "Submit exactly one order section per action."

        orders = self._parse_order_lines(sections[0])
        _, invalid_orders = self.engine.parse_orders(power_name, orders)
        if invalid_orders:
            first_error = invalid_orders[0]["reason"]
            return [], f"Invalid order submission: {first_error}"
        return orders, None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """A player who repeatedly fails to submit orders in the final round is eliminated."""
        power_name = self.player_power_map[player_id]
        self.eliminate(player_id)
        self.engine.powers[power_name].is_defeated = True
        self.add_observation(from_id=ta.GAME_ID, to_id=-1, message=f"Player {player_id} ({power_name}) has been eliminated after repeated invalid moves.")
        # Treat the eliminated power as having submitted no orders so the phase can still resolve
        self.pending_orders.setdefault(power_name, [])
        self.orders_submitted.add(player_id)
        alive = [pid for pid in self.player_power_map if self.state.is_player_alive(pid)]
        if len(alive) <= 1:
            return self.winner(alive, reason="All other players were eliminated by repeated invalid moves.")
        if self._all_required_orders_submitted():
            self._process_orders()
            if self.engine.game_over:
                return self._game_over_outcome()
        # The engine hands the turn to the next alive player
        return None

    def _game_over_outcome(self) -> ta.Outcome:
        """Build the final Outcome and announce the game result to all players."""
        outcome = self._announce_game_result()
        self.step_info.update({
            'reason': "Game Over",
            'detailed_reason': (
                f"Game ended after {self.engine.completed_game_years} game years. "
                f"The winners are {self.engine.winners}."
            ),
            'winners': self.engine.winners,
            'winning_players': [self.power_player_map[power] for power in self.engine.winners] if self.engine.winners else [],
            'final_sc_count': {power: len(self.engine.powers[power].controlled_centers) for power in self.engine.powers},
            'turn_number': self.engine.turn_number,
            'completed_game_years': self.engine.completed_game_years,
        })
        return outcome

    def _process_player_action(self, player_id: int, power_name: str, action: str) -> Tuple[Dict, bool]:
        """
        Process a player's action string, extracting communications and orders
        
        Args:
            player_id (int): The player ID
            power_name (str): The power name
            action (str): The action string
            
        Returns:
            Tuple[Dict, bool]: Summary of actions taken and whether game state changed
        """
        game_state_changed = False
        action_summary = {
            "broadcasts": [],
            "whispers": [],
            "orders_submitted": False,
            "orders": []
        }
        
        # Process broadcasts (bare line-oriented form + legacy bracketed form)
        for pattern in (self.bare_broadcast_pattern, self.broadcast_pattern):
            for match in pattern.finditer(action):
                message = next((g for g in match.groups() if g and g.strip()), None)
                if message:
                    message = message.strip()
                    # broadcast to all
                    self.add_observation(from_id=player_id, to_id=-1, message=message)
                    action_summary["broadcasts"].append(message)

        # Process whispers (bare line-oriented form + legacy bracketed form)
        for pattern in (self.bare_whisper_pattern, self.whisper_pattern):
            for match in pattern.finditer(action):
                target_id = int(match.group(1))
                target_power = match.group(2)
                message = (match.group(3) or "").strip()

                # Validate target_power if provided
                if (
                    target_power
                    and self.player_power_map.get(target_id)
                    != target_power.upper()
                ):
                    continue

                # add observation to the whisperee
                self.add_observation(from_id=player_id, to_id=target_id, message=message)
                action_summary["whispers"].append({
                    "to_player": target_id,
                    "to_power": self.player_power_map.get(target_id),
                    "message": message
                })

        # Process order submission (bare line-oriented form + legacy bracketed form)
        if self.current_negotiation_round == self.negotiations_per_phase - 1:
            sections = self._extract_order_sections(action)
            if len(sections) == 1:
                orders_text = sections[0].strip()
                if self._handle_orders_submission(
                    player_id, power_name, orders_text
                ):
                    action_summary["orders_submitted"] = True
                    action_summary["orders"].append(orders_text)

            # Check if all players have submitted orders and it's time to process them
            if self._all_required_orders_submitted():
                game_state_changed = self._process_orders()

        return action_summary, game_state_changed


    def _handle_orders_submission(
        self, player_id: int, power_name: str, orders_text: str
    ) -> bool:
        """Handle order submission from a player"""
        orders = self._parse_order_lines(orders_text)
        _, invalid_orders = self.engine.parse_orders(power_name, orders)
        if invalid_orders:
            return False
    
        # Store pending orders and mark player as submitted
        self.pending_orders[power_name] = orders
        self.orders_submitted.add(player_id)
        
        # Notify player their orders were received
        msg = f"Orders received for {power_name} ({len(orders)} orders)"
        self.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=msg)
        return True

    def _process_orders(self) -> bool:
        """Process all submitted orders"""
        # Submit orders to the engine
        phase_changed, new_state = self.engine.resolve_orders(self.pending_orders)
        self._sync_defeated_players()
        
        # Update game state
        self.state.game_state = self._build_game_state(new_state)
        
        # Update phase tracking
        self.current_season = self.engine.season
        self.current_year = self.engine.year
        self.current_phase = self.engine.phase
        
        # Announce results to all players
        self._announce_order_results()
        
        # Reset for next phase
        self.orders_submitted = set()
        self.pending_orders = {}
        self.current_negotiation_round = 0
        
        # Update game state
        self.state.game_state['current_negotiation_round'] = 0
        
        return True

    def _sync_defeated_players(self) -> None:
        """Remove engine-defeated powers from future environment rotations."""
        for player_id, power_name in self.player_power_map.items():
            if (
                self.engine.powers[power_name].is_defeated
                and self.state.is_player_alive(player_id)
            ):
                self.eliminate(player_id)
                self.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=(
                        f"Player {player_id} ({power_name}) has been "
                        "eliminated from the game."
                    ),
                    observation_type=ta.ObservationType.GAME_ADMIN,
                )

    def _advance_negotiation_round(self):
        """Advance to the next negotiation round"""
        self.current_negotiation_round += 1
        self.state.game_state['current_negotiation_round'] = self.current_negotiation_round
        
        # Notify all players about the new negotiation round
        if self.current_negotiation_round < self.negotiations_per_phase:
            message=(f"Negotiation Round {self.current_negotiation_round + 1} of "
                       f"{self.negotiations_per_phase} begins")
            self.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message)
                
            # If this is the final round, notify players to submit orders
            if self.current_negotiation_round == self.negotiations_per_phase - 1:
                message="Final negotiation round: please submit your orders"
                self.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message)
        else:
            # Force order processing if we've somehow exceeded max rounds
            if self.pending_orders:
                self._process_orders()


    def _announce_game_state(self):
        """Announce the current game state to all players"""
        phase_type = self.engine.phase.value
        season = self.engine.season.value
        year = self.engine.year
        
        # Create announcement message
        announcement = (
            f"===== {season} {year} {phase_type} Phase Begins =====\n"
            f"Current supply center counts:\n"
        )
        
        # Add supply center counts for each power
        for power_name, player_id in self.power_player_map.items():
            centers = len(self.engine.powers[power_name].controlled_centers)
            units = len(self.engine.powers[power_name].units)
            announcement += f"- Player {player_id} ({power_name}): {centers} centers, {units} units\n"
        
        # Send to all players
        for player_id in self.player_power_map.keys():
            self.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=announcement)

    def _announce_order_results(self):
        """Announce order results to all players"""
        # Create basic announcement
        base_announcement = (
            f"===== Order Results: {self.current_season.value} {self.current_year} =====\n"
        )
        
        # Create individualized announcements with detailed results
        for player_id, power_name in self.player_power_map.items():
            power_announcement = base_announcement
            
            # Add own orders and results
            if power_name in self.pending_orders:
                power_announcement += f"\nYour orders ({power_name}):\n"
                for order in self.pending_orders[power_name]:
                    power_announcement += f"- {order}\n"
            
            # Add public information about other powers' orders
            power_announcement += "\nOther powers' orders:\n"
            for other_power, orders in self.pending_orders.items():
                if other_power != power_name:
                    power_announcement += f"\n{other_power}:\n"
                    for order in orders:
                        power_announcement += f"- {order}\n"
            
            # Send to player
            self.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=power_announcement)
        
        # Announce new phase
        self._announce_game_state()

    def _announce_game_result(self) -> ta.Outcome:
        """Announce the game result to all players and return the final Outcome"""
        if self.engine.winners:
            # Victory announcement
            winners_text = ", ".join(self.engine.winners)
            winning_players = [self.power_player_map[power] for power in self.engine.winners]
            winning_players_text = ", ".join(f"Player {pid}" for pid in winning_players)
            
            reason = (
                f"Victory achieved by: {winners_text} ({winning_players_text})\n\n"
                f"Final supply center counts:\n"
            )
        else:
            # Draw announcement
            reason = (
                f"Game ended in a DRAW after "
                f"{self.engine.completed_game_years} game years.\n\n"
                f"Final supply center counts:\n"
            )

        # Include final counts in both the terminal Outcome and announcement.
        for power_name, player_id in self.power_player_map.items():
            if power_name in self.engine.powers:
                centers = len(self.engine.powers[power_name].controlled_centers)
                reason += (
                    f"- Player {player_id} ({power_name}): "
                    f"{centers} centers\n"
                )

        if self.engine.winners:
            outcome = self.winner(winning_players, reason=reason)
        else:
            outcome = self.draw(reason=reason)
        
        announcement = "Game Results:\n" + reason
        # Add game history summary
        announcement += "\nGame Summary:\n"
        for entry in self.engine.order_history:
            announcement += f"- {entry['season']} {entry['year']} {entry['phase']}\n"

        # Send to all players
        for player_id in self.player_power_map.keys():
            self.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=announcement)

        return outcome

    def add_observation(self, from_id: int, to_id: int, message: str, observation_type: Optional[ta.ObservationType] = None):
        """Add an observation to the chat history"""
        if observation_type is None:
            observation_type = ta.ObservationType.GAME_MESSAGE if from_id == ta.GAME_ID else ta.ObservationType.PLAYER_ACTION
        self.chat_history.append({
            "turn": self.state.turn,
            "from": from_id,
            "from_power": self.player_power_map.get(from_id),
            "to": to_id,
            "to_power": self.player_power_map.get(to_id),
            "message": message
        })
        self.state.add_event(from_id=from_id, message=message, observation_type=observation_type, to_id=to_id)

    def get_game_state(self):
        game_state = {
            # ===== Game State =====
            "current_season": self.current_season.value,
            "current_year": self.current_year,
            "current_phase": self.current_phase.value,
            "current_negotiation_round": self.current_negotiation_round,
            "total_negotiation_rounds": self.negotiations_per_phase,
            # ===== Players =====
            "Players": [
                {
                    "id": player_id,
                    "power": self.player_power_map[player_id],
                    "controlled_centers": len(self.engine.powers[self.player_power_map[player_id]].controlled_centers),
                    "units": len(self.engine.powers[self.player_power_map[player_id]].units)
                }
                for player_id in self.player_power_map.keys()
            ],
            # ===== Orders =====
            "orders_submitted": list(self.orders_submitted),
            "pending_orders_count": {power: len(orders) for power, orders in self.pending_orders.items()},
            "sc_counts": {power: len(self.engine.powers[power].controlled_centers) for power in self.engine.powers},
            "unit_counts": {power: len(self.engine.powers[power].units) for power in self.engine.powers},
            "is_final_round": self.current_negotiation_round == self.negotiations_per_phase - 1,
        }
        
        return game_state

    def get_conversation_history(self) -> List[List[Dict[str, Any]]]:
        """Log the current conversation history as a list indexed by turn"""
        # Create a list-based conversation history organized by turn
        max_turn = 0
        turn_messages = {}
        
        # Use the dedicated chat_history attribute
        for entry in self.chat_history:
            turn = entry["turn"]
            
            # Process the message to clean up whispers
            message = entry["message"]
            if "[Whisper to" in message:
                # Remove the whisper prefix for cleaner history
                message = re.sub(r"\[Whisper to \d+(?:\s+\([A-Z]+\))?: ", "", message)
                entry["message"] = message
            
            # Organize by turn
            if turn not in turn_messages:
                turn_messages[turn] = []
            
            # Add a cleaned version to the turn messages
            clean_entry = {
                "from": entry["from_power"] if entry["from_power"] else ("GAME" if entry["from"] == ta.GAME_ID else f"Player {entry['from']}"),
                "to": entry["to_power"] if entry["to"] != -1 and entry["to_power"] else ("ALL" if entry["to"] == -1 else f"Player {entry['to']}"),
                "message": message,
                "turn": turn
            }
            turn_messages[turn].append(clean_entry)
            
            max_turn = max(max_turn, turn)
        
        # Convert dict to list with proper indexing
        conversation_history = [[] for _ in range(max_turn + 1)]
        for turn, messages in turn_messages.items():
            conversation_history[turn] = messages
        
        return conversation_history
    
    def get_order_history(self) -> Dict[str, Any]:
        """Get the current order history"""
        return self.engine.order_history
    
    def get_game_state_history(self) -> List[Dict[str, Any]]:
        """Get the game state history"""
        return self.engine.game_state_history
    
    def expand_phase_info(self):
        """
        Convert a phase like 'S1901M' into a more descriptive string:
        'Spring 1901 Movement (early game): Units can move, support, or convoy...'
        This function also references the current year to classify early/mid/late game.
        """
        season = self.engine.season.value
        year = self.engine.year
        phase = self.engine.phase.value
        # Basic mapping of abbreviations
        
        # Approximate game stage
        if year <= 1902:
            stage = "early game"
        elif year <= 1906:
            stage = "mid game"
        else:
            stage = "late game"
        
        # Phase-specific action text
        if phase == 'Movement':
            actions = "Players issue move, support, or convoy orders."
        elif phase == 'Retreats':
            actions = "Dislodged units must retreat or disband."
        elif phase == 'Adjustments':
            actions = "Powers may build new units if they have more centers than units, otherwise disband if fewer."
        else:
            actions = "Unknown phase actions."
        
        return f"{season} {year} {phase} ({stage}): {actions}"

    def generate_phase_summary(self, phase_history):
        # Generate a summary of game state changes, TODO finish this part
        game_state_history = self.get_game_state_history()
        game_state_changes = ""
        if len(game_state_history) >= 2:
            current_state = game_state_history[-1]
            previous_state = game_state_history[-2]
            
            # Compare supply center counts
            sc_changes = []
            for power in current_state["sc_counts"]:
                current_sc = current_state["sc_counts"][power]
                previous_sc = previous_state["sc_counts"].get(power, 0)
                if current_sc != previous_sc:
                    change = current_sc - previous_sc
                    sc_changes.append(f"{power}: {'+' if change > 0 else ''}{change} supply centers")
            
            if sc_changes:
                game_state_changes += "Supply Center Changes:\n" + "\n".join(sc_changes) + "\n\n"
            
            # Compare unit counts
            unit_changes = []
            for power in current_state["unit_counts"]:
                current_units = current_state["unit_counts"][power]
                previous_units = previous_state["unit_counts"].get(power, 0)
                if current_units != previous_units:
                    change = current_units - previous_units
                    unit_changes.append(f"{power}: {'+' if change > 0 else ''}{change} units")
            
            if unit_changes:
                game_state_changes += "Unit Count Changes:\n" + "\n".join(unit_changes) + "\n\n"
        
        # Get the phase summary prompt
        with open(os.path.join(os.path.dirname(__file__), "prompts", "phase_summary_prompt.txt"), "r") as f:
            prompt = f.read()
        
        # Format the prompt with the phase history and game state changes
        prompt = prompt.format(phase_history=phase_history, game_state_changes=game_state_changes)
        
        # ... rest of the function remains the same ...