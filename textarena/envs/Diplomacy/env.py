import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Diplomacy.game_engine import (
    DiplomacyGameEngine,
    Order,
    OrderType,
    PhaseType,
    Season,
    UnitType,
)
from textarena.envs.Diplomacy.prompts.power_strategy import POWER_STRATEGY

# A command starts at the beginning of a line and runs until the next line that
# starts a command (or the end of the action).
_COMMAND_START = re.compile(
    r"^[ \t]*(Broadcast|Whisper|Submit[ \t]+Orders?)\b",
    re.IGNORECASE | re.MULTILINE,
)
_BARE_BROADCAST = re.compile(r"\s*Broadcast\s*:(.*)", re.IGNORECASE | re.DOTALL)
#   Whisper to 2: ...   /   Whisper to 3 (ITALY): ...   /   Whisper to FRANCE: ...
_BARE_WHISPER = re.compile(
    r"\s*Whisper\s+(?:to\s+)?(?:Player\s+)?(\w+)\s*(?:\(\s*(\w+)\s*\)\s*)?:(.*)",
    re.IGNORECASE | re.DOTALL,
)
_BARE_SUBMIT = re.compile(r"\s*Submit\s+Orders?\s*:?(.*)", re.IGNORECASE | re.DOTALL)


def _location(province: str, coast: Optional[str]) -> str:
    return f"{province}({coast})" if coast else province


