import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.PigDice.renderer import create_board_str


class PigDiceEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    MAX_WINNING_SCORE = 1_000_000
    action_pattern = (
        r"(?i)^\s*(?P<bracket>\[)?\s*(?P<action>roll|hold)\s*"
        r"(?(bracket)\])\s*$"
    )
    action_format = "either 'roll' to roll the die or 'hold' to bank your turn total"

    def __init__(self, winning_score: int = 100, max_turns: int = 500):
        """
        Args:
            winning_score (int): The score needed to win.
            max_turns (int): Maximum number of turns before the game ends.
        """
        if type(winning_score) is not int or winning_score < 1:
            raise ValueError("winning_score must be a positive integer.")
        if winning_score > self.MAX_WINNING_SCORE:
            raise ValueError(f"winning_score cannot exceed {self.MAX_WINNING_SCORE}.")
        # A cap is required: two players who only hold (or only roll) would otherwise never finish.
        if type(max_turns) is not int or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        self.winning_score = winning_score
        self.max_turns = max_turns
        self.roll_value = None

    def setup(self) -> Dict[str, Any]:
        self.roll_value = None
        return {"scores": [0, 0], "turn_total": 0, "turn_rolls": []}

    def prompt(self, player_id: int) -> str:
        turn_limit_rule = (
            f"\n- After {self.max_turns} completed actions, the player with "
            "the higher banked score wins; equal scores draw"
        )
        return (
            f"You are Player {player_id} playing a game of Pig Dice.\n"
            f"Rules:\n- On your turn, you can either 'roll' or 'hold'\n- Roll a 2-6: Add to your turn total\n"
            f"- Roll a 1: Lose turn total and end turn\n- Hold: Add turn total to your score and end turn\n"
            f"- First to {self.winning_score} points wins{turn_limit_rule}\n\nWhen it's your turn, you'll see the current scores and turn total.\n"
            f"Respond with 'roll' to roll the die or 'hold' to bank your points."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        board = "Current Total Scores: " + "; ".join(f"Player {i}: '{score}'" for i, score in enumerate(gs["scores"]))
        board += f"\nYour current turn total is {gs['turn_total']}. "
        board += f"\nYour roll history for this turn: {', '.join(gs['turn_rolls'])}" if gs["turn_rolls"] else "\nThis is the first roll of your turn."
        board += "\nAvailable actions: 'roll' or 'hold'"
        return board

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        action = move.group("action").lower()
        if action == "roll":
            roll_value = self.rng.randint(1, 6)
            self.roll_value = roll_value
            self.broadcast(
                f"Player {player_id} rolled a {roll_value}.",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            if roll_value == 1:  # bust: lose the turn total, end the turn
                self.broadcast(f"Player {player_id} busted, losing {self.game_state['turn_total']} points!", ta.ObservationType.GAME_MESSAGE)
                return self._end_turn(player_id)
            self.game_state["turn_total"] += roll_value
            self.game_state["turn_rolls"].append(f"'{roll_value}'")
            self.set_next_player(player_id)  # keep rolling
            return None
        else:  # hold
            self.game_state["scores"][player_id] += self.game_state["turn_total"]
            self.broadcast(f"Player {player_id} holds and banks {self.game_state['turn_total']} points.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            return self._end_turn(player_id)

    def _end_turn(self, player_id: int) -> Optional[ta.Outcome]:
        scores = self.game_state["scores"]
        self.game_state["turn_total"] = 0
        self.game_state["turn_rolls"] = []
        self.roll_value = None
        if scores[player_id] >= self.winning_score:
            return self.winner(player_id, reason=f"Player {player_id} won by reaching the target score of {self.winning_score}!")
        self.broadcast("Current Scores: " + "; ".join(f"Player {i}: '{score}'" for i, score in enumerate(scores)), ta.ObservationType.GAME_MESSAGE)
        return None  # default rotation passes the turn to the other player

    def on_turn_limit(self) -> ta.Outcome:
        scores = self.game_state["scores"]
        if scores[0] == scores[1]:
            return self.draw(reason=f"The turn limit has been reached and all players have the same score: {scores}")
        winner_id = 0 if scores[0] > scores[1] else 1
        return self.winner(winner_id, reason=f"Player {winner_id} won by having a higher score at the turn limit ({scores})")

    def get_board_str(self):
        return create_board_str(
            scores=self.game_state["scores"], turn_total=self.game_state["turn_total"],
            current_player=self.state.current_player_id, current_roll=self.roll_value,
            goal=self.winning_score,
        )
