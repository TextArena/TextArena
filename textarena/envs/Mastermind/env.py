import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Mastermind.renderer import create_board_str


class MastermindEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_code_length = 256
    max_number_options = 1_000_000
    max_action_chars = 4096

    def __init__(self, code_length: Optional[int] = 4, num_numbers: Optional[int] = 6, max_turns: Optional[int] = 20, duplicate_numbers: Optional[bool] = False):
        """
        Args:
            code_length (int): the number of options to get right
            max_turns (int): the number of turns until draw
            duplicate_numbers (bool): whether numbers can be duplicates
        """
        if (
            not isinstance(code_length, int)
            or isinstance(code_length, bool)
            or not 1 <= code_length <= self.max_code_length
        ):
            raise ValueError(
                f"code_length must be between 1 and {self.max_code_length}"
            )
        if (
            not isinstance(num_numbers, int)
            or isinstance(num_numbers, bool)
            or not 1 <= num_numbers <= self.max_number_options
        ):
            raise ValueError(
                f"num_numbers must be between 1 and {self.max_number_options}"
            )
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        if not isinstance(duplicate_numbers, bool):
            raise ValueError("duplicate_numbers must be a boolean")
        if not duplicate_numbers and code_length > num_numbers:
            raise ValueError(
                "code_length cannot exceed num_numbers when duplicates are disabled"
            )
        self.max_turns = max_turns
        self.code_length = code_length
        self.num_numbers = num_numbers
        self.duplicate_numbers = duplicate_numbers

    def get_board_str(self):
        return create_board_str(
            game_state=self.state.game_state,
            reveal_secret=self.state.done,
        )

    def render(self, player_id: int) -> str:
        return self.get_board_str()

    def setup(self) -> Dict[str, Any]:
        sample_fn = self.rng.choices if self.duplicate_numbers else self.rng.sample
        code = sample_fn(range(1, self.num_numbers + 1), k=self.code_length)
        return {"secret_code": code, "guess": [], "code_length": self.code_length, "num_numbers": self.num_numbers, "duplicate_numbers": self.duplicate_numbers, "history": []}

    def prompt(self, player_id: int) -> str:
        example = " ".join(str(i % self.num_numbers + 1) for i in range(self.code_length))
        repeats = (
            "Numbers may repeat, in the code and in your guesses."
            if self.duplicate_numbers
            else "All numbers in the code are different, and your guesses may not repeat a number either."
        )
        return (
            f"You are playing Mastermind.\n"
            f"You need to find the secret code: {self.code_length} numbers, each from 1 to {self.num_numbers}. {repeats}\n"
            f"Submit your guess as {self.code_length} space-separated numbers, e.g. '{example}'.\n"
            "After each guess, you will receive feedback in the form of black and white pegs.\n"
            "A black peg indicates a correct number in the correct position, while a white peg indicates a correct number in the wrong position.\n"
            "In the guess history, 🎯 is a black peg, ⚪ is a white peg, and ▫️ is an empty slot.\n"
            f"You have {self.max_turns} guesses to crack the code.\n"
            "Repeating an earlier guess or submitting the wrong count or range of numbers is an invalid move. "
            "It changes nothing and you may try again, but two invalid moves in a row end the game."
        )

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        match = re.fullmatch(r"\d+(?:(?:\s*,\s*|\s+)\d+)*", action_text)
        if match is None:
            return self.invalid("You did not respond with a space-separated list of numbers, e.g. '1 2 3 4'.")

        player_guess = list(map(int, re.split(r"[,\s]+", match.group(0))))

        if len(player_guess) != self.game_state["code_length"]:
            return self.invalid(f"The guess should contain exactly {self.game_state['code_length']} numbers.")

        if any(num < 1 or num > self.game_state["num_numbers"] for num in player_guess):
            return self.invalid(f"All numbers must be between 1 and {self.game_state['num_numbers']}.")

        if not self.game_state["duplicate_numbers"] and len(set(player_guess)) != len(player_guess):
            return self.invalid("Duplicate numbers are not allowed.")

        previous_guesses = [entry["guess"] for entry in self.game_state["history"]]
        if player_guess in previous_guesses:
            return self.invalid(f"You have already guessed {player_guess}. Please try a different guess.")

        black_pegs, white_pegs = self._evaluate_guess(player_guess)
        self.game_state["history"].append({"guess": player_guess, "black": black_pegs, "white": white_pegs})

        if black_pegs == self.game_state["code_length"]:
            return self.outcome({0: 1}, reason=f"You have cracked the code, solving {black_pegs} out of {self.game_state['code_length']} pegs correctly")
        self.broadcast(f"Submitted '{' '.join(map(str, player_guess))}'. Feedback: {black_pegs} black peg(s), {white_pegs} white peg(s).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_completion = self._get_percentage_completion()
        return self.outcome({0: pct_completion}, reason=f"Turn limit reached. You guessed {pct_completion*100:.2f} percent of the numbers correctly.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _evaluate_guess(self, player_guess: List[int]) -> Tuple[int, int]:
        black_pegs, white_pegs = 0, 0
        secret_copy = self.game_state["secret_code"].copy()
        guess_copy = player_guess.copy()
        # First pass: count black pegs and mark them as None
        for i in range(self.game_state["code_length"]):
            if guess_copy[i] == secret_copy[i]:
                black_pegs += 1
                secret_copy[i] = None
                guess_copy[i] = None
        # Second pass: count white pegs using the remaining numbers
        for i in range(self.game_state["code_length"]):
            if guess_copy[i] is not None and guess_copy[i] in secret_copy:
                white_pegs += 1
                secret_copy[secret_copy.index(guess_copy[i])] = None  # Remove the first occurrence to prevent over-counting
        return black_pegs, white_pegs

    def _get_percentage_completion(self) -> float:
        """ Calculate a percentage completion score based on the player's latest performance """
        if not self.game_state["history"]: return 0.0
        latest_entry = self.game_state["history"][-1]
        return ((latest_entry["black"] * 1.0) + (latest_entry["white"] * 0.5)) / self.game_state["code_length"]