class DiplomacyEnv(ta.GameEnv):
    """Environment for Diplomacy with negotiation support"""

    min_players = 3
    max_players = 7

    max_game_years = ta.Param(30, "The number of complete game years before the game ends in a draw.", min=1)
    negotiations_per_phase = ta.Param(
        3, "The turns each player takes per phase. Orders are due in the last one.", min=1,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Game state
        self.engine = None
        self.player_power_map = {}
        self.power_player_map = {}
        self.current_negotiation_round = 0
        self.orders_submitted = set()  # Track which players submitted orders
        self.pending_orders = {}       # Store orders until processing
        self.chat_history: List[Dict[str, Any]] = []

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        # Only the author sees the raw action; apply() echoes it once the action is accepted.
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
        self.chat_history: List[Dict[str, Any]] = []

        return self._build_game_state()

    def _build_game_state(self) -> Dict[str, Any]:
        """Return the stable public state schema used at setup and resolution."""
        game_state = dict(self.engine.get_state())
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
        power_name = self.player_power_map[player_id]
        rounds = self.negotiations_per_phase
        players = ", ".join(self._power_label(power) for power in self._powers_by_player())
        total_centers = len(self.engine.map.get_supply_centers())
        return "\n".join([
            f"# DIPLOMACY - YOU ARE {power_name} (PLAYER {player_id})",
            "",
            "You command one of the great powers of pre-WWI Europe on the standard Diplomacy map. "
            f"Players: {players}. Powers that are not in play are removed from the board and their home "
            "centers start unowned.",
            "",
            "## HOW THE GAME ENDS",
            f"A power that controls {self._victory_threshold()} of the {total_centers} supply centers wins. "
            "The game also ends when only one power is left, and as a draw after "
            f"{self.max_game_years} complete game year(s).",
            "",
            "## TURN STRUCTURE",
            "- Every game year has five phases, always played in this order: Spring Movement, Spring Retreats, "
            "Fall Movement, Fall Retreats, Winter Adjustments. A phase is played even if nobody has anything to order.",
            f"- Each phase has {rounds} negotiation round(s). In every round each player takes one turn, in order "
            "of player id.",
            f"- Orders are accepted only in the final round (round {rounds}) of a phase, and every player must submit "
            "them then (an empty list is fine). Orders sent in earlier rounds are not recorded; you will be told so.",
            "- Once every power has submitted, all orders resolve at the same time and everyone is shown every order "
            "and its result.",
            "- Supply centers change hands at the end of each Fall, after the Fall Retreats phase: each center then "
            "belongs to the power occupying it. In Winter every power builds or disbands units until its unit count "
            "matches its center count.",
            "- Before each of your turns you receive a board summary: the phase, every unit, supply-center owners, "
            "your legal orders, and what is expected from you now.",
            "",
            "## ORDERS",
            "Units are A (army: land provinces, can be convoyed across sea) and F (fleet: sea and coastal provinces). "
            "Provinces use three-letter codes; the split coasts of SPA, STP and BUL are written like STP(NC), and a "
            "fleet moving to one of those provinces must name the coast.",
            "- Movement: hold 'A PAR H'; move 'A PAR - BUR'; support a hold 'A MAR S A PAR'; support a move "
            "'A MAR S A PAR - BUR'; convoy 'F NTH C A LON - BEL'; move by convoy 'A LON - BEL VIA'. "
            "Units without an order hold.",
            "- Retreats: retreat 'A PAR R BUR' or disband 'A PAR D'. A dislodged unit without an order is disbanded.",
            "- Adjustments: build 'A PAR B' or 'F STP(NC) B' in a vacant home center you own, skip a build with "
            "'WAIVE', disband 'A PAR D'. Unordered builds are waived; if you order too few disbands, the units "
            "farthest from your home centers are disbanded automatically.",
            "",
            "## COMBAT",
            "- Every unit has strength 1 and each valid support adds 1. The strongest move into a province succeeds; "
            "equally strong moves bounce and none of them moves in.",
            "- A support is cut if the supporting unit is attacked from any province other than the one it is "
            "supporting a move into.",
            "- A dislodged unit must retreat to an adjacent empty province that its attacker did not come from and "
            "that was not left empty by a bounce, or disband. Units retreating to the same province are all disbanded.",
            "- You can never dislodge your own unit.",
            "",
            "## HOW TO REPLY",
            "Start each command on its own line. A command runs until the next command line, so messages may span "
            "several lines.",
            "- 'Broadcast: <message>' sends a message to every player.",
            "- 'Whisper to <player id>: <message>' sends a private message that only that player sees. You can name "
            "the power instead ('Whisper to FRANCE: ...'); 'Whisper to 3 (ITALY): ...' is rejected if Player 3 is "
            "not ITALY.",
            "- 'Submit Orders:' followed by one order per line submits your orders (final round only).",
            "Messages you receive are marked '(to all)' for broadcasts and '(privately to you)' for whispers.",
            "A reply with a malformed command or, in the final round, an illegal order is rejected as a whole and "
            "nothing in it is sent. You may correct it, but a second invalid reply in a row eliminates you.",
            "",
            "Example final-round reply:",
            "Broadcast: I will keep my fleets out of the Channel this year.",
            "Whisper to 2: As agreed, I will support you into Belgium next year.",
            "Submit Orders:",
            "A PAR - BUR",
            "A MAR S A PAR - BUR",
            "F BRE - MAO",
            "",
            f"## STRATEGY ADVICE FOR {power_name}",
            POWER_STRATEGY[power_name],
        ])

    def on_start(self):
        self._announce_phase_start()

    # ------------------------------------------------------------- rendering
    def render(self, player_id: int) -> Optional[str]:
        """Board summary sent privately to the player about to act."""
        if self.state.done:
            return None
        power_name = self.player_power_map[player_id]
        sections = [
            self._render_header(player_id),
            self._render_centers(),
            self._render_units(),
            self._render_order_options(power_name),
            self._render_instructions(power_name),
        ]
        return "\n\n".join("\n".join(lines) for lines in sections)

    def _render_header(self, player_id: int) -> List[str]:
        engine = self.engine
        rounds = self.negotiations_per_phase
        round_text = f"negotiation round {self.current_negotiation_round + 1} of {rounds}"
        if self._is_final_round():
            round_text += " (final round: orders due)"
        turn_order = ", ".join(
            self._power_label(power)
            for pid, power in sorted(self.player_power_map.items())
            if self.state.is_player_alive(pid)
        )
        return [
            f"=== {engine.season.value} {engine.year} {engine.phase.value} | game year "
            f"{engine.completed_game_years + 1} of {self.max_game_years} | {round_text} ===",
            f"It is your turn. You are {self._power_label(self.player_power_map[player_id])}.",
            f"Turn order each round: {turn_order}.",
        ]

    def _render_centers(self) -> List[str]:
        lines = [
            f"Supply centers ({self._victory_threshold()} needed to win; they change hands at the end of "
            "each Fall Retreats phase):"
        ]
        owned = set()
        for pid, power_name in sorted(self.player_power_map.items()):
            centers = sorted(self.engine.powers[power_name].controlled_centers)
            owned.update(centers)
            lines.append(
                f"  {self._power_label(power_name)}{self._status(pid)}: {len(centers)} - "
                f"{', '.join(centers) or 'none'}"
            )
        unowned = sorted(set(self.engine.map.get_supply_centers()) - owned)
        lines.append(f"  Unowned: {len(unowned)} - {', '.join(unowned) or 'none'}")
        return lines

    def _render_units(self) -> List[str]:
        lines = ["Units (A = army, F = fleet):"]
        for pid, power_name in sorted(self.player_power_map.items()):
            labels = []
            for unit in self.engine.powers[power_name].units:
                label = self._unit_label(unit)
                if unit.dislodged:
                    label += f" (dislodged, can retreat to: {', '.join(unit.retreat_options) or 'nowhere'})"
                labels.append(label)
            lines.append(
                f"  {self._power_label(power_name)}{self._status(pid)}: {len(labels)} - "
                f"{', '.join(labels) or 'none'}"
            )
        return lines

    def _render_order_options(self, power_name: str) -> List[str]:
        if self.engine.phase == PhaseType.MOVEMENT:
            return self._render_movement_options(power_name)
        if self.engine.phase == PhaseType.RETREATS:
            return self._render_retreat_options(power_name)
        return self._render_adjustment_options(power_name)

    def _render_movement_options(self, power_name: str) -> List[str]:
        power = self.engine.powers[power_name]
        lines = [
            f"Your units ({power_name}) and their legal orders. Every unit may also hold. Supports list the "
            "supported unit with the hold and/or destinations you can support:"
        ]
        if not power.units:
            return lines + ["  You have no units."]
        possible = self.engine.get_possible_orders(power_name)
        for unit in power.units:
            location = unit.region.name
            moves: List[str] = []
            supports: Dict[str, List[str]] = {}
            convoys: Dict[str, List[str]] = {}
            for text in possible.get(location, []):
                order = Order.parse(text, power_name)
                if order.order_type == OrderType.MOVE:
                    moves.append(_location(order.target, order.target_coast))
                elif order.order_type == OrderType.SUPPORT:
                    supports.setdefault(order.target, []).append(
                        "hold" if order.secondary_target is None
                        else _location(order.secondary_target, order.secondary_target_coast)
                    )
                elif order.order_type == OrderType.CONVOY:
                    convoys.setdefault(order.target, []).append(order.secondary_target)
            moves.sort()
            parts = [f"move to {', '.join(moves)}" if moves else "no moves"]
            if unit.type == UnitType.ARMY:
                by_convoy = [
                    destination
                    for destination in self.engine.get_convoy_destinations(location)
                    if destination not in moves
                ]
                if by_convoy:
                    parts.append(f"move by convoy to {', '.join(by_convoy)}")
            if supports:
                parts.append("support " + "; ".join(
                    f"{target} ({', '.join(options)})" for target, options in supports.items()
                ))
            if convoys:
                parts.append("convoy " + "; ".join(
                    f"{target} to {', '.join(destinations)}" for target, destinations in convoys.items()
                ))
            lines.append(f"  {self._unit_label(unit)}: " + " | ".join(parts))
        lines.append(
            "Syntax: 'A PAR H', 'A PAR - BUR', 'A MAR S A PAR' (support hold), 'A MAR S A PAR - BUR' "
            "(support move), 'F NTH C A LON - BEL' (convoy), 'A LON - BEL VIA' (move by convoy)."
        )
        return lines

    def _render_retreat_options(self, power_name: str) -> List[str]:
        dislodged = [unit for unit in self.engine.powers[power_name].units if unit.dislodged]
        if not dislodged:
            return [f"Your units ({power_name}): none are dislodged, so you have nothing to order this phase."]
        lines = [f"Your dislodged units ({power_name}) must retreat or disband:"]
        for unit in dislodged:
            label = self._unit_label(unit)
            if unit.retreat_options:
                lines.append(
                    f"  {label}: retreat to {', '.join(unit.retreat_options)} "
                    f"(e.g. '{label} R {unit.retreat_options[0]}') or disband ('{label} D')"
                )
            else:
                lines.append(f"  {label}: no retreat is possible, it can only disband ('{label} D')")
        lines.append(
            "A dislodged unit without an order is disbanded, and units retreating to the same province "
            "are all disbanded."
        )
        return lines

    def _render_adjustment_options(self, power_name: str) -> List[str]:
        power = self.engine.powers[power_name]
        build_count = power.count_needed_builds()
        status = (
            f"Your adjustment ({power_name}): {len(power.controlled_centers)} supply center(s), "
            f"{len(power.units)} unit(s)."
        )
        if build_count > 0:
            buildable = power.get_buildable_locations(self.engine.map)
            if not buildable:
                return [
                    f"{status} You may build {build_count} unit(s), but none of your home centers is both "
                    "owned and vacant, so you cannot build."
                ]
            possible = self.engine.get_possible_orders(power_name)
            builds = [
                order for location in buildable for order in possible.get(location, []) if order != "WAIVE"
            ]
            return [
                f"{status} You may build {build_count} unit(s), at most one per vacant home center you own:",
                f"  {', '.join(builds)}",
                "Write WAIVE to skip a build; builds you do not order are waived.",
            ]
        if build_count < 0:
            disbands = ", ".join(f"{self._unit_label(unit)} D" for unit in power.units)
            return [
                f"{status} You must disband {-build_count} unit(s):",
                f"  {disbands}",
                "If you order fewer disbands, the units farthest from your home centers are disbanded automatically.",
            ]
        return [f"{status} Nothing to build or disband."]

    def _render_instructions(self, power_name: str) -> List[str]:
        rounds = self.negotiations_per_phase
        if not self._is_final_round():
            return [
                f"NOW: negotiation round {self.current_negotiation_round + 1} of {rounds}. Send messages with "
                "'Broadcast: <message>' (everyone) and/or 'Whisper to <player id or power>: <message>' (private). "
                f"Orders are only accepted in the final round (round {rounds}); orders sent earlier are not recorded."
            ]
        defaults = {
            PhaseType.MOVEMENT: "Units without an order hold.",
            PhaseType.RETREATS: "Dislodged units without an order are disbanded.",
            PhaseType.ADJUSTMENTS: "Unordered builds are waived and missing disbands are chosen automatically.",
        }
        phase = self.engine.phase
        lines = [
            f"NOW: final negotiation round ({rounds} of {rounds}). This reply must submit your {phase.value} "
            "orders: a line 'Submit Orders:' followed by one order per line. You may also send messages. "
            f"{defaults[phase]}"
        ]
        if not self.engine.get_orderable_locations(power_name):
            lines.append("You have nothing to order, so send 'Submit Orders:' with no order lines.")
        return lines

    # --------------------------------------------------------------- actions
    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """
        Process a player's action (a multi-line string of communications and orders).
        """
        power_name = self.player_power_map[player_id]
        commands, error = self._parse_action(player_id, action)
        if error:
            return self.invalid(error)

        # In the final round, validate the complete order section before
        # emitting any part of the action. Invalid actions must be atomic.
        final_round = self._is_final_round()
        orders: List[str] = []
        if final_round:
            orders, error = self._validate_orders(power_name, commands["order_sections"])
            if error:
                return self.invalid(error)

        self.add_observation(from_id=player_id, to_id=player_id, message=action)
        for recipient, message in commands["messages"]:
            self._send_chat(player_id, recipient, message)
        if final_round:
            self._record_orders(player_id, power_name, orders)
        elif commands["order_sections"]:
            notice = (
                "Your orders were NOT recorded: orders are only accepted in the final negotiation round "
                f"(round {self.negotiations_per_phase} of {self.negotiations_per_phase}). Submit them again then."
            )
            if commands["messages"]:
                notice += " Your messages were sent."
            self.add_observation(ta.GAME_ID, player_id, notice, ta.ObservationType.GAME_ADMIN)
        elif not commands["messages"]:
            self.add_observation(
                ta.GAME_ID,
                player_id,
                "No message was sent: your reply had no 'Broadcast:' or 'Whisper to <player id>:' line. "
                "Each command must start at the beginning of a line.",
                ta.ObservationType.GAME_ADMIN,
            )

        if final_round:
            if self._all_required_orders_submitted():
                self._process_orders()
                if self.engine.game_over:
                    return self._final_outcome()
        else:
            # Default round-robin rotation moves to the next alive player; if the
            # rotation wraps around, a full round of negotiations has completed.
            next_pid = self.state.next_alive_player()
            if next_pid is not None and next_pid <= player_id:
                self._advance_negotiation_round()
        return None

    def _parse_action(self, player_id: int, action: str) -> Tuple[Dict[str, list], Optional[str]]:
        """Split an action into messages and order sections without side effects."""
        commands: Dict[str, list] = {"messages": [], "order_sections": []}
        starts = list(_COMMAND_START.finditer(action))
        error = None
        for index, start in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(action)
            error = self._parse_bare(player_id, start.group(1), action[start.start():end], commands)
            if error:
                break
        return commands, error

    def _parse_bare(self, player_id: int, keyword: str, segment: str, commands: Dict[str, list]) -> Optional[str]:
        keyword = keyword.lower()
        first_line = segment.strip().splitlines()[0][:80]
        if keyword == "broadcast":
            match = _BARE_BROADCAST.fullmatch(segment)
            if not match:
                return f"Could not read '{first_line}'. Write broadcasts as 'Broadcast: <message>'."
            message = match.group(1).strip()
            if message:
                commands["messages"].append((-1, message))
            return None
        if keyword == "whisper":
            match = _BARE_WHISPER.fullmatch(segment)
            if not match:
                return f"Could not read '{first_line}'. Write whispers as 'Whisper to <player id>: <message>'."
            return self._add_whisper(player_id, *match.groups(), commands)
        match = _BARE_SUBMIT.fullmatch(segment)
        commands["order_sections"].append(match.group(1))
        return None

    def _add_whisper(
        self, player_id: int, target: str, power_check: Optional[str], message: Optional[str],
        commands: Dict[str, list],
    ) -> Optional[str]:
        key = target.upper()
        if key.isascii() and key.isdigit():
            key = key.lstrip("0") or "0"
        target_id = next(
            (pid for pid, power in self.player_power_map.items() if key in (str(pid), power)),
            None,
        )
        if target_id is None:
            return f"Unknown whisper target: {target}. Use a player id or power name from the board summary."
        if target_id == player_id:
            return "You cannot whisper to yourself."
        target_power = self.player_power_map[target_id]
        if not self.state.is_player_alive(target_id):
            return f"Player {target_id} ({target_power}) is no longer in the game."
        if power_check and power_check.upper() != target_power:
            return f"Player {target_id} is not {power_check.upper()}."
        message = (message or "").strip()
        if not message:
            return "Whisper messages cannot be empty."
        commands["messages"].append((target_id, message))
        return None

    @staticmethod
    def _parse_order_lines(orders_text: str) -> List[str]:
        return [
            line.strip()
            for line in orders_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _validate_orders(self, power_name: str, sections: List[str]) -> Tuple[List[str], Optional[str]]:
        if not sections:
            return [], (
                "This is the final negotiation round: your reply must include a 'Submit Orders:' line followed "
                "by one order per line (send the line alone if you have nothing to order)."
            )
        if len(sections) != 1:
            return [], "Submit exactly one order section per action."
        orders = self._parse_order_lines(sections[0])
        _, invalid_orders = self.engine.parse_orders(power_name, orders)
        if invalid_orders:
            first = invalid_orders[0]
            more = f" ({len(invalid_orders) - 1} more invalid order(s))" if len(invalid_orders) > 1 else ""
            return [], (
                f"Invalid order submission: '{first['orders'][0]}': {first['reason']}{more}. "
                "No orders were recorded; resubmit the complete list."
            )
        return orders, None

    def _record_orders(self, player_id: int, power_name: str, orders: List[str]) -> None:
        self.pending_orders[power_name] = orders
        self.orders_submitted.add(player_id)
        parsed, _ = self.engine.parse_orders(power_name, orders)
        listed = "; ".join(str(order) for order in parsed) or "no orders"
        self.add_observation(
            from_id=ta.GAME_ID,
            to_id=player_id,
            message=(
                f"Orders received for {power_name} ({len(parsed)}): {listed}. They resolve once every power "
                "has submitted."
            ),
        )

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """A player who repeatedly sends invalid replies is eliminated; their units stay and hold."""
        power_name = self.player_power_map[player_id]
        self.eliminate(player_id)
        self.engine.powers[power_name].is_defeated = True
        self.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=f"Player {player_id} ({power_name}) has been eliminated after repeated invalid moves.",
            observation_type=ta.ObservationType.GAME_ADMIN,
        )
        alive = [pid for pid in self.player_power_map if self.state.is_player_alive(pid)]
        if len(alive) <= 1:
            return self.winner(alive, reason="All other players were eliminated by repeated invalid moves.")
        if self._is_final_round():
            # The eliminated power submits no orders, so the phase can still resolve.
            self.pending_orders.setdefault(power_name, [])
            self.orders_submitted.add(player_id)
            if self._all_required_orders_submitted():
                self._process_orders()
                if self.engine.game_over:
                    return self._final_outcome()
        else:
            next_pid = self.state.next_alive_player(after=player_id)
            if next_pid is not None and next_pid <= player_id:
                self._advance_negotiation_round()
        # The engine hands the turn to the next alive player
        return None

    # ------------------------------------------------------------ phase flow
    def _is_final_round(self) -> bool:
        return self.current_negotiation_round == self.negotiations_per_phase - 1

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

    def _process_orders(self) -> None:
        """Resolve all submitted orders and announce the results."""
        self.engine.resolve_orders(self.pending_orders)
        record = self.engine.order_history[-1]

        self.orders_submitted = set()
        self.pending_orders = {}
        self.current_negotiation_round = 0
        self.state.game_state = self._build_game_state()

        self._announce_order_results(record)
        self._sync_defeated_players()
        if not self.engine.game_over:
            self._announce_phase_start()

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
                        f"Player {player_id} ({power_name}) has no units or "
                        "supply centers left and is eliminated from the game."
                    ),
                    observation_type=ta.ObservationType.GAME_ADMIN,
                )

    def _advance_negotiation_round(self):
        """Advance to the next negotiation round"""
        self.current_negotiation_round += 1
        self.state.game_state['current_negotiation_round'] = self.current_negotiation_round
        message = (
            f"Negotiation round {self.current_negotiation_round + 1} of "
            f"{self.negotiations_per_phase} begins."
        )
        if self._is_final_round():
            message += " This is the final round: every power must submit its orders now."
        self.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message)

    def _final_outcome(self) -> ta.Outcome:
        if self.engine.winners:
            winning_players = [self.power_player_map[power] for power in self.engine.winners]
            reason = (
                f"Victory achieved by: {', '.join(self.engine.winners)} "
                f"({', '.join(f'Player {pid}' for pid in winning_players)})\n\n"
            )
        else:
            winning_players = []
            reason = f"Game ended in a DRAW after {self.engine.completed_game_years} game years.\n\n"
        reason += "Final supply center counts:\n" + "".join(
            f"- Player {self.power_player_map[power]} ({power}): "
            f"{len(self.engine.powers[power].controlled_centers)} centers\n"
            for power in self._powers_by_player()
        )
        if winning_players:
            return self.winner(winning_players, reason=reason)
        return self.draw(reason=reason)

    # --------------------------------------------------------- announcements
    def _announce_phase_start(self) -> None:
        rounds = self.negotiations_per_phase
        self.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,
            message=(
                f"===== {self.engine.season.value} {self.engine.year} {self.engine.phase.value} phase begins: "
                f"{rounds} negotiation round(s), orders are due in round {rounds} ====="
            ),
        )

    def _announce_order_results(self, record: Dict[str, Any]) -> None:
        """Publish every order of the resolved phase with its outcome."""
        phase = record["phase"]
        results = record["results"]
        lines = [f"===== Results of {record['season']} {record['year']} {phase} ====="]
        for power_name in self._powers_by_player():
            if results.get(power_name):
                lines.append(f"{self._power_label(power_name)}:")
                lines.extend(f"  {order}: {outcome}" for order, outcome in results[power_name])
        if phase == PhaseType.MOVEMENT.value:
            if record["dislodged"]:
                lines.append("Dislodged units (they retreat or disband in the Retreats phase):")
                for entry in record["dislodged"]:
                    options = ", ".join(entry["retreat_options"]) or "none, so it will be disbanded"
                    lines.append(
                        f"  {entry['unit']} ({self._power_label(entry['power'])}), attacked from "
                        f"{entry['attacked_from']}: can retreat to {options}"
                    )
            else:
                lines.append("No units were dislodged.")
        elif phase == PhaseType.RETREATS.value:
            if not any(results.values()):
                lines.append("No units had to retreat.")
            if record["season"] == Season.FALL.value:
                lines.extend(self._center_change_lines(record))
        elif not any(results.values()):
            lines.append("No units were built or disbanded.")
        self.add_observation(from_id=ta.GAME_ID, to_id=-1, message="\n".join(lines))

    def _center_change_lines(self, record: Dict[str, Any]) -> List[str]:
        year = record["year"]
        if record["center_changes"]:
            lines = [f"Supply centers that changed hands at the end of Fall {year}:"]
            lines.extend(
                f"  {center}: {old_owner or 'unowned'} -> {new_owner}"
                for center, old_owner, new_owner in record["center_changes"]
            )
        else:
            lines = [f"No supply centers changed hands at the end of Fall {year}."]
        counts = ", ".join(
            f"{self._power_label(power)} {len(self.engine.powers[power].controlled_centers)}"
            for power in self._powers_by_player()
        )
        lines.append(f"Supply centers now: {counts} ({self._victory_threshold()} needed to win).")
        return lines

    # --------------------------------------------------------------- helpers
    def _powers_by_player(self) -> List[str]:
        return [power for _, power in sorted(self.player_power_map.items())]

    def _power_label(self, power_name: str) -> str:
        return f"{power_name} (Player {self.power_player_map[power_name]})"

    def _status(self, player_id: int) -> str:
        return "" if self.state.is_player_alive(player_id) else " [eliminated]"

    def _victory_threshold(self) -> int:
        return len(self.engine.map.get_supply_centers()) // 2 + 1

    @staticmethod
    def _unit_label(unit) -> str:
        return str(unit).lstrip("*")

    def _send_chat(self, sender: int, recipient: int, message: str) -> None:
        """Deliver a player message, labeled as public or private for the reader."""
        label = "(to all)" if recipient == -1 else "(privately to you)"
        message = self.strip_role_tags(message)
        self._log_chat(sender, recipient, message)
        self.state.add_event(
            from_id=sender,
            message=f"{label} {message}",
            observation_type=ta.ObservationType.PLAYER_ACTION,
            to_id=recipient,
        )

    def add_observation(self, from_id: int, to_id: int, message: str, observation_type: Optional[ta.ObservationType] = None):
        """Add an observation to the chat history"""
        if observation_type is None:
            observation_type = ta.ObservationType.GAME_MESSAGE if from_id == ta.GAME_ID else ta.ObservationType.PLAYER_ACTION
        self._log_chat(from_id, to_id, message)
        self.state.add_event(from_id=from_id, message=message, observation_type=observation_type, to_id=to_id)

    def _log_chat(self, from_id: int, to_id: int, message: str) -> None:
        self.chat_history.append({
            "turn": self.state.turn,
            "from": from_id,
            "from_power": self.player_power_map.get(from_id),
            "to": to_id,
            "to_power": self.player_power_map.get(to_id),
            "message": message
        })
