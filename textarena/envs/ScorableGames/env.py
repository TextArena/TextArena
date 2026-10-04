import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.ScorableGames.renderer import (
    render_game_issues,
    render_deal_with_scores_and_votes
)


# Canonical commands are bare and must start a line, so free-text rationale can
# coexist on the preceding lines without ambiguity. Keywords are case-insensitive.
_COMMAND_PATTERNS = (
    ("Propose", re.compile(r"^[ \t]*Propose:?(?=[ \t]|$)", re.M | re.I)),
    ("Accept",  re.compile(r"^[ \t]*Accept:?(?=[ \t]|$)",  re.M | re.I)),
    ("Reject",  re.compile(r"^[ \t]*Reject:?(?=[ \t]|$)",  re.M | re.I)),
)

# Only option-shaped tokens (an issue letter followed by a number) on the
# proposal line are read; other words such as "And" or "Because" are ignored.
_OPTION_TOKEN = re.compile(r"[A-Za-z]\d+")


def _find_command(action: str):
    """Return the first command line in an action, or (None, None)."""
    commands = _find_commands(action)
    return commands[0] if commands else (None, None)


def _find_commands(action: str):
    """Return all command lines in source order."""
    commands = []
    for kind, pattern in _COMMAND_PATTERNS:
        commands.extend((kind, match) for match in pattern.finditer(action))
    return sorted(commands, key=lambda command: command[1].start())


