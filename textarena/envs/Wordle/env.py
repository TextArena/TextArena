import re
from typing import Optional, List, Dict, Any, Union

import textarena as ta
from textarena.envs.Wordle.renderer import create_board_str
from textarena.utils.word_lists import get_basic_english_words, get_english_words, get_headwords, is_english_word

class WordleEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    action_pattern = r"^([a-zA-Z]+)$"
    snapshot_excluded_attributes = ("word_list",)

    def __init__(self, word_length: int = 5, num_guesses: int = 6, hardcore: Optional[bool] = False):
        """ Initializes the Wordle environment """
        if not isinstance(word_length, int) or isinstance(word_length, bool) or word_length < 1:
            raise ValueError("word_length must be a positive integer.")
        if not isinstance(num_guesses, int) or isinstance(num_guesses, bool) or num_guesses < 1:
            raise ValueError("num_guesses must be a positive integer.")
        if not isinstance(hardcore, bool):
            raise ValueError("hardcore must be a boolean.")
        self.word_length = word_length
        self.num_guesses = num_guesses
        self.max_turns = num_guesses
        self._load_word_list(hardcore=hardcore)

    def _check_word(self, word: str) -> bool:
        return is_english_word(word)

    def _load_word_list(self, hardcore: bool = False) -> None:
        """ Secret words: Basic English, or every dictionary headword in hardcore mode """
        source = get_headwords() if hardcore else get_basic_english_words()
        self.word_list = sorted(word for word in source if len(word) == self.word_length and self._check_word(word))
        if not self.word_list:
            # Lengths the chosen list lacks still get playable secrets from the full dictionary.
            self.word_list = sorted(word for word in get_english_words() if len(word) == self.word_length)
        if not self.word_list:
            raise ValueError(f"No target words are available with length {self.word_length}.")

    def setup(self) -> Dict[str, Any]:
        return {
            "secret_word": self.rng.choice(self.word_list),
            "guess_history": [],
            "word_length": self.word_length,
            "num_guesses": self.num_guesses,
            "rendered_board": "No guesses yet.",
            "player_view": "No guesses yet.",
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Playing Wordle.\nA secret {self.game_state['word_length']}-letter word has been chosen. You have {self.game_state['num_guesses']} attempts to guess it.\n"
            f"For each guess, reply with the word you want to try, e.g. '{self._example_guess()}'.\n"
            f"Every guess must be a {self.game_state['word_length']}-letter English word from the game's dictionary (UK and US spellings are accepted, proper nouns are not), and you cannot repeat a guess.\n"
            "Feedback for each letter will be given as follows:\n"
            "  - G (green): correct letter in the correct position\n"
            "  - Y (yellow): letter exists in the word but in the wrong position\n"
            "  - X (wrong): letter is not in the word\n"
            "Enter your guess to begin.\n"
        )

    def _example_guess(self) -> str:
        examples = {5: "apple", 7: "example"}
        return examples.get(self.word_length, self.word_list[0])

    @property
    def action_format(self) -> str:
        return f"a {self.word_length}-letter English word, for example '{self._example_guess()}'"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        word = move.group(1).lower()
        if len(word) != gs["word_length"]:
            return self.invalid(f"Your word must be exactly {gs['word_length']} letters.")

        previous_words = [guess_word for guess_word, _ in gs["guess_history"]]
        if word in previous_words:
            return self.invalid(f"You have already guessed '{word}' before. Please try a different word.")

        if not self._check_word(word):
            return self.invalid(f"'{word}' is not in the game's English dictionary.")

        feedback = self._evaluate_guess(word) # Evaluate the word
        gs["guess_history"].append((word, feedback)) # Save the guess and feedback

        # Update board views
        gs["rendered_board"] = self._render_board()
        gs["player_view"] = self._render_player_view(player_id)

        # Check for win condition (all letters green)
        if all(f == "G" for f in feedback):
            return self.outcome({0: 1}, reason="Congratulations! You guessed the word correctly!")
        self.broadcast(
            f"You submitted '{word}'.\nFeedback:\n{self._render_player_view(player_id)}\nYou have {gs['num_guesses'] - self.state.turn - 1} guesses left.",
            ta.ObservationType.GAME_MESSAGE,
        )
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        reason = (
            f"The turn limit has been reached. You didn't guess the word, but your best guess scored {round(pct_complete * 100)}% (a green letter counts 1, a yellow letter 0.5).\n"
            f"The secret word was: **{self.game_state['secret_word']}**."
        )
        return self.outcome({0: pct_complete}, reason=reason)

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state, reveal_answer=self.state.done)

    def _evaluate_guess(self, guess: str) -> List[str]:
        """
        Evaluates the player's guess against the secret word and returns feedback for each letter.

        Feedback:
            - "green": correct letter in the correct position.
            - "yellow": letter is in the word but in the wrong position.
            - "wrong": letter is not in the word.

        Args:
            guess (str): The player's guess.

        Returns:
            List[str]: A list of feedback tokens for each letter.
        """
        feedback = [None] * self.game_state["word_length"]
        secret_list = list(self.game_state["secret_word"])
        guess_list = list(guess)

        # First pass: mark correct letters in the correct position (green)
        for i in range(self.word_length):
            if guess_list[i] == secret_list[i]:
                feedback[i] = "G"
                secret_list[i] = None  # Mark this letter as accounted for

        # Second pass: mark correct letters in the wrong position (yellow) or wrong letters
        for i in range(self.word_length):
            if feedback[i] is None:
                if guess_list[i] in secret_list:
                    feedback[i] = "Y"
                    # Remove the first occurrence of guess_list[i] from secret_list
                    index = secret_list.index(guess_list[i])
                    secret_list[index] = None
                else:
                    feedback[i] = "X"
        return feedback

    def _render_board(self) -> str:
        """ Renders the board in full Wordle format. """
        history = self.game_state["guess_history"]
        if not history:
            return "No guesses yet."

        output = []
        for word, feedback in history:
            letters_row = "| Letter  | " + " ".join(word.upper()) + " |"
            divider_row = "|---------|" + "--" * self.game_state['word_length'] + "--"
            status_row = "| Status  | " + " ".join(feedback) + " |"
            output.append(f"{letters_row}\n{divider_row}\n{status_row}\n")

        return "\n".join(output)

    def _render_player_view(self, player_id: int) -> str:
        """ Renders a simplified player view (letters and feedback only). """
        if not self.game_state["guess_history"]:
            return "No guesses yet."

        # Get the most recent guess
        word, feedback = self.game_state["guess_history"][-1]
        word_row = " ".join(word.upper())
        feedback_row = " ".join(feedback)
        return f"{word_row}\n{feedback_row}"

    def _get_percentage_completion(self) -> float:
        """
        Compute completion based on the best submitted guess.
        Returns a float ∈ [0.0, 1.0]
        """
        if not self.game_state.get("guess_history", []):
            return 0.0

        def score(feedback: List[str]) -> float:
            greens = sum(f == "G" for f in feedback)
            yellows = sum(f == "Y" for f in feedback) * 0.5
            return (greens + yellows) / self.game_state["word_length"]

        return max(score(feedback) for _, feedback in self.game_state["guess_history"])
