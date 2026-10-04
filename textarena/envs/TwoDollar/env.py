"""
Two Dollar Negotiation Game Environment

A classic negotiation exercise where two players must agree on how to split $2.00.
Each player has secret role instructions that may include minimum thresholds,
behavioral constraints, or strategic guidelines.

Based on the original Two Dollar game used in negotiation research and education.
"""

import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.TwoDollar.renderer import render_game_state, render_negotiation_summary, render_final_results


class TwoDollarEnv(ta.GameEnv):
    """
    Two-player negotiation environment where players split a fixed amount of money.
    Players have secret role instructions that create different constraints and objectives.

    Money is tracked in integer cents; the dollar-valued properties are views for
    renderers and callers.
    """

    min_players = 2
    max_players = 2

    # Decision grammar (what the prompts teach): every message ends with
    # exactly one decision line whose first token is exactly the command
    # keyword, case-insensitive, followed by its arguments; trailing "." or
    # "!" is tolerated. A "propose" line whose remainder is empty or starts
    # with "$" or a digit is a proposal attempt and must be well-formed. Every
    # other line, such as "Proposed split: ..." or "Propose we split it", is
    # persuasion text.
    _ACCEPT_LINE_RE = re.compile(r"accept\s*[.!]*", re.IGNORECASE)
    _REJECT_LINE_RE = re.compile(r"reject\s*[.!]*", re.IGNORECASE)
    _PROPOSE_LINE_RE = re.compile(r"propose(?![^\s:.!])\s*:?\s*(?P<args>.*)", re.IGNORECASE)
    _AMOUNT_RE = re.compile(r"\$(?P<dollars>[0-9]+)(?:\.(?P<cents>[0-9]{1,2}))?")

    player_roles = ta.Param(
        None,
        'Two role names, such as `["vanilla", "50_cents"]`, for Players 0 and 1. `None` draws two different roles at '
        "random. Requesting `x_rounds` with `max_rounds` below 4 raises a `ValueError`.",
        type=list, check=lambda roles: len(roles) == 2 and all(isinstance(role, str) for role in roles),
        rule="a list of two role names",
    )
    total_amount = ta.Param(
        2.00, "The amount to split.", check=lambda amount: amount > 0 and round(amount, 2) == amount,
        rule="a positive amount with at most two decimal places",
    )
    max_rounds = ta.Param(
        20, "The number of messages, counting both players, before the game ends without a deal. It also sets the "
            "`x_rounds` deadline to `max_rounds // 2`.", min=1,
    )
    error_allowance = ta.Param(
        3, "The number of consecutive invalid moves a player is warned about before the next one forfeits the game.",
        min=0,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.total_cents = round(self.total_amount * 100)

        # Load all available roles
        self.available_roles = self._load_available_roles()
        for role_name in self.player_roles or []:
            self._check_role_feasible(role_name)

        # Assigned per reset
        self.assigned_roles = {}
        self.player_deadline = {}  # For x_rounds role

    # -- dollar views of the cent-valued game_state (for renderers/analysis) --
    @property
    def current_proposal(self) -> Dict[str, Any]:
        proposal = self.game_state["current_proposal"]
        return {"amount": self._dollars(proposal["amount_cents"]), "proposer": proposal["proposer"]}

    @property
    def negotiation_history(self) -> List[Dict[str, Any]]:
        return self.game_state["negotiation_history"]

    @property
    def player_proposal_history(self) -> Dict[int, List[float]]:
        return {
            pid: [self._dollars(cents) for cents in proposals]
            for pid, proposals in self.game_state["player_proposal_history"].items()
        }

    @property
    def final_amounts(self) -> Dict[int, float]:
        return {pid: self._dollars(cents) for pid, cents in self.game_state["final_cents"].items()}

    @staticmethod
    def _dollars(cents: Optional[int]) -> Optional[float]:
        return None if cents is None else cents / 100

    @staticmethod
    def _format_cents(cents: int) -> str:
        return f"${cents // 100}.{cents % 100:02d}"

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
        if self.player_roles is None:
            self.assigned_roles = self._assign_random_roles()
        else:
            self.assigned_roles = self._assign_specific_roles(self.player_roles)

        # Set deadlines for x_rounds role
        self.player_deadline = {}
        for player_id, role in self.assigned_roles.items():
            if role.get("name") == "x_rounds":
                self.player_deadline[player_id] = self.max_rounds // 2

        return {
            "current_proposal": {"amount_cents": None, "proposer": None},
            "negotiation_history": [],
            "player_proposal_history": {0: [], 1: []},
            "final_cents": {0: 0, 1: 0},
        }

    @staticmethod
    def _x_rounds_feasible(max_rounds: int) -> bool:
        """Whether the x_rounds deadline (max_rounds // 2 turns) leaves room for a
        proposal in round 1 and an acceptance in round 2."""
        return max_rounds // 2 >= 2

    def _check_role_feasible(self, role_name: str):
        if role_name == "x_rounds" and not self._x_rounds_feasible(self.max_rounds):
            raise ValueError(
                f"Role 'x_rounds' needs max_rounds >= 4 (got {self.max_rounds}): its deadline is "
                f"max_rounds // 2 = {self.max_rounds // 2} rounds, and the earliest possible "
                "deal is accepted in round 2"
            )

    def _assign_random_roles(self) -> Dict[int, Dict]:
        """Randomly assign 2 different roles that can be satisfied under max_rounds"""
        pool = list(self.available_roles.keys())
        if not self._x_rounds_feasible(self.max_rounds):
            pool.remove("x_rounds")
        selected_roles = self.rng.sample(pool, 2)
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
            self._check_role_feasible(role_name)
            player_roles[i] = self.available_roles[role_name]
        return player_roles

    def prompt(self, player_id: int) -> str:
        """Generate initial prompt for a player."""
        role = self.assigned_roles[player_id]

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
        prompt = prompt.replace("{forfeit_after}", str(self.error_allowance + 1))

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
        proposal = self.game_state["current_proposal"]
        if proposal["amount_cents"] is not None:
            proposer_id = proposal["proposer"]
            amount = proposal["amount_cents"]
            board += f"\nCURRENT PROPOSAL:\n"
            board += (
                f"Player {proposer_id} wants {self._format_cents(amount)}, "
                f"Player {1 - proposer_id} gets {self._format_cents(self.total_cents - amount)}\n"
            )
        return board

    # -- command detection: own-line decisions --
    def _classify_line(self, line: str) -> Optional[Tuple[str, str]]:
        """('accept'|'reject', '') or ('propose', arguments) if a stripped line is a decision."""
        if self._ACCEPT_LINE_RE.fullmatch(line):
            return "accept", ""
        if self._REJECT_LINE_RE.fullmatch(line):
            return "reject", ""
        match = self._PROPOSE_LINE_RE.fullmatch(line)
        if match is not None:
            args = match.group("args").rstrip(" \t.!")
            if not args or args[0] in "$0123456789":
                return "propose", args
        return None

    def _find_decisions(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Every decision line in the message: kind, arguments, and line index."""
        decisions = []
        for index, line in enumerate(lines):
            classified = self._classify_line(line.strip())
            if classified is not None:
                kind, args = classified
                decisions.append({"kind": kind, "args": args, "line": index})
        return decisions

    def _parse_amount(self, args: str) -> Tuple[Optional[int], Optional[str]]:
        """'$X.XX' -> (cents, None), or (None, reason) if malformed or out of range."""
        match = self._AMOUNT_RE.fullmatch(args)
        if match is None:
            return None, "Invalid proposal format. Use: 'Propose $X.XX' where X.XX is a valid dollar amount"
        dollars = match.group("dollars").lstrip("0") or "0"
        cents = (match.group("cents") or "").ljust(2, "0")
        # More dollar digits than the total has cent digits is always out of
        # range; checking first keeps int() off arbitrarily long digit strings.
        fits = len(dollars) <= len(str(self.total_cents))
        amount_cents = int(dollars) * 100 + int(cents) if fits else None
        if amount_cents is None or amount_cents > self.total_cents:
            return None, f"Invalid amount {args}. Must be between $0.00 and {self._format_cents(self.total_cents)}"
        return amount_cents, None

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        """Process a player's action."""
        action = self.strip_role_tags(action).strip()
        decision, reason = self._parse_action(player_id, action)
        if reason is not None:
            return self.invalid(reason)

        # Log only validated raw actions to their author (the engine raw-echo is suppressed).
        self.message(player_id, f"Your action: {action}", ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        rationale = decision["before"]
        if decision["kind"] == "propose":
            self._process_proposal(player_id, decision["amount_cents"], rationale)
        elif decision["kind"] == "accept":
            self._process_accept(player_id, rationale)
        else:
            self._process_reject(player_id, rationale)

        # Check for game end conditions
        if self._check_deal_accepted() or self.state.turn >= self.max_rounds - 1:
            return self._end_game()
        return None

    def _parse_action(self, player_id: int, action: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Return (decision, None) for a valid action or (None, reason) for an invalid one."""
        lines = action.split("\n")
        decisions = self._find_decisions(lines)
        if not decisions:
            return None, "Invalid action. Finish your message with your decision on its own line: 'Propose $X.XX', 'Accept', or 'Reject'"
        if len(decisions) > 1:
            return None, "Multiple actions detected. Use only one action per turn: 'Propose $X.XX', 'Accept', or 'Reject'"
        decision = decisions[0]
        if any(rest.strip() for rest in lines[decision["line"] + 1:]):
            return None, "The decision command must be the final non-empty part of the message."
        decision["before"] = "\n".join(lines[:decision["line"]]).strip()

        if decision["kind"] == "propose":
            amount_cents, reason = self._parse_amount(decision["args"])
            if reason is not None:
                return None, reason
            decision["amount_cents"] = amount_cents
        elif self.game_state["current_proposal"]["amount_cents"] is None:
            return None, f"No current proposal to {decision['kind']}"
        elif self.game_state["current_proposal"]["proposer"] == player_id:
            return None, f"You cannot {decision['kind']} your own proposal"

        reason = self._role_violation(player_id, decision)
        if reason is not None:
            return None, reason
        return decision, None

    def _role_violation(self, player_id: int, decision: Dict[str, Any]) -> Optional[str]:
        """Reason the action breaks the player's per-message role rules, if it does."""
        role = self.assigned_roles[player_id]
        if role.get("enforcement") != "action_validation":
            return None
        rules = role["behavioral_rules"]

        if role["name"] == "say_little":
            word_count = len(decision["before"].split())
            if word_count > rules["max_words_per_message"]:
                return rules["violation_message"].format(word_count=word_count)

        elif role["name"] == "high_tension" and decision["kind"] == "propose":
            proposals = self.game_state["player_proposal_history"][player_id]
            if proposals:
                concession = proposals[-1] - decision["amount_cents"]
                if concession > round(rules["max_concession"] * 100):
                    return rules["violation_message"].format(concession=concession / 100)

        return None

    def _process_proposal(self, player_id: int, amount_cents: int, rationale: str):
        """Process a deal proposal."""
        self.game_state["current_proposal"] = {"amount_cents": amount_cents, "proposer": player_id}
        self._record_action(player_id, "propose", amount_cents, rationale)

        message = (
            f"Player {player_id} proposes: {self._format_cents(amount_cents)} for themselves, "
            f"{self._format_cents(self.total_cents - amount_cents)} for their opponent"
        )
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_accept(self, player_id: int, rationale: str):
        """Process an accept action."""
        self._record_action(player_id, "accept", self.game_state["current_proposal"]["amount_cents"], rationale)

        message = f"Player {player_id} accepts the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _process_reject(self, player_id: int, rationale: str):
        """Process a reject action."""
        self._record_action(player_id, "reject", None, rationale)

        message = f"Player {player_id} rejects the proposal"
        if rationale:
            message = f"Player {player_id} says: {rationale}\n{message}"

        self.game_state["current_proposal"] = {"amount_cents": None, "proposer": None}
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _record_action(self, player_id: int, action_type: str, amount_cents: Optional[int] = None, message: str = ""):
        """Record all actions for analysis"""
        self.game_state["negotiation_history"].append({
            "player_id": player_id,
            "action_type": action_type,
            "amount_cents": amount_cents,
            "message": message,
            "round": self.state.turn
        })

        # Track proposals separately for easy access
        if action_type == "propose" and amount_cents is not None:
            self.game_state["player_proposal_history"][player_id].append(amount_cents)

    def _check_deal_accepted(self) -> bool:
        """Check if the current deal has been accepted."""
        proposal = self.game_state["current_proposal"]
        if proposal["amount_cents"] is None:
            return False

        # Only count as accepted if someone other than the proposer accepted
        history = self.game_state["negotiation_history"]
        if history:
            last_action = history[-1]
            if (last_action["action_type"] == "accept" and
                last_action["player_id"] != proposal["proposer"]):
                return True

        return False

    def _end_game(self) -> ta.Outcome:
        """End the game and determine final amounts."""
        if self._check_deal_accepted():
            return self._finalize_accepted_deal()
        return self._handle_no_deal()

    def _finalize_accepted_deal(self) -> ta.Outcome:
        """Finalize an accepted deal and check role compliance."""
        proposal = self.game_state["current_proposal"]
        proposer_id = proposal["proposer"]
        final_cents = {
            proposer_id: proposal["amount_cents"],
            1 - proposer_id: self.total_cents - proposal["amount_cents"],
        }
        accepted_round = self.game_state["negotiation_history"][-1]["round"]

        # Check role compliance for each player
        for player_id in [0, 1]:
            role = self.assigned_roles[player_id]

            if role.get("enforcement") == "end_game_check":
                if role.get("threshold") is not None:
                    if final_cents[player_id] < round(role["threshold"] * 100):
                        final_cents[player_id] = 0  # Failed threshold

                elif role.get("name") == "x_rounds":
                    # The deal counts if it was concluded in time, whoever accepted it.
                    deadline = self.player_deadline.get(player_id, self.max_rounds // 2)
                    if accepted_round >= deadline:
                        final_cents[player_id] = 0  # Failed deadline

            elif role.get("enforcement") == "action_validation":
                # Already enforced during the game via the error allowance
                pass

        self.game_state["final_cents"] = final_cents
        deal_str = (
            f"{self._format_cents(final_cents[0])} for Player 0, "
            f"{self._format_cents(final_cents[1])} for Player 1"
        )
        self.broadcast(f"DEAL FINALIZED: {deal_str}", ta.ObservationType.GAME_ADMIN)

        return self._final_outcome()

    def _handle_no_deal(self) -> ta.Outcome:
        """Handle case where no deal was reached."""
        self.game_state["final_cents"] = {0: 0, 1: 0}
        self.broadcast("NO DEAL REACHED - Both players receive $0.00", ta.ObservationType.GAME_ADMIN)
        return self._final_outcome()

    def _final_outcome(self) -> ta.Outcome:
        """Build the final Outcome from the final amounts."""
        final = self.game_state["final_cents"]
        shares = {pid: self._format_cents(final[pid]) for pid in (0, 1)}
        # Determine winners (players who got more than $0)
        winners = [pid for pid in [0, 1] if final[pid] > 0]

        if len(winners) == 2:
            if final[0] > final[1]:
                return self.winner(0, reason=f"Player 0 received more money ({shares[0]} vs {shares[1]})")
            elif final[1] > final[0]:
                return self.winner(1, reason=f"Player 1 received more money ({shares[1]} vs {shares[0]})")
            else:
                return self.draw(reason=f"Both players received equal amounts ({shares[0]} each)")
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
        history = [
            dict(entry, amount=self._dollars(entry["amount_cents"]))
            for entry in self.negotiation_history
        ]
        if getattr(self.state, "done", False):
            summary = render_negotiation_summary(
                negotiation_history=history,
                player_proposal_history=self.player_proposal_history,
                total_amount=self.total_amount,
            )
            results = render_final_results(
                final_amounts=self.final_amounts,
                player_roles=self.assigned_roles,
                total_amount=self.total_amount,
            )
            return f"{summary}\n\n{results}"

        return render_game_state(
            current_proposal=self.current_proposal,
            total_amount=self.total_amount,
            negotiation_history=history,
            max_history_items=5,
        )
