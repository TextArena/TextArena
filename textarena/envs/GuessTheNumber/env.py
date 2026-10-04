import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.GuessTheNumber.renderer import create_board_str


class GuessTheNumberEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    action_pattern = r"^\s*\[?\s*([+-]?\d+)\s*\]?\s*$"

    def __init__(self, min_number: int = 1, max_number: int = 20, max_turns: int = 20):
        """
        Args:
           min_number: The lower bound
           max_number: The upper bound
           max_turns: The number of guesses
        """
        if (
            not isinstance(min_number, int)
            or isinstance(min_number, bool)
            or not isinstance(max_number, int)
            or isinstance(max_number, bool)
        ):
            raise ValueError("min_number and max_number must be integers.")
        if min_number > max_number:
            raise ValueError("min_number must not exceed max_number.")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        self.min_number = min_number
        self.max_number = max_number
        self.max_turns = max_turns

    @property
    def action_format(self) -> str:
        return f"a whole number from {self.min_number} to {self.max_number}, for example '{self.min_number}'"

    def setup(self) -> Dict[str, Any]:
        return {
            "game_number": self.rng.randint(self.min_number, self.max_number),
            "guess_history": [],
            "guessed_numbers": set(),
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id}. You are playing Guess The Number.\n"
            f"You have to guess the number between {self.min_number} and {self.max_number} (inclusive) within {self.max_turns} turns.\n"
            "After each wrong guess, the game tells you whether the target number is higher or lower than your guess and how many guesses you have left.\n"
            f"Reply with the number you want to guess, e.g. '{self.min_number}'. Numbers outside the range and numbers you have already guessed are invalid moves.\n"
            "Use the hints to find the number before you run out of guesses.\n"
            "Enter your guess."
        )

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        try:
            guess = int(move.group(1))
        except ValueError:
            return self.invalid("Invalid move. The submitted integer is too large to parse.")
        if guess < self.min_number or guess > self.max_number:
            return self.invalid(f"Invalid move. Player {player_id} guessed a number outside the range specified.")
        if guess in self.game_state["guessed_numbers"]:
            return self.invalid(f"Invalid move. Player {player_id} has already guessed the number.")

        self.game_state["guessed_numbers"].add(guess)
        if guess == self.game_state["game_number"]:
            self.game_state["guess_history"].append((guess, "correct"))
            return self.outcome({0: 1}, reason="Congratulations! You guessed the correct number.")
        hint = "lower" if guess > self.game_state["game_number"] else "higher"
        guesses_left = self.max_turns - self.state.turn - 1
        self.broadcast(
            f"Your guess {guess} is too {'high' if hint == 'lower' else 'low'}: the target number is {hint}. Guesses left: {guesses_left}.",
            ta.ObservationType.GAME_MESSAGE,
        )
        self.game_state["guess_history"].append((guess, hint))
        return None

    def on_turn_limit(self) -> ta.Outcome:
        last_guess = self.game_state["guess_history"][-1][0] if self.game_state["guess_history"] else None
        return self.outcome(
            {0: self._get_percentage_completion()},
            reason=f"The turn limit has been reached. Guess: {last_guess}, Target: {self.game_state['game_number']}",
        )

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state, reveal_answer=self.state.done)

    def _get_percentage_completion(self) -> float:
        """Reward shaping: how close the last guess was to the target number."""
        if not self.game_state["guess_history"]:
            return 0.0
        last_guess, _ = self.game_state["guess_history"][-1]
        distance = abs(last_guess - self.game_state["game_number"])
        span = self.max_number - self.min_number
        if span == 0:
            return 1.0 if distance == 0 else 0.0
        return max(0.0, 1 - (distance / span))
