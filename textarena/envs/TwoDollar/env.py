"""
Two Dollar Negotiation Game Environment

A classic negotiation exercise where two players must agree on how to split $2.00.
Each player has secret role instructions that may include minimum thresholds,
behavioral constraints, or strategic guidelines.

Based on the original Two Dollar game used in negotiation research and education.
"""

import os
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.TwoDollar.renderer import render_game_state, render_negotiation_summary, render_final_results


class TwoDollarEnv(ta.GameEnv):
    """
    Two-player negotiation environment where players split a fixed amount of money.
    Players have secret role instructions that create different constraints and objectives.
    """

    min_players = 2
    max_players = 2

    # Command grammar: the decision is a bare command phrase on its own line
    # (this is what the prompts teach). Optional surrounding brackets and the
    # legacy embedded "[Command]" tokens are still recognized for backwards
    # compatibility, but brackets are never required.
    _BARE_ACCEPT_RE = re.compile(r"^[ \t]*(?:accept|\[[ \t]*accept[ \t]*\])[ \t]*[.!]?[ \t]*$", re.IGNORECASE | re.MULTILINE)
    _BARE_REJECT_RE = re.compile(r"^[ \t]*(?:reject|\[[ \t]*reject[ \t]*\])[ \t]*[.!]?[ \t]*$", re.IGNORECASE | re.MULTILINE)
    _BARE_PROPOSE_RE = re.compile(r"^[ \t]*propose[ \t]*:?[ \t]*(?P<rest>[^\n]*)$", re.IGNORECASE | re.MULTILINE)
    _PROPOSE_AMOUNT_RE = re.compile(r"[ \t]*\$(\d+(?:\.\d{1,2})?)[ \t]*[.!]?[ \t]*")
    _LEGACY_COMMAND_RE = re.compile(
        r"(?:\[(?P<decision>Accept|Reject)\][ \t]*[.!]?"
        r"|\[Propose\][ \t]*\$(?P<proposal>\d+(?:\.\d{1,2})?)[ \t]*[.!]?"
        r"|\[Propose[ \t]+\$(?P<inside>\d+(?:\.\d{1,2})?)[ \t]*\][ \t]*[.!]?)"
    )

    def __init__(self,
                 player_roles: Optional[List[str]] = None,
                 total_amount: float = 2.00,
                 max_rounds: int = 20,
                 error_allowance: int = 3):
        """
        Initialize the Two Dollar environment.

        Args:
            player_roles: List of 2 role names, or None for random assignment
            total_amount: Total money to be split (default: $2.00)
            max_rounds: Maximum number of negotiation rounds
            error_allowance: Number of invalid moves allowed before applying default action
        """
        if player_roles is not None and (
            not isinstance(player_roles, (list, tuple))
            or len(player_roles) != 2
            or any(not isinstance(role_name, str) for role_name in player_roles)
        ):
            raise ValueError("player_roles must contain exactly 2 role names")
        try:
            normalized_total = float(total_amount)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("total_amount must be a positive amount with at most two decimal places") from None
        if (
            not isinstance(total_amount, (int, float))
            or isinstance(total_amount, bool)
            or not math.isfinite(normalized_total)
            or normalized_total <= 0
            or round(normalized_total, 2) != normalized_total
        ):
            raise ValueError("total_amount must be a positive amount with at most two decimal places")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds <= 0:
            raise ValueError("max_rounds must be a positive integer")
        if not isinstance(error_allowance, int) or isinstance(error_allowance, bool) or error_allowance < 0:
            raise ValueError("error_allowance must be a non-negative integer")
        self.player_roles_config = list(player_roles) if player_roles is not None else None
        self.total_amount = normalized_total
        self.max_rounds = max_rounds
        self.error_allowance = error_allowance

        # Load all available roles
        self.available_roles = self._load_available_roles()

        # Assigned per reset
        self.player_roles = {}
        self.player_deadline = {}  # For x_rounds role

    # -- game_state-backed views (kept as attributes for renderers/analysis) --
    @property
    def current_proposal(self) -> Dict[str, Any]:
        return self.game_state["current_proposal"]

    @property
    def negotiation_history(self) -> List[Dict[str, Any]]:
        return self.game_state["negotiation_history"]

    @property
    def player_proposal_history(self) -> Dict[int, List[float]]:
        return self.game_state["player_proposal_history"]

    @property
    def final_amounts(self) -> Dict[int, float]:
        return self.game_state["final_amounts"]

    def _load_available_roles(self) -> Dict[str, Dict]:
        """Load all role definitions from enforceable and non_enforceable folders"""
        roles_dir = os.path.join(os.path.dirname(__file__), "roles")
        available_roles = {}

        for folder in ["enforceable", "non_enforceable"]:
            folder_path = os.path.join(roles_dir, folder)
            if os.path.exists(folder_path):
                for filename in sorted(os.listdir(folder_path)):
                    if filename.endswith('.json'):
                        role_name = filename[:-5]  # Remove .json
                        with open(os.path.join(folder_path, filename), 'r') as f:
                            available_roles[role_name] = json.load(f)

        return available_roles

    def setup(self) -> Dict[str, Any]:
        # Assign roles
        if self.player_roles_config is None:
            self.player_roles = self._assign_random_roles()
        else:
            if len(self.player_roles_config) != 2:
                raise ValueError("player_roles must contain exactly 2 role names")
            self.player_roles = self._assign_specific_roles(self.player_roles_config)

        # Set deadlines for x_rounds role
        self.player_deadline = {}
        for player_id, role in self.player_roles.items():
            if role.get("name") == "x_rounds":
                self.player_deadline[player_id] = self.max_rounds // 2

        return {
            "current_proposal": {"amount": None, "proposer": None},
            "negotiation_history": [],
            "player_proposal_history": {0: [], 1: []},
            "final_amounts": {0: 0.0, 1: 0.0}
        }

    def _assign_random_roles(self) -> Dict[int, Dict]:
        """Randomly assign 2 different roles"""
        selected_roles = self.rng.sample(list(self.available_roles.keys()), 2)
        return {
            0: self.available_roles[selected_roles[0]],
            1: self.available_roles[selected_roles[1]]
        }

    def _assign_specific_roles(self, role_names: List[str]) -> Dict[int, Dict]:
        """Assign specific roles by name"""
        player_roles = {}
        for i, role_name in enumerate(role_names):
            if role_name not in self.available_roles:
                raise ValueError(f"Unknown role: {role_name}. Available roles: {list(self.available_roles.keys())}")
            player_roles[i] = self.available_roles[role_name]
        return player_roles

    def prompt(self, player_id: int) -> str:
        """Generate initial prompt for a player."""
        role = self.player_roles[player_id]

        prompt = f"""TWO DOLLAR NEGOTIATION GAME

You are Player {player_id} negotiating with another player over how to split ${self.total_amount:.2f} total.
There are {self.max_rounds} maximum rounds.

GAME RULES:
- You must reach an agreement on how to split the ${self.total_amount:.2f}
- If no agreement is reached, both players get $0.00
- You have secret instructions that only you can see (below)

REQUIRED ACTION FORMAT:
Write your reasoning/persuasion first, then finish your message with your
decision on its own line (exactly one decision per turn).

Available actions:
- Make a proposal: "Propose $X.XX" (the amount you want for yourself)
- Accept current proposal: "Accept"
- Reject current proposal: "Reject"

Example:
I think this is fair because we both contributed equally.
Propose $1.00

"""

        prompt += f"\n=== YOUR SECRET INSTRUCTIONS ===\n"
        prompt += f"{role['instructions']}\n"
        prompt += f"\nVICTORY CONDITION: {role['victory_condition']}\n"
        prompt += f"FAILURE CONDITION: {role['failure_condition']}\n"

        # Add deadline info for x_rounds role
        if role.get("name") == "x_rounds":
            deadline = self.player_deadline.get(player_id, self.max_rounds // 2)
            prompt = prompt.replace("{deadline}", str(deadline))
            prompt = prompt.replace("{total_rounds}", str(self.max_rounds))

        return prompt

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # the env emits its own "Your action: ..." echo in apply

    def render(self, player_id: int) -> str:
        """Round header + current proposal shown to the player about to act."""
        board = f"=== ROUND {self.state.turn + 1} of {self.max_rounds} ===\n"
        if self.current_proposal["amount"] is not None:
            proposer_id = self.current_proposal["proposer"]
            amount = self.current_proposal["amount"]
            other_amount = self.total_amount - amount
            board += f"\nCURRENT PROPOSAL:\n"
            board += f"Player {proposer_id} wants ${amount:.2f}, Player {1 - proposer_id} gets ${other_amount:.2f}\n"
        return board

    # -- command detection: bare own-line phrase or legacy bracketed token --
    def _has_accept(self, action: str) -> bool:
        return any(command["type"] == "accept" for command in self._find_commands(action))

    def _has_reject(self, action: str) -> bool:
        return any(command["type"] == "reject" for command in self._find_commands(action))

    def _has_propose(self, action: str) -> bool:
        return any(command["type"] == "propose" for command in self._find_commands(action))

    def _text_before_command(self, action: str, legacy_token: str, bare_re: re.Pattern) -> str:
        """Free-text rationale: everything before the command token/line."""
        commands = self._find_commands(action)
        return action[:commands[0]["start"]].strip() if commands else action.strip()

    def _find_commands(self, action: str) -> List[Dict[str, Any]]:
        """Find every real decision command, preserving duplicates for validation."""
        commands: List[Dict[str, Any]] = []
        occupied = []

        for command_type, pattern in (
            ("accept", self._BARE_ACCEPT_RE),
            ("reject", self._BARE_REJECT_RE),
        ):
            for match in pattern.finditer(action):
                commands.append({"type": command_type, "amount": None, "start": match.start(), "end": match.end()})
                occupied.append(match.span())

        for match in self._BARE_PROPOSE_RE.finditer(action):
            amount_match = self._PROPOSE_AMOUNT_RE.fullmatch(match.group("rest"))
            amount = float(amount_match.group(1)) if amount_match else None
            commands.append({"type": "propose", "amount": amount, "start": match.start(), "end": match.end()})
            occupied.append(match.span())

        for match in self._LEGACY_COMMAND_RE.finditer(action):
            if any(match.start() >= start and match.end() <= end for start, end in occupied):
                continue
            decision = match.group("decision")
            if decision is not None:
                command_type, amount = decision.lower(), None
            else:
                command_type = "propose"
                amount = float(match.group("proposal") or match.group("inside"))
            commands.append({"type": command_type, "amount": amount, "start": match.start(), "end": match.end()})

        return sorted(commands, key=lambda command: command["start"])

    def _extract_rationale(self, action: str) -> str:
        """Free-text part of the message, before whichever command it carries."""
        if self._has_propose(action):
            return self._text_before_command(action, "[Propose]", self._BARE_PROPOSE_RE)
        if self._has_accept(action):
            return self._text_before_command(action, "[Accept]", self._BARE_ACCEPT_RE)
        if self._has_reject(action):
            return self._text_before_command(action, "[Reject]", self._BARE_REJECT_RE)
        return action.strip()

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process a player's action."""
        valid, reason = self._validate_action(player_id, action)
        if not valid:
            return self.invalid(reason)

        # Log only validated raw actions to their author (the engine raw-echo is suppressed).
        self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        self._process_valid_action(player_id, action)

        # Check for game end conditions
        if self._check_deal_accepted() or self.state.turn >= self.max_rounds - 1:
            return self._end_game()
        return None

    def _validate_action(self, player_id: int, action: str) -> Tuple[bool, Optional[str]]:
        """Check if an action is valid; return (valid, reason)."""
        action = action.strip()

        commands = self._find_commands(action)
        action_count = len(commands)

        if action_count == 0:
            return False, "Invalid action. Finish your message with your decision on its own line: 'Propose $X.XX', 'Accept', or 'Reject'"
        elif action_count > 1:
            return False, "Multiple actions detected. Use only one action per turn: 'Propose $X.XX', 'Accept', or 'Reject'"
        if action[commands[0]["end"]:].strip():
            return False, "The decision command must be the final non-empty part of the message."

        has_propose = commands[0]["type"] == "propose"
        has_accept = commands[0]["type"] == "accept"
        has_reject = commands[0]["type"] == "reject"

        # Validate proposal format
        if has_propose:
            if not self._is_valid_proposal(action):
                amount = self._extract_proposal_amount(action)
                if amount is None:
                    return False, "Invalid proposal format. Use: 'Propose $X.XX' where X.XX is a valid dollar amount"
                elif amount < 0 or amount > self.total_amount:
                    return False, f"Invalid amount ${amount:.2f}. Must be between $0.00 and ${self.total_amount:.2f}"
                else:
                    return False, "Invalid proposal format"

        # Validate accept/reject actions require a current proposal
        if has_accept or has_reject:
            if self.current_proposal["amount"] is None:
                action_type = "accept" if has_accept else "reject"
                return False, f"No current proposal to {action_type}"

            # Players cannot accept/reject their own proposals
            if self.current_proposal["proposer"] == player_id:
                action_type = "accept" if has_accept else "reject"
                return False, f"You cannot {action_type} your own proposal"

        # Role-specific validation
        valid, error_msg = self._validate_role_specific_action(player_id, action)
        if not valid:
            return False, error_msg

        return True, None

    def _is_valid_proposal(self, action: str) -> bool:
        """Check if a proposal has valid format and amount."""
        try:
            amount = self._extract_proposal_amount(action)
            if amount is None:
                return False
            if amount < 0 or amount > self.total_amount:
                return False
            return True
        except Exception:
            return False

    def _extract_proposal_amount(self, action: str) -> Optional[float]:
        """Extract dollar amount from proposal action (bare or legacy form)."""
        proposals = [command for command in self._find_commands(action) if command["type"] == "propose"]
        return proposals[0]["amount"] if len(proposals) == 1 else None

    def _validate_role_specific_action(self, player_id: int, action: str) -> Tuple[bool, Optional[str]]:
        """Validate action against player's role requirements"""
        role = self.player_roles[player_id]

        if role.get("enforcement") == "action_validation":
            if role["name"] == "say_little":
                # Count words in the free-text part before the command
                message_part = self._extract_rationale(action)
                word_count = len(message_part.split())
                if word_count > role["behavioral_rules"]["max_words_per_message"]:
                    return False, role["behavioral_rules"]["violation_message"].format(word_count=word_count)

            elif role["name"] == "high_tension" and self._has_propose(action):
                # Check concession size against own previous proposals
                amount = self._extract_proposal_amount(action)
                proposals = self.player_proposal_history[player_id]

                if proposals and amount is not None and amount < proposals[-1]:  # Making concession
                    concession = proposals[-1] - amount
                    max_concession = role["behavioral_rules"]["max_concession"]
                    if concession > max_concession:
                        return False, role["behavioral_rules"]["violation_message"].format(concession=concession)

        return True, None

    def _process_valid_action(self, player_id: int, action: str):
        """Process a valid action."""
        action = action.strip()

        if self._has_propose(action):
            self._process_proposal(player_id, action)
        elif self._has_accept(action):
            self._process_accept(player_id, action)
        elif self._has_reject(action):
            self._process_reject(player_id, action)

    def _process_proposal(self, player_id: int, action: str):
        """Process a deal proposal."""
        rationale = self._text_before_command(action, "[Propose]", self._BARE_PROPOSE_RE)
        amount = self._extract_proposal_amount(action)

        if amount is None:
            return  # Should not happen due to validation

        self.game_state["current_proposal"] = {"amount": amount, "proposer": player_id}
        self._record_action(player_id, "propose", amount, rationale)

        other_amount = self.total_amount - amount
        message = f"Player {player_id} proposes: ${amount:.2f} for themselves, ${other_amount:.2f} for their opponent"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_accept(self, player_id: int, action: str):
        """Process an accept action."""
        rationale = self._text_before_command(action, "[Accept]", self._BARE_ACCEPT_RE)
        self._record_action(player_id, "accept", self.current_proposal["amount"], rationale)

        message = f"Player {player_id} accepts the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_reject(self, player_id: int, action: str):
        """Process a reject action."""
        rationale = self._text_before_command(action, "[Reject]", self._BARE_REJECT_RE)
        self._record_action(player_id, "reject", None, rationale)

        message = f"Player {player_id} rejects the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"

        # Reset the proposal amount to none
        self.current_proposal["amount"] = None
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _record_action(self, player_id: int, action_type: str, amount: Optional[float] = None, message: str = ""):
        """Record all actions for analysis"""
        self.negotiation_history.append({
            "player_id": player_id,
            "action_type": action_type,
            "amount": amount,
            "message": message,
            "round": self.state.turn
        })

        # Track proposals separately for easy access
        if action_type == "propose" and amount is not None:
            self.player_proposal_history[player_id].append(amount)

    def _check_deal_accepted(self) -> bool:
        """Check if the current deal has been accepted."""
        if self.current_proposal["amount"] is None:
            return False

        # Only count as accepted if someone other than the proposer accepted
        if self.negotiation_history:
            last_action = self.negotiation_history[-1]
            if (last_action["action_type"] == "accept" and
                last_action["player_id"] != self.current_proposal["proposer"]):
                return True

        return False

    def _end_game(self) -> ta.Outcome:
        """End the game and determine final amounts."""
        if self._check_deal_accepted():
            return self._finalize_accepted_deal()
        return self._handle_no_deal()

    def _finalize_accepted_deal(self) -> ta.Outcome:
        """Finalize an accepted deal and check role compliance."""
        proposer_id = self.current_proposal["proposer"]
        accepter_id = 1 - proposer_id
        proposer_amount = self.current_proposal["amount"]
        accepter_amount = round(self.total_amount - proposer_amount, 2)

        self.final_amounts[proposer_id] = proposer_amount
        self.final_amounts[accepter_id] = accepter_amount

        # Check role compliance for each player
        for player_id in [0, 1]:
            role = self.player_roles[player_id]
            player_amount = self.final_amounts[player_id]

            if role.get("enforcement") == "end_game_check":
                if role.get("threshold") is not None:
                    threshold = role.get("threshold", 0)
                    if player_amount < threshold:
                        self.final_amounts[player_id] = 0.0  # Failed threshold

                elif role.get("name") == "x_rounds":
                    # Check if they met their deadline
                    deadline = self.player_deadline.get(player_id, self.max_rounds // 2)
                    met_deadline = False
                    for action in self.negotiation_history:
                        if (action["player_id"] == player_id and
                            action["action_type"] == "accept" and
                            action["round"] < deadline):
                            met_deadline = True
                            break

                    if not met_deadline:
                        self.final_amounts[player_id] = 0.0  # Failed deadline

            elif role.get("enforcement") == "action_validation":
                # Already enforced during the game via the error allowance
                pass

        deal_str = f"${self.final_amounts[0]:.2f} for Player 0, ${self.final_amounts[1]:.2f} for Player 1"
        self.broadcast(f"DEAL FINALIZED: {deal_str}", ta.ObservationType.GAME_ADMIN)

        return self._final_outcome()

    def _handle_no_deal(self) -> ta.Outcome:
        """Handle case where no deal was reached."""
        self.game_state["final_amounts"] = {0: 0.0, 1: 0.0}
        self.broadcast("NO DEAL REACHED - Both players receive $0.00", ta.ObservationType.GAME_ADMIN)
        return self._final_outcome()

    def _final_outcome(self) -> ta.Outcome:
        """Build the final Outcome from the final amounts."""
        # Determine winners (players who got more than $0)
        winners = [pid for pid in [0, 1] if self.final_amounts[pid] > 0]

        if len(winners) == 2:
            if self.final_amounts[0] > self.final_amounts[1]:
                return self.winner(0, reason=f"Player 0 received more money (${self.final_amounts[0]:.2f} vs ${self.final_amounts[1]:.2f})")
            elif self.final_amounts[1] > self.final_amounts[0]:
                return self.winner(1, reason=f"Player 1 received more money (${self.final_amounts[1]:.2f} vs ${self.final_amounts[0]:.2f})")
            else:
                return self.draw(reason=f"Both players received equal amounts (${self.final_amounts[0]:.2f} each)")
        elif len(winners) == 1:
            return self.winner(winners[0], reason=f"Player {winners[0]} met their role requirements, Player {1 - winners[0]} failed")
        else:
            return self.draw(reason="Both players failed to meet their role requirements")

    def get_board_str(self) -> str:
        """
        Return the main board string:
        - Ongoing: current state (proposals + history)
        - Done: negotiation summary (and results)
        """
        if getattr(self.state, "done", False):
            summary = render_negotiation_summary(
                negotiation_history=self.negotiation_history,
                player_proposal_history=self.player_proposal_history,
                total_amount=self.total_amount,
            )
            results = render_final_results(
                final_amounts=self.final_amounts,
                player_roles=self.player_roles,
                total_amount=self.total_amount,
            )
            return f"{summary}\n\n{results}"

        return render_game_state(
            current_proposal=self.current_proposal,
            total_amount=self.total_amount,
            negotiation_history=self.negotiation_history,
            max_history_items=5,
        )
