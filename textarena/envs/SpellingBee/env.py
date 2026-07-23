
import re, numpy
from typing import Optional, Tuple, Dict, Any, List

import textarena as ta
from textarena.envs.SpellingBee.renderer import create_board_str
from textarena.envs.utils.word_lists import (
    EnglishDictionary,
    WordFreqDictionary,
    NON_ALPHABETIC_LANGS,
)

# English letter frequencies (rough estimates). Kept exactly as the original so
# the English content-language path is byte-identical.
_EN_LETTER_FREQUENCIES = {
    'a': 8.17, 'b': 1.49, 'c': 2.78, 'd': 4.25, 'e': 12.70, 'f': 2.23, 'g': 2.02, 'h': 6.09, 'i': 7.00, 'j': 0.15, 'k': 0.77, 'l': 4.03, 'm': 2.41,
    'n': 6.75, 'o': 7.51, 'p': 1.93, 'q': 0.10, 'r': 5.99, 's': 6.33, 't': 9.06, 'u': 2.76, 'v': 0.98, 'w': 2.36, 'x': 0.15, 'y': 1.97, 'z': 0.07
}

class SpellingBeeEnv(ta.Env):
    def __init__(self, num_letters: int = 7):
        """
        Args:
            num_letters (int): Number of unique allowed letters.
        """
        super().__init__()
        self.num_letters = num_letters
        self.dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True)
        # Non-English content languages are handled lazily via the optional
        # wordfreq backend, cached per language.
        self._ml_dict_cache: Dict[str, Any] = {}
        self._active_dictionary = self.dictionary

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def _content_lang(self) -> str:
        """The single language the allowed letters / words are drawn from for this episode.

        SpellingBee is single-content-language (the allowed-letter set and word
        validity are in one language); per-player UI language still varies via
        the locale layer. When players request different languages we take
        player 0's as the content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    def _lang_dictionary(self, lang: str):
        """Return the word dictionary for the content language."""
        if lang == "en":
            return self.dictionary
        if lang not in self._ml_dict_cache:
            if lang in NON_ALPHABETIC_LANGS:
                raise ValueError(
                    f"SpellingBee is a per-letter word game and does not support "
                    f"the non-alphabetic language '{lang}'."
                )
            self._ml_dict_cache[lang] = WordFreqDictionary(lang)
        return self._ml_dict_cache[lang]

    def reset(self, num_players: int = 2, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        lang = self._content_lang()
        self._active_dictionary = self._lang_dictionary(lang)
        self.state.reset(game_state={"allowed_letters": self._generate_allowed_letters(lang, seed), "word_history": []}, player_prompt_function=self._prompt)

    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("prompt", "intro", player_id=player_id, allowed_letters=''.join(sorted(game_state['allowed_letters'])))

    def _generate_allowed_letters(self, lang: str, seed: Optional[int]) -> set:
        assert self.num_letters <= 26, "num_letters cannot exceed 26."
        # Seed numpy from the game seed so the allowed-letter set is reproducible
        # run-to-run (previously it used the global numpy RNG state).
        if seed is not None:
            numpy.random.seed(seed)
        if lang == "en":
            letter_frequencies = _EN_LETTER_FREQUENCIES
        else:
            letter_frequencies = self._active_dictionary.letter_frequencies()
        letters = list(letter_frequencies.keys())
        total = sum(letter_frequencies.values())
        probs = [w / total for w in letter_frequencies.values()]  # Convert weights to probabilities that sum to 1.
        n = min(self.num_letters, len(letters))
        return set(numpy.random.choice(letters, size=n, replace=False, p=probs))

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\w+)\]", action.strip().lower()) # extract provided word
        reason = None
        if match:
            word = match.group(1)
            # check if the word is longer/equal than the last word, and not a repeated word
            if len(self.state.game_state["word_history"])!=0 and len(word) < len(self.state.game_state["word_history"][-1]): reason=self.m("invalid", "shorter")
            elif word in self.state.game_state["word_history"]: reason=self.m("invalid", "repeated")
            elif not (self._active_dictionary.is_valid(word)): reason=self.m("invalid", "not_a_word")
            elif not set(word).issubset(self.state.game_state["allowed_letters"]): reason=self.m("invalid", "illegal_characters")
            else: self.state.game_state["word_history"].append(word); self.state.add_observation(message=self.m("feedback", "submitted", player_id=self.state.current_player_id, word=word), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else: reason=self.m("invalid", "wrong_format")
        if reason: self.state.set_invalid_move(reason=reason)
        return self.state.step()
