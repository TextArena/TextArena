import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.NewRecruit.renderer import create_board_str


class NewRecruitEnv(ta.GameEnv):
    """
    New Recruit is a 2-player, turn-based negotiation game where players take on the roles of a recruiter and a candidate.
    Each player has preferences regarding 8 issues, with 5 choices per issue and different point values for each choice.
    Players take turns proposing choices for each issue and arguing to convince the other player to accept.
    The game ends when a proposal is accepted or after a maximum number of turns.
    """

    min_players = 2
    max_players = 2

    # Matched against stripped text (the proposal against the last line only), so
    # padded or very long input cannot trigger catastrophic backtracking.
    _DECISION_RE = re.compile(r"(accept|reject)", re.IGNORECASE)
    _PROPOSE_LINE_RE = re.compile(r"propose\s+(?P<letters>[a-e](?:[ \t]*[a-e]){7})", re.IGNORECASE)
    _PROPOSE_WORD_RE = re.compile(r"propose\b", re.IGNORECASE)

    max_turns = ta.Param(10, "The turns in the whole game, counting both players.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Define the point value dictionary as provided in the task
        self.point_value_dict = {
            # distributive
            "Salary": {
                "$60000": [-6000, 0],
                "$58000": [-4500, -1500],
                "$56000": [-3000, -3000],
                "$54000": [-1500, -4500],
                "$52000": [0, -6000]
            },
            "Signing Bonus": {
                "10%": [0, 4000],
                "8%": [1000, 3000],
                "6%": [2000, 2000],
                "4%": [3000, 1000],
                "2%": [4000, 0]
            },
            # compatible
            "Job Assignment": {
                "Division A": [0, 0],
                "Division B": [-600, -600],
                "Division C": [-1200, -1200],
                "Division D": [-1800, -1800],
                "Division E": [-2400, -2400]
            },
            "Company Car": {
                "LUX EX2": [1200, 1200],
                "MOD 250": [900, 900],
                "RAND XTR": [600, 600],
                "DE PAS 450": [300, 300],
                "PALO LSR": [0, 0]
            },
            # integrative
            "Starting Date": {
                "Jun 1": [1600, 0],
                "Jun 15": [1200, 1000],
                "Jul 1": [800, 2000],
                "Jul 15": [400, 3000],
                "Aug 1": [0, 4000]
            },
            "Vacation Days": {
                "30 days": [0, 1600],
                "25 days": [1000, 1200],
                "20 days": [2000, 800],
                "15 days": [3000, 400],
                "10 days": [4000, 0]
            },
            "Moving Expense Reimbursement": {
                "100%": [0, 3200],
                "90%": [200, 2400],
                "80%": [400, 1600],
                "70%": [600, 800],
                "60%": [800, 0]
            },
            "Insurance Coverage": {
                "Allen Insurance": [0, 800],
                "ABC Insurance": [800, 600],
                "Good Health Insurance": [1600, 400],
                "Best Insurance Co.": [2400, 200],
                "Insure Alba": [3200, 0]
            },
        }

        # Define issue categories for reference
        self.issue_categories = {
            "distributive": ["Salary", "Signing Bonus"],
            "compatible": ["Job Assignment", "Company Car"],
            "integrative": ["Starting Date", "Vacation Days", "Moving Expense Reimbursement", "Insurance Coverage"]
        }

        # List of all issues
        self.issues = list(self.point_value_dict.keys())

        # Create letter-to-choice mappings for multiple choice format
        self.choice_letters = {}
        letters = ['A', 'B', 'C', 'D', 'E']
        for issue in self.issues:
            self.choice_letters[issue] = {}
            choices = list(self.point_value_dict[issue].keys())
            for i, choice in enumerate(choices):
                if i < len(letters):
                    self.choice_letters[issue][letters[i]] = choice

        # Create reverse mapping (choice-to-letter) for display purposes
        self.letter_choices = {}
        for issue in self.issues:
            self.letter_choices[issue] = {}
            for letter, choice in self.choice_letters[issue].items():
                self.letter_choices[issue][choice] = letter

    def get_board_str(self):
        return self.render(self.state.current_player_id)

    def render(self, player_id: int) -> str:
        return create_board_str(
            game_state=self.game_state, player_id=player_id, issues=self.issues,
            point_value_dict=self.point_value_dict, letter_choices=self.letter_choices,
            turn=min(self.state.turn + 1, self.max_turns), max_turns=self.max_turns,
        )

    def setup(self) -> Dict[str, Any]:
        return {
            "roles": {0: "Recruiter", 1: "Candidate"},
            "current_proposal": None,
            "accepted_proposal": None,
            "current_rationale": None,
            "proposal_history": [],
            "player_preferences": {
                0: {issue: {choice: self.point_value_dict[issue][choice][0] for choice in self.point_value_dict[issue]} for issue in self.issues},
                1: {issue: {choice: self.point_value_dict[issue][choice][1] for choice in self.point_value_dict[issue]} for issue in self.issues}
            }
        }

    def roles(self) -> Dict[int, str]:
        return {0: "Recruiter", 1: "Candidate"}

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        role = game_state["roles"][player_id]
        opponent_role = game_state["roles"][1 - player_id]

        # Create a string representation of the player's preferences with letter choices
        preferences_str = ""
        for issue in self.issues:
            preferences_str += f"\n{issue}:\n"
            choices = list(self.point_value_dict[issue].keys())
            for i, choice in enumerate(choices):
                if i < len(self.choice_letters[issue]):
                    letter = list(self.choice_letters[issue].keys())[i]
                    points = self.point_value_dict[issue][choice][player_id]
                    preferences_str += f"  {letter}. {choice}: {points} points\n"

        # Create a string representation of the issue order
        issue_order_str = "\n".join([f"{i+1}. {issue}" for i, issue in enumerate(self.issues)])

        prompt = (
            f"You are the {role} in the New Recruit negotiation game.\n\n"
            f"Your preferences for each issue are as follows (higher points are better):{preferences_str}\n"
            f"You are negotiating with the {opponent_role}. You can only see your own preferences, not theirs.\n\n"
            "The issues are in this order:\n"
            f"{issue_order_str}\n\n"
            "Available actions:\n"
            f"  - Write your rationale to convince {opponent_role}, followed by a proposal using letter choices on the last line:\n"
            f"    You may say anything (truths, lies, all in between) to persuade {opponent_role} to accept the proposal.\n"
            "    Example format:\n"
            "    ```\n"
            "    I believe this proposal is fair because it balances our interests.\n"
            "    Propose CCAACCCC\n"
            "    ```\n"
            "    Where each letter corresponds to a choice for each issue in the order listed above.\n"
            "    You must always propose one letter A-E for each issue, 8 letters in total. A new proposal replaces the one on the table.\n"
            "  - Reply with exactly 'Accept' to accept the proposal you received; this ends the game.\n"
            "  - Reply with exactly 'Reject' to reject the proposal you received.\n\n"
            "Scoring: when a proposal is accepted, each player scores it with their own point table, and the player "
            "with the higher total wins (equal totals are a draw).\n"
            f"If no proposal is accepted within {self.max_turns} turns (counting both players' turns), the game ends in a draw."
        )
        return prompt

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        game_state = self.game_state
        text = action.strip()

        decision = self._DECISION_RE.fullmatch(text)
        if decision:
            verb = decision.group(1).lower()
            if not game_state["current_proposal"]:
                return self.invalid(f"There is no proposal to {verb}. Make one with 'Propose' followed by 8 letters (A-E).")
            if game_state["current_proposal"]["proposer_id"] == player_id:
                return self.invalid(f"You cannot {verb} your own proposal.")
            if verb == "accept":
                return self._accept_proposal(player_id)
            self._reject_proposal(player_id)
            return None

        # Otherwise the last line must be the proposal; everything before it is the rationale.
        lines = text.splitlines()
        proposal_match = self._PROPOSE_LINE_RE.fullmatch(lines[-1].strip()) if lines else None
        if not proposal_match:
            return self.invalid(
                "Invalid action. Please submit 'Propose' followed by 8 letters (A-E), "
                "or reply with 'Accept'/'Reject' when there's a current proposal."
            )

        rationale_lines = lines[:-1]
        rationale_text = "\n".join(rationale_lines).strip()
        if any(
            self._DECISION_RE.fullmatch(line.strip()) or self._PROPOSE_WORD_RE.match(line.strip())
            for line in rationale_lines
        ):
            return self.invalid("Submit exactly one decision or proposal command per action.")

        # Extract sequence and clean a bit
        raw_sequence = proposal_match.group("letters")
        letter_sequence = re.sub(r'[^A-Ea-e]', '', raw_sequence).upper()
        parsed_proposal = self._parse_letter_sequence(letter_sequence)
        if not parsed_proposal:
            return self.invalid(
                "Invalid proposal format. Please use 'Propose ABCDEABC', where each letter (A-E) "
                "corresponds to a choice for each issue."
            )

        game_state["current_rationale"] = rationale_text if rationale_text else None

        # Create the proposal
        game_state["current_proposal"] = {"proposer_id": player_id, "choices": parsed_proposal}

        # Add to proposal history
        proposal_entry = {"proposer_id": player_id, "choices": parsed_proposal, "accepted": False}
        if game_state["current_rationale"]:
            proposal_entry["rationale"] = game_state["current_rationale"]
        game_state["proposal_history"].append(proposal_entry)

        self.broadcast(f"Player {player_id} ({game_state['roles'][player_id]}) made a new proposal.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.draw(reason="Maximum number of turns reached without an accepted proposal.")

    def _accept_proposal(self, player_id: int) -> ta.Outcome:
        """Accept the current proposal and end the game."""
        game_state = self.game_state
        current_proposal = game_state["current_proposal"]

        # Mark the proposal as accepted
        for i in range(len(game_state["proposal_history"]) - 1, -1, -1):
            proposal = game_state["proposal_history"][i]
            if (proposal["proposer_id"] == current_proposal["proposer_id"] and
                    proposal["choices"] == current_proposal["choices"]):
                game_state["proposal_history"][i]["accepted"] = True
                break

        game_state["accepted_proposal"] = current_proposal

        # Calculate scores
        recruiter_score = self._calculate_score(0, current_proposal["choices"])
        candidate_score = self._calculate_score(1, current_proposal["choices"])

        self.broadcast(f"Player {player_id} ({game_state['roles'][player_id]}) accepted the proposal.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if recruiter_score > candidate_score:
            return self.winner(0, reason=f"Recruiter wins with {recruiter_score} points vs Candidate's {candidate_score} points.")
        elif candidate_score > recruiter_score:
            return self.winner(1, reason=f"Candidate wins with {candidate_score} points vs Recruiter's {recruiter_score} points.")
        return self.draw(reason=f"Draw with both players scoring {recruiter_score} points.")

    def _reject_proposal(self, player_id: int):
        """Reject the current proposal and continue the game."""
        self.broadcast(f"Player {player_id} ({self.game_state['roles'][player_id]}) rejected the proposal.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.game_state["current_proposal"] = None
        self.game_state["current_rationale"] = None

    def _calculate_score(self, player_id: int, proposal: Dict[str, str]) -> int:
        return sum(self.point_value_dict[issue][choice][player_id] for issue, choice in proposal.items())

    def _parse_letter_sequence(self, letter_sequence: str) -> Optional[Dict[str, str]]:
        """Parse a letter sequence (e.g. "ABCDEDCA") into a dict mapping issues to choices, or None if invalid."""
        if len(letter_sequence) != len(self.issues):
            return None
        proposal = {}
        for i, issue in enumerate(self.issues):
            letter = letter_sequence[i].upper()
            if letter not in self.choice_letters[issue]:
                return None
            proposal[issue] = self.choice_letters[issue][letter]
        return proposal