class ScorableGamesEnv(ta.GameEnv):
    """
    Multi-player negotiation environment based on LLM-Deliberation research.
    Players negotiate over multiple issues with private scoring functions.
    """

    min_players = 2
    max_players = 15

    game_config = ta.Param(
        "base", "The scenario folder under `games_descriptions/`, listed in the table above.",
        check=lambda name: bool(name) and os.path.basename(name) == name and name not in {".", ".."},
        rule="a configuration directory name",
    )
    max_rounds = ta.Param(120, "The total number of turns before the game ends without a deal.", min=1)
    required_votes = ta.Param(
        None, "The acceptances needed for a deal to pass. None means all players but one.", type=int, min=1,
    )
    veto_roles = ta.Param(
        ["p1", "p2"], "The scenario roles whose acceptance is mandatory.",
        check=lambda roles: all(isinstance(role, str) and role for role in roles),
        rule="a list of non-empty role names",
    )
    unanimity_bonus_role = ta.Param(
        "p1", "The scenario role that earns the unanimity bonus.", optional=True, check=bool,
        rule="a non-empty role name",
    )
    starting_role = ta.Param(
        "p1", "The scenario role that moves first. Player 0 starts if no party has that role.", optional=True,
        check=bool, rule="a non-empty role name",
    )
    invalid_move_default = ta.Param(
        "Accept", "The vote cast for a player who exceeds the invalid-move allowance, including on a deal proposed "
                  "for them.", check=lambda vote: vote.strip().title() in {"Accept", "Reject"},
        rule="'Accept' or 'Reject' (in any case)",
    )
    error_allowance = ta.Param(3, "The consecutive invalid moves that only produce a warning.", min=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_turns = self.max_rounds  # engine turn limit
        self.invalid_move_default = self.invalid_move_default.strip().title()

        self.game_dir = os.path.join(os.path.dirname(__file__), "games_descriptions", self.game_config)
        self._load_game_configuration()
        # Each scenario has a fixed cast of parties.
        self.min_players = self.max_players = len(self.player_configs)
        if self.required_votes is not None and self.required_votes > self.max_players:
            raise ValueError(f"required_votes cannot exceed the configured player count ({self.max_players})")

    # game_state is the canonical owner of all mutable gameplay containers.
    @property
    def current_deal(self) -> Dict[str, str]:
        return self.game_state["current_deal"]

    @current_deal.setter
    def current_deal(self, value: Dict[str, str]):
        self.game_state["current_deal"] = value

    @property
    def negotiation_history(self) -> List[Dict[str, Any]]:
        return self.game_state["negotiation_history"]

    @negotiation_history.setter
    def negotiation_history(self, value: List[Dict[str, Any]]):
        self.game_state["negotiation_history"] = value

    @property
    def player_votes(self) -> Dict[int, str]:
        return self.game_state["player_votes"]

    @player_votes.setter
    def player_votes(self, value: Dict[int, str]):
        self.game_state["player_votes"] = value

    @property
    def valid_actions_this_round(self) -> set:
        return self.game_state["valid_actions_this_round"]

    @valid_actions_this_round.setter
    def valid_actions_this_round(self, value: set):
        self.game_state["valid_actions_this_round"] = value

    def setup(self) -> Dict[str, Any]:
        return {
            "current_deal": {},
            "negotiation_history": [],
            "player_votes": {},
            "valid_actions_this_round": set(),
            "terminal_result": None,
        }

    def on_start(self):
        # Set starting player based on configured starting role
        starting_player_id = self._get_player_by_role(self.starting_role)
        if starting_player_id is not None:
            self.set_current_player(starting_player_id)

    def _load_game_configuration(self):
        """Load game configuration from files."""
        if not os.path.exists(self.game_dir):
            raise FileNotFoundError(f"Game configuration directory not found: {self.game_dir}")

        # Load global instructions
        global_file = os.path.join(self.game_dir, "global_instructions.txt")
        with open(global_file, 'r') as f:
            self.global_instructions = f.read().strip()

        # Parse issues from global instructions
        self._parse_issues_from_global_instructions()

        # Load player configurations
        config_file = os.path.join(self.game_dir, "config.txt")
        self._load_player_configurations(config_file)

        # Load player scores and instructions
        self._load_player_data()

    def _parse_issues_from_global_instructions(self):
        """Parse issue definitions from global instructions."""
        self.issues = {}

        # Split by the separator lines to get individual issue sections
        sections = re.split(r'=+', self.global_instructions)

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Look for Issue X: "Name" pattern
            issue_match = re.search(r'Issue ([A-Z]):\s*"([^"]+)"', section)
            if not issue_match:
                continue

            issue_key = issue_match.group(1)
            issue_name = issue_match.group(2)

            options = {}

            # Find all options in this section: A1 "name": description
            option_pattern = rf'{issue_key}(\d+)\s+"([^"]+)":\s*([^\n]+(?:\n(?!{issue_key}\d)[^\n]*)*)'
            option_matches = re.findall(option_pattern, section, re.MULTILINE)

            for option_num, option_name, option_desc in option_matches:
                option_key = f"{issue_key}{option_num}"
                # Clean up the description
                clean_desc = re.sub(r'\s+', ' ', option_desc.strip())
                options[option_key] = f"{option_name}: {clean_desc}"

            if options:  # Only add if we found valid options
                self.issues[issue_key] = {
                    "name": issue_name,
                    "options": options
                }

    def _load_player_configurations(self, config_file: str):
        """Load player configurations from config.txt."""
        self.player_configs = {}

        with open(config_file, 'r') as f:
            for line_num, line in enumerate(f):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                parts = [part.strip() for part in line.split(',')]
                if len(parts) != 5:
                    raise ValueError(f"Invalid config line {line_num + 1}: {line}")

                agent_name, file_name, role, incentive, model = parts
                player_id = len(self.player_configs)

                self.player_configs[player_id] = {
                    "agent_name": agent_name,
                    "file_name": file_name,
                    "role": role,
                    "incentive": incentive,
                    "model": model
                }

    def _get_player_by_role(self, role: str) -> Optional[int]:
        """Get player ID by role (p1, p2, etc.)."""
        for player_id, config in self.player_configs.items():
            if config["role"] == role:
                return player_id
        return None

    def _load_player_data(self):
        """Load player scores and individual instructions."""
        self.player_scores = {}
        self.player_instructions = {}

        for player_id, config in self.player_configs.items():
            file_name = config["file_name"]
            incentive = config["incentive"]

            # Load scores
            scores_file = os.path.join(self.game_dir, "scores_files", f"{file_name}.txt")
            self.player_scores[player_id] = self._load_player_scores(scores_file)

            # Load individual instructions
            instructions_file = os.path.join(
                self.game_dir, "individual_instructions", incentive, f"{file_name}.txt"
            )
            with open(instructions_file, 'r') as f:
                self.player_instructions[player_id] = f.read().strip()

    def _load_player_scores(self, scores_file: str) -> Dict[str, Dict[str, int]]:
        """Load player scoring function from scores file."""
        scores = {}

        with open(scores_file, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]

        # Map lines to issues (A, B, C, etc.)
        issue_keys = sorted(self.issues.keys())

        for i, line in enumerate(lines[:-1]):  # Last line is threshold
            if i < len(issue_keys):
                issue_key = issue_keys[i]
                score_values = [int(x.strip()) for x in line.split(',')]

                # Map scores to options (A1, A2, etc.)
                issue_options = sorted(self.issues[issue_key]["options"].keys())
                issue_scores = {}

                for j, score in enumerate(score_values):
                    if j < len(issue_options):
                        option_key = issue_options[j]
                        issue_scores[option_key] = score

                scores[issue_key] = issue_scores

        # Store minimum threshold
        if lines:
            scores["threshold"] = int(lines[-1])

        return scores

    def prompt(self, player_id: int) -> str:
        """Generate initial prompt for a player."""
        config = self.player_configs[player_id]
        agent_name = config["agent_name"]

        # Extract only the scenario part (before issues) from global instructions
        global_text = self._extract_scenario_from_global_instructions(agent_name)

        # Get individual instructions with scores filled in
        individual_text = self._fill_scores_in_instructions(player_id)

        # Generate dynamic voting rules based on configuration
        voting_rules = "\n" + self._generate_voting_rules_text(player_id)

        # Game rules and actions
        rules_text = f"""

GAME RULES:
- This is a {self.state.num_players}-player negotiation game with {self.max_rounds} rounds maximum.
- Currently, it is Round {self.state.turn + 1} of {self.max_rounds}.
- You must negotiate to reach a deal regarding all issues.
- Your goal is to maximize your total score from the final deal.
- The game ends when a deal is accepted or max rounds reached.
- You cannot under any circumstances disclose numbers in your scoring sheet or the values of the deal to the other parties. But you can share
high-level priorities (e.g., you can say I cannot accept option D5, etc.)

REQUIRED ACTION FORMAT:
- You must propose complete deals covering all issues (use space-separated format like A1 B2 C3 D1 E4).
- Always provide your reasoning BEFORE the action command
- The command (Propose ..., Accept, or Reject) must start at the beginning of its own line
- Any text after the command line will be ignored

Examples:
- Make a proposal:
  ```
  I think this balances everyone's interests while protecting the environment.
  Propose A1 B2 C2 D2 E3
  ```

- Accept a proposal:
  ```
  This meets my minimum acceptable score and helps the community.
  Accept
  ```

- Reject a proposal:
  ```
  The environmental impact is too severe for my constituents.
  Reject
  ```

{voting_rules}

SCORING:
- You can see your own scores for different options below.
- Other players have different preferences (hidden from you).
- Your minimum acceptable score is {self.player_scores[player_id].get('threshold', 0)} points.
- If no deal is reached after max rounds, you will get {self.player_scores[player_id].get('threshold', 0)} points.
"""

        # Show available issues
        issues_text = "\n" + render_game_issues(self.issues)

        # Show player's private scores
        if self.current_deal:
            scores_text = "\n" + render_deal_with_scores_and_votes(
                self.current_deal, self.issues,
                self.player_scores[player_id], agent_name,
                self.player_votes, self.player_configs
            )
        else:
            scores_text = f"\n{agent_name}'s Private Scoring Function:\n"
            scores_text += "=" * 30 + "\n"
            for issue_key, issue_scores in self.player_scores[player_id].items():
                scores_text += f"{issue_key}: {issue_scores}\n".replace('threshold', 'Minimum acceptable score')

        # Reorder: global_text + issues_text + individual_text + rules_text + scores_text
        return global_text + "\n" + issues_text + "\n\n" + individual_text + "\n" + rules_text + "\n" + scores_text

    def _fill_scores_in_instructions(self, player_id: int) -> str:
        """Fill score placeholders in individual instructions."""
        instructions = self.player_instructions[player_id]
        scores = self.player_scores[player_id]

        # Replace score placeholders like #A1_NUM, #A_MAX_NUM, etc.
        for issue_key, issue_scores in scores.items():
            if issue_key == "threshold":
                continue

            # Replace individual option scores
            for option_key, score in issue_scores.items():
                placeholder = f"#{option_key}_NUM"
                instructions = instructions.replace(placeholder, str(score))

            # Replace max score for issue
            max_score = max(issue_scores.values()) if issue_scores else 0
            max_placeholder = f"#{issue_key}_MAX_NUM"
            instructions = instructions.replace(max_placeholder, str(max_score))

        return instructions

    def _generate_voting_rules_text(self, player_id: int) -> str:
        """Generate dynamic voting rules text based on configuration parameters."""

        # Calculate required votes
        required_votes = self.required_votes if self.required_votes is not None else (self.state.num_players - 1)

        # Build threshold explanation
        threshold_text = f"- A proposal passes if at least {required_votes} out of {self.state.num_players} players accept"

        # Build veto power explanation
        veto_text = ""
        if self.veto_roles:
            veto_players = []
            current_player_has_veto = False

            for role in self.veto_roles:
                veto_player_id = self._get_player_by_role(role)
                if veto_player_id is not None:
                    veto_player_name = self.player_configs[veto_player_id]["agent_name"]
                    if veto_player_id == player_id:
                        current_player_has_veto = True
                    else:
                        veto_players.append(veto_player_name)

            if current_player_has_veto and veto_players:
                if len(veto_players) == 1:
                    veto_text = f"- Both you and {veto_players[0]} have veto power - you both must accept for any deal to pass"
                else:
                    veto_text = f"- You and {', '.join(veto_players)} have veto power - all veto players must accept for any deal to pass"
            elif current_player_has_veto and not veto_players:
                veto_text = f"- You have veto power - you must accept for any deal to pass"
            elif veto_players:
                if len(veto_players) == 1:
                    veto_text = f"- {veto_players[0]} has veto power - they must accept for any deal to pass"
                else:
                    veto_text = f"- {', '.join(veto_players)} have veto power - they all must accept for any deal to pass"

        # Build unanimity bonus explanation
        bonus_text = ""
        if self.unanimity_bonus_role:
            bonus_player_id = self._get_player_by_role(self.unanimity_bonus_role)
            if bonus_player_id is not None:
                bonus_player_name = self.player_configs[bonus_player_id]["agent_name"]
                if bonus_player_id == player_id:
                    bonus_text = f"- UNANIMITY BONUS: If all {self.state.num_players} players accept, you get +10 bonus points"
                else:
                    bonus_text = f"- {bonus_player_name} gets +10 bonus points if all players achieve unanimity"

        # Combine all parts
        voting_rules = "VOTING RULES:\n"
        voting_rules += threshold_text + "\n"
        voting_rules += "- Proposing a deal counts as your acceptance of it; a new proposal clears all earlier votes\n"
        if veto_text:
            voting_rules += veto_text + "\n"
        if bonus_text:
            voting_rules += bonus_text + "\n"

        return voting_rules

    def _extract_scenario_from_global_instructions(self, agent_name: str) -> str:
        """Extract only the scenario part (before issues) from global instructions."""
        # Replace agent name in global instructions
        global_text = self.global_instructions.replace(f'"{agent_name}"', f'"{agent_name}" (represented by you)')

        # Find where the issues start and cut off there
        # Look for the first "Issue A:" pattern to know where to stop
        issue_start = re.search(r'Issue [A-Z]:', global_text)
        if issue_start:
            # Return everything before the first issue
            return global_text[:issue_start.start()].strip()
        else:
            # If no issues found, return the whole text (fallback)
            return global_text

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # the env emits its own "Your action: ..." echo inside apply

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process a player's action."""
        action = self.strip_role_tags(action).strip()  # validate exactly the text other agents will see
        valid, reason = self._validate_action(action)
        if not valid:
            return self.invalid(reason)

        # Invalid submissions must not enter the action log or active-round state.
        self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        self.valid_actions_this_round.add(player_id)
        self._process_action(player_id, action)

        # Check for game end (the round limit is handled by the engine via on_turn_limit)
        if self._check_deal_accepted():
            return self._final_outcome()

        return None  # engine rotates to the next player

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # Player exceeded error allowance - apply default action and advance turn
        self._apply_default_action(player_id)
        self.valid_actions_this_round.add(player_id)

        # A defaulted action consumes a round.
        self.state.game_info[player_id]["turn_count"] += 1
        self.state.turn += 1

        if self._check_deal_accepted() or self.state.turn >= self.max_rounds:
            return self._final_outcome()

        self.set_next_player((player_id + 1) % self.state.num_players)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self._final_outcome()

    def _final_outcome(self) -> ta.Outcome:
        """Compute the terminal Outcome; the engine finalizes it (rewards/done)."""
        if self._check_deal_accepted():
            return self._finalize_accepted_deal()
        return self._handle_no_deal()

    def _is_valid_action(self, action: str) -> bool:
        """Check command syntax without applying proposal-dependent context."""
        commands = _find_commands(action)
        if len(commands) != 1:
            return False
        kind, _ = commands[0]
        return kind != "Propose" or self._is_valid_proposal(action)

    def _validate_action(self, action: str) -> Tuple[bool, Optional[str]]:
        """Validate syntax and context without logging or mutating gameplay state."""
        commands = _find_commands(action)
        if len(commands) > 1:
            return False, "Multiple decision lines detected. Use exactly one Propose, Accept, or Reject command"
        if not commands:
            return False, self._invalid_reason(action)
        if not self._is_valid_action(action):
            return False, self._invalid_reason(action)

        kind, _ = commands[0]
        if kind in ("Accept", "Reject") and not self.current_deal:
            return False, "No current proposal to vote on"
        return True, None

    def _invalid_reason(self, action: str) -> str:
        """Determine the reason for an invalid action."""
        commands = _find_commands(action)
        if len(commands) > 1:
            return "Multiple decision lines detected. Use exactly one Propose, Accept, or Reject command"
        kind, _ = _find_command(action)
        if kind == "Propose":
            return "Invalid proposal format. Use: Propose A1 B2 C3 D1 E4 (cover all issues with valid options)"
        elif kind is None:
            return "Invalid action. Use: Propose A1 B2 C3 D1 E4, Accept, or Reject (the command must start a line)"
        else:
            return "Invalid action format"

    def _is_valid_proposal(self, action: str) -> bool:
        """Check if a proposal is valid."""
        return self._parse_proposal(action) is not None

    def _parse_proposal(self, action: str) -> Optional[Dict[str, str]]:
        """Parse a complete proposal using the same rules as validation."""
        try:
            kind, match = _find_command(action)
            if kind != "Propose":
                return None

            proposal_part = action[match.end():].strip()
            first_line = proposal_part.split('\n')[0].strip()
            deal_parts = first_line.split()

            expected_issues = set(self.issues.keys())
            proposal = {}

            for raw_part in deal_parts:
                part = raw_part.strip().rstrip('.,!?;:')
                if not _OPTION_TOKEN.fullmatch(part):
                    continue
                option = part.upper()
                issue_key = option[0]
                if issue_key in expected_issues:
                    if option not in self.issues[issue_key]["options"]:
                        return None
                    proposal[issue_key] = option

            return proposal if set(proposal) == expected_issues else None

        except Exception:
            return None

    def _process_action(self, player_id: int, action: str) -> Optional[ta.Invalid]:
        """Process a validated action; may still return Invalid (e.g. voting with no proposal on the table)."""
        kind, _ = _find_command(action)
        if kind == "Propose":
            return self._process_proposal(player_id, action)
        elif kind == "Accept":
            return self._process_vote(player_id, action, "Accept")
        elif kind == "Reject":
            return self._process_vote(player_id, action, "Reject")
        return None

    def _process_proposal(self, player_id: int, action: str) -> Optional[ta.Invalid]:
        """Process a deal proposal."""
        _, match = _find_command(action)

        # Extract rationale (everything before the Propose command line)
        rationale = action[:match.start()].strip()
        new_deal = self._parse_proposal(action)

        # Only proceed if we have a complete deal
        if new_deal is not None:
            config = self.player_configs[player_id]

            # Check if this is identical to current deal
            if self.current_deal and new_deal == self.current_deal:
                # Same deal - treat as acceptance
                self.player_votes[player_id] = "Accept"

                # Announce as acceptance with rationale
                if rationale:
                    message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} accepts the current proposal"
                else:
                    message = f"{config['agent_name']} accepts the current proposal"

                self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

                # Record as acceptance in history
                self.negotiation_history.append({
                    "player_id": player_id,
                    "action_type": "Accept",
                    "rationale": rationale,
                    "proposal": self.current_deal.copy(),
                    "round": self.state.turn
                })
            else:
                # Different deal - normal proposal logic
                self.current_deal = new_deal

                # Clear previous votes; the proposer supports their own proposal
                self.player_votes = {player_id: "Accept"}

                # Announce the proposal with rationale
                deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(new_deal.items())])

                if rationale:
                    message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} proposes: {deal_str}"
                else:
                    message = f"{config['agent_name']} proposes: {deal_str}"

                self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

                # Record in history with enhanced structure
                self.negotiation_history.append({
                    "player_id": player_id,
                    "action_type": "Propose",
                    "rationale": rationale,
                    "proposal": new_deal.copy(),
                    "round": self.state.turn
                })
            return None
        else:
            # Incomplete proposal (validation and parsing disagree, e.g. punctuation) - invalid move
            return self.invalid(self._invalid_reason(action))

    def _process_vote(self, player_id: int, action: str, vote: str) -> Optional[ta.Invalid]:
        """Process an accept/reject vote."""
        if not self.current_deal:
            # No current proposal - handle as invalid action
            return self.invalid(self._invalid_reason(action))

        # Extract rationale (everything before the Accept/Reject command line)
        _, match = _find_command(action)
        rationale = action[:match.start()].strip() if match else ""

        self.player_votes[player_id] = vote

        config = self.player_configs[player_id]

        if rationale:
            message = f"{config['agent_name']} says: {rationale}\n{config['agent_name']} votes: {vote}"
        else:
            message = f"{config['agent_name']} votes: {vote}"

        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # Record in history with enhanced structure
        self.negotiation_history.append({
            "player_id": player_id,
            "action_type": vote,
            "rationale": rationale,
            "proposal": self.current_deal.copy(),
            "round": self.state.turn
        })
        return None

    def _apply_default_action(self, player_id: int):
        """Apply default action when player exceeds error allowance."""
        config = self.player_configs[player_id]

        if self.current_deal:
            # There's a current proposal - default their vote
            self.player_votes[player_id] = self.invalid_move_default

            message = f"{config['agent_name']} exceeded number of invalid actions limit, defaulting vote to {self.invalid_move_default}"
            self.broadcast(message, ta.ObservationType.GAME_ADMIN)

            # Record in history with enhanced structure
            self.negotiation_history.append({
                "player_id": player_id,
                "action_type": self.invalid_move_default,
                "rationale": "Auto-defaulted after exceeding number of invalid actions limit",
                "proposal": self.current_deal.copy(),
                "round": self.state.turn
            })
        else:
            # No current proposal - generate optimal proposal
            optimal_proposal = self._generate_optimal_proposal(player_id)
            self.current_deal = optimal_proposal

            # Clear previous votes; the defaulted player's own vote is the configured default
            self.player_votes = {player_id: self.invalid_move_default}

            # Announce the auto-generated proposal
            deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(optimal_proposal.items())])
            message = f"{config['agent_name']} exceeded error limit, auto-proposing: {deal_str}"

            self.broadcast(message, ta.ObservationType.GAME_ADMIN)

            # Record in history with enhanced structure
            self.negotiation_history.append({
                "player_id": player_id,
                "action_type": "Propose",
                "rationale": f"Auto-defaulted after exceeding number of invalid actions limit",
                "proposal": optimal_proposal.copy(),
                "round": self.state.turn
            })

        # Reset error count after applying default action so the game can continue normally
        self.state.error_count = 0
        self.state.made_invalid_move = False

    def _generate_optimal_proposal(self, player_id: int) -> Dict[str, str]:
        """Generate an optimal proposal that maximizes the player's score."""
        optimal_deal = {}
        player_scores = self.player_scores[player_id]

        for issue_key in self.issues.keys():
            if issue_key in player_scores and issue_key != "threshold":
                # Find the option with the highest score for this issue
                best_option = None
                best_score = float('-inf')

                for option_key, score in player_scores[issue_key].items():
                    if score > best_score:
                        best_score = score
                        best_option = option_key

                if best_option:
                    optimal_deal[issue_key] = best_option

        return optimal_deal

    def _check_deal_accepted(self) -> bool:
        """
        Check if the current deal has been accepted using configurable voting rules:
        - Need required_votes accept votes (default: num_players - 1)
        - Players with veto_roles must accept (default: ["p1", "p2"])
        - Deal cannot pass until all veto players have voted
        """
        if not self.current_deal or not self.player_votes:
            return False

        total_players = self.state.num_players
        accept_votes = sum(1 for vote in self.player_votes.values() if vote == "Accept")
        required_votes = self.required_votes if self.required_votes is not None else (total_players - 1)
        if accept_votes < required_votes:
            return False

        veto_player_ids = {
            player_id
            for role in self.veto_roles
            if (player_id := self._get_player_by_role(role)) is not None
        }
        return all(self.player_votes.get(pid) == "Accept" for pid in veto_player_ids)

    def _check_unanimity(self) -> bool:
        """Check if all players voted Accept (for P1 bonus)."""
        if len(self.player_votes) != self.state.num_players:
            return False
        return all(vote == "Accept" for vote in self.player_votes.values())

    def _finalize_accepted_deal(self) -> ta.Outcome:
        """Finalize an accepted deal, determine scores, and build the threshold-based Outcome."""
        cached = self.game_state.get("terminal_result")
        if cached is not None:
            return self.outcome(cached["rewards"], cached["reason"])

        deal_str = ", ".join([f"{k}:{v}" for k, v in self.current_deal.items()])

        self.broadcast(f"DEAL ACCEPTED: {deal_str}", ta.ObservationType.GAME_ADMIN)

        # Step 1: Calculate final scores
        final_scores = {}
        unanimity_achieved = self._check_unanimity()
        bonus_player_id = self._get_player_by_role(self.unanimity_bonus_role)

        for pid in range(self.state.num_players):
            score = self._calculate_player_score(pid, self.current_deal)

            # Apply unanimity bonus if applicable
            if unanimity_achieved and pid == bonus_player_id:
                score += 10
                role_name = self.player_configs[pid]["agent_name"]
                self.message(pid, f"{role_name} unanimity bonus: +10 points", ta.ObservationType.GAME_ADMIN)

            final_scores[pid] = score

            # Save raw score in game_info
            self.state.game_info[pid]["score"] = score
            self.state.game_info[pid]["threshold"] = self.player_scores[pid].get("threshold", 0)
            self.state.game_info[pid]["deal_accepted"] = True

            # Announce score vs threshold
            threshold = self.player_scores[pid].get("threshold", 0)
            config = self.player_configs[pid]
            self.message(pid, f"{config['agent_name']} final score: {score} points (threshold: {threshold})", ta.ObservationType.GAME_ADMIN)

        # Step 2: Threshold-based rewards: +1 if the deal meets the player's minimum
        # acceptable score, -1 if it is worse than walking away with no deal (which scores 0)
        winners = [pid for pid, score in final_scores.items()
                if score >= self.player_scores[pid].get("threshold", 0)]
        rewards = {pid: (1.0 if pid in winners else -1.0) for pid in range(self.state.num_players)}

        # Step 3: Outcome annotation
        if winners:
            names = ", ".join(self.player_configs[pid]["agent_name"] for pid in winners)
            reason = (
                f"Deal accepted: {len(winners)} of {self.state.num_players} parties "
                f"met their minimum acceptable score ({names})"
            )
            self.state.step_info["winner_reason"] = reason
        else:
            reason = "Deal accepted, but no party met its minimum acceptable score"
        for pid in range(self.state.num_players):
            self.state.game_info[pid]["winner"] = pid in winners

        # Step 4: Log scores + rewards together
        lines = ["=== Final Scores and Rewards (Threshold-Based) ==="]
        for pid in range(self.state.num_players):
            config = self.player_configs[pid]
            score = final_scores[pid]
            reward = rewards[pid]
            threshold = self.player_scores[pid].get("threshold", 0)
            lines.append(f"{config['agent_name']}: {score} points (threshold {threshold}) → reward {reward:+.1f}")

        self.broadcast("\n".join(lines), ta.ObservationType.GAME_ADMIN)

        self.game_state["terminal_result"] = {
            "deal_accepted": True,
            "deal": self.current_deal.copy(),
            "scores": final_scores.copy(),
            "rewards": rewards.copy(),
            "reason": reason,
        }
        return self.outcome(rewards, reason)

    def _handle_no_deal(self) -> ta.Outcome:
        """Handle case where no deal was reached: every party falls back to exactly its
        minimum acceptable score, which is neither a success nor a failure (reward 0)."""
        cached = self.game_state.get("terminal_result")
        if cached is not None:
            return self.outcome(cached["rewards"], cached["reason"])

        self.broadcast("NO DEAL REACHED - Each player receives their minimum acceptable score", ta.ObservationType.GAME_ADMIN)

        fallback_scores = {}
        rewards = {pid: 0.0 for pid in range(self.state.num_players)}
        last_proposal = self.current_deal.copy()
        self.current_deal = {}
        self.player_votes = {}
        for player_id in range(self.state.num_players):
            threshold = self.player_scores[player_id].get("threshold", 0)
            fallback_scores[player_id] = threshold
            self.state.game_info[player_id]["score"] = threshold
            self.state.game_info[player_id]["threshold"] = threshold
            self.state.game_info[player_id]["deal_accepted"] = False

            # Add individual notification with human-friendly language
            config = self.player_configs[player_id]
            message = f"{config['agent_name']} receives minimum acceptable score: {threshold} points"
            self.message(player_id, message, ta.ObservationType.GAME_ADMIN)

        # A draw: no negotiated agreement, and nobody ends below their minimum
        for pid in range(self.state.num_players):
            self.state.game_info[pid]["winner"] = False
        reason = "No agreement reached - players received minimum acceptable scores (draw)"
        self.state.step_info["draw_reason"] = reason

        self.game_state["terminal_result"] = {
            "deal_accepted": False,
            "deal": None,
            "last_proposal": last_proposal,
            "scores": fallback_scores.copy(),
            "rewards": rewards.copy(),
            "reason": reason,
        }
        return self.outcome(rewards, reason)

    def _calculate_player_score(self, player_id: int, deal: Dict[str, str]) -> int:
        """Calculate a player's score for a given deal."""
        total_score = 0
        player_scores = self.player_scores[player_id]

        for issue_key, option in deal.items():
            if issue_key in player_scores and option in player_scores[issue_key]:
                total_score += player_scores[issue_key][option]

        return total_score

    def get_observation(self):
        """Get observation for current player."""
        player_id = self.state.current_player_id
        observation = self.state.get_current_player_observation()

        # Add current game state information with combined deal and scores
        if self.current_deal:
            config = self.player_configs[player_id]
            combined_summary = render_deal_with_scores_and_votes(
                self.current_deal, self.issues,
                self.player_scores[player_id], config["agent_name"],
                self.player_votes, self.player_configs
            )
            observation.append((ta.GAME_ID, combined_summary, ta.ObservationType.GAME_BOARD))

        return player_id, observation

    def get_board_str(self) -> str:
        """
        Return a formatted string representation of the negotiation state.
        - Ongoing: current deal with scores and voting status
        - Done: final results (deal accepted with scores OR no deal with thresholds)
        """
        terminal_result = self.game_state.get("terminal_result")
        if terminal_result is not None:
            lines = ["=== FINAL OUTCOME ===", ""]

            if terminal_result["deal_accepted"]:
                deal_str = ", ".join([f"{k}:{v}" for k, v in sorted(terminal_result["deal"].items())])
                lines.append(f"Final Deal Accepted: {deal_str}")
            else:
                lines.append("No deal was reached.")

            lines.append("")
            lines.append("=== PLAYER RESULTS ===")

            # Show each player's score and threshold
            for pid, config in self.player_configs.items():
                agent_name = config["agent_name"]

                score = terminal_result["scores"][pid]
                threshold = self.player_scores[pid].get("threshold", 0)
                reward = terminal_result["rewards"][pid]

                if terminal_result["deal_accepted"]:
                    status = "✅ Met threshold" if score >= threshold else "❌ Below threshold"
                else:
                    status = "No deal — fallback threshold score"
                lines.append(
                    f"{agent_name}: {score} points (threshold {threshold}) {status} → reward {reward:+.1f}"
                )

            return "\n".join(lines)

        # If the game is ongoing
        current_pid = self.state.current_player_id
        config = self.player_configs.get(current_pid, {"agent_name": f"Player {current_pid}"})
        agent_name = config["agent_name"]

        if self.current_deal:
            return render_deal_with_scores_and_votes(
                deal_state=self.current_deal,
                issues=self.issues,
                player_scores=self.player_scores[current_pid],
                player_name=agent_name,
                player_votes=self.player_votes,
                player_configs=self.player_configs
            )
        else:
            # No deal yet: show available issues
            return render_game_issues(self.issues)
