import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.Hangman.renderer import create_board_str
from textarena.utils.word_lists import get_basic_english_words, get_headwords


class HangmanEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    action_pattern = r"^([a-zA-Z]+)$"
    action_format = "a single letter or the entire word, for example 'L' or 'LIGHT'"
    snapshot_excluded_attributes = ("word_list",)

    hardcore = ta.Param(False, "Draw the secret word from every dictionary headword instead of Basic English.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        source_words = get_headwords() if self.hardcore else get_basic_english_words()
        self.word_list = sorted(word for word in source_words if len(word) >= 3)
        if not self.word_list:
            raise ValueError("The selected dictionary contains no playable Hangman words.")

    def setup(self) -> Dict[str, Any]:
        target_word = self.rng.choice(self.word_list)
        return {
            "target_word": target_word, "target_letters": list(target_word.upper()),
            "current_board": ["_" for _ in target_word],
            "guessed_letters": set(),
            "guessed_words": set(),
            "tries_left": 6,
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing Hangman. The objective of the game is to guess the word by providing one letter guesses or the entire word.\n"
            "Each column is numbered. The cells that need to be populated with letters are represented by '_'.\n\n"
            "There are two ways you can answer. You can guess a single letter, e.g. 'L', or you can guess the entire word, e.g. 'LIGHT'.\n"
            "If the given letter is in the word, it will be revealed in the grid.\n"
            "If the given word is correct, you win.\n"
            "As you play, the history of your choices will be appended below. Use the information to figure out the word and win.\n"
            "You have 6 incorrect tries before the game ends: every letter that is not in the word and every wrong word guess costs one try.\n"
            "Repeating a letter or word you already guessed is an invalid move.\n\n"
        )

    def render(self, player_id: int) -> str:
        return (
            f"Current board:\n{self._render_current_board()}\nYou have {self.game_state['tries_left']} tries left.\n"
            f"Guessed letters: {', '.join(sorted(self.game_state['guessed_letters']))}"
        )

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        letter = move.group(1).upper()
        if len(letter) > 1:  # Player guessed full word
            if letter in gs["guessed_words"]:
                return self.invalid(f"You already guessed the word '{letter}'.")
            if letter == gs["target_word"].upper():
                gs["current_board"] = gs["target_letters"]  # reveal the word
                return self.outcome({0: 1}, reason="Congratulations! You completed the Hangman puzzle.")
            gs["guessed_words"].add(letter)
            gs["tries_left"] -= 1
            self.broadcast(f"Your guess of '{letter}' is not the target word.", ta.ObservationType.GAME_MESSAGE)
        else:  # Player guessed a single letter
            if letter in gs["guessed_letters"]:
                return self.invalid(f"You guessed the letter '{letter}' which has already been guessed.")
            gs["guessed_letters"].add(letter)
            if letter in gs["target_letters"]:
                self._reveal_letter(letter)
                self.broadcast(f"Your guess of {letter} is in the word", ta.ObservationType.GAME_MESSAGE)
            else:
                gs["tries_left"] -= 1
                self.broadcast(f"Your guess of {letter} is not in the word. You have {gs['tries_left']} lives left.", ta.ObservationType.GAME_MESSAGE)

        if gs["tries_left"] <= 0:
            return self.outcome(
                {0: self._get_percentage_completion()},
                reason=f"You are out of tries. You guessed {self._get_percentage_completion()*100:.2f} percentage of the characters correctly. The target word was : {gs['target_word']}",
            )
        if gs["current_board"] == gs["target_letters"]:
            return self.outcome({0: 1}, reason="Congratulations! You have completed the Hangman puzzle.")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state, reveal_answer=self.state.done)

    def _render_current_board(self) -> str:
        lines = [" ".join(f"C{i:02}" for i in range(len(self.game_state["current_board"])))]
        row_str = ""
        for i, val in enumerate(self.game_state["current_board"]): row_str += f"  {val} "
        lines.append(row_str)
        return "\n" + "\n".join(lines)

    def _reveal_letter(self, letter: str) -> None:
        for i, char in enumerate(self.game_state["target_letters"]):
            if char == letter: self.game_state["current_board"][i] = letter

    def _get_percentage_completion(self) -> float:
        return sum(1 for a, b in zip(self.game_state["current_board"], self.game_state["target_word"]) if a.upper() == b.upper()) / len(self.game_state["target_word"])
