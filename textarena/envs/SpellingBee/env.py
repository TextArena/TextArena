import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.SpellingBee.renderer import create_board_str
from textarena.utils.word_lists import is_english_word


class SpellingBeeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    snapshot_excluded_attributes = ("is_word",)
    max_word_chars = 64
    max_action_chars = 128
    _ACTION_RE = re.compile(rf"[A-Za-z]{{1,{max_word_chars}}}")

    num_letters = ta.Param(7, "The size of the letter set.", min=1, max=26)
    is_word = ta.Param(
        is_english_word,
        "A function that receives a lowercase word and returns whether it counts, for example to use a custom word "
        "list. The default is `is_english_word` from `textarena/utils/word_lists.py`. If it raises an exception, the "
        "submission is not counted and the player is asked to retry.",
        type=object, check=callable, rule="a function that takes a word and returns whether it counts",
    )

    def get_board_str(self): return create_board_str(game_state=self.game_state)

    def render(self, player_id: int) -> str:
        return self.get_board_str()

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    def setup(self) -> Dict[str, Any]:
        return {"allowed_letters": self._generate_allowed_letters(), "word_history": []}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in the Spelling Bee Game.\nAllowed Letters: {''.join(sorted(self.game_state['allowed_letters']))}\n"
            "Players take turns submitting English words that use only the allowed letters; each letter may be used any number of times.\n"
            "Words are checked against the game's English dictionary (UK and US spellings are accepted, proper nouns are not).\n"
            "Each word must be at least as long as the previous word.\nRepeated words are not allowed.\n"
            "If you submit two invalid words in a row, you lose.\n"
            "Reply with exactly one word, e.g., 'example'.\n"
        )

    def _generate_allowed_letters(self) -> set:
        letter_frequencies = { # Frequency of letters in the English language (rough estimates)
            'a': 8.17, 'b': 1.49, 'c': 2.78, 'd': 4.25, 'e': 12.70, 'f': 2.23, 'g': 2.02, 'h': 6.09, 'i': 7.00, 'j': 0.15, 'k': 0.77, 'l': 4.03, 'm': 2.41,
            'n': 6.75, 'o': 7.51, 'p': 1.93, 'q': 0.10, 'r': 5.99, 's': 6.33, 't': 9.06, 'u': 2.76, 'v': 0.98, 'w': 2.36, 'x': 0.15, 'y': 1.97, 'z': 0.07
        }
        # Weighted sampling without replacement using the env RNG
        letters = list(letter_frequencies.keys())
        weights = list(letter_frequencies.values())
        chosen = set()
        while len(chosen) < self.num_letters:
            pick = self.rng.choices(letters, weights=weights, k=1)[0]
            idx = letters.index(pick)
            letters.pop(idx); weights.pop(idx)
            chosen.add(pick)
        return chosen

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(move, str):
            return self.invalid("Submit exactly one word.")
        if len(move) > self.max_action_chars:
            return self.invalid(f"Actions are limited to {self.max_action_chars} characters.")
        if not self._ACTION_RE.fullmatch(move):
            return self.invalid(f"Submit one word of at most {self.max_word_chars} letters.")
        word = move.lower()
        gs = self.game_state
        # check if the word is longer/equal than the last word, and not a repeated word
        if len(gs["word_history"]) != 0 and len(word) < len(gs["word_history"][-1]): return self.invalid("The submitted word is shorter than the previous word.")
        if word in gs["word_history"]: return self.invalid("The submitted word has been submitted before.")
        if not set(word).issubset(gs["allowed_letters"]): return self.invalid("The submitted word contains illegal characters.")
        try:
            valid = bool(self.is_word(word))
        except Exception:
            return self.retryable("The dictionary could not validate the word.")
        if not valid: return self.invalid("The submitted word is not a valid English word.")
        gs["word_history"].append(word)
        self.broadcast(f"Player {player_id} submitted the word: {word}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None
