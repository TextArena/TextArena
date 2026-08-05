import re, random
from typing import Any, Dict, List, Optional, Tuple

import nltk
from nltk.corpus import words
nltk.download("words")

import textarena as ta
from textarena.envs.WordChains.renderer import create_board_str
from textarena.envs.utils.word_lists import (
    EnglishDictionary,
    WordFreqDictionary,
    NON_ALPHABETIC_LANGS,
)


class WordChainsEnv(ta.Env):
    def __init__(self):
        # English path is built eagerly and left semantically unchanged (same
        # EnglishDictionary, same <=5-letter filtering). The word list is sorted
        # so start-word selection is reproducible across processes (a plain
        # set()->list() ordering is hash-randomized, which would make the golden
        # transcript non-deterministic). Non-English content languages are handled
        # lazily via the optional wordfreq backend (see _lang_dict_and_pool).
        self.word_list = sorted(set(word.lower() for word in words.words())) # Ensure NLTK words are loaded
        self.word_list = [word for word in self.word_list if len(word) <= 5] # only conserd words shorter then 6 characters
        self.dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True) # Initialize dictionaries for US and UK English
        self._ml_dict_cache: Dict[str, Any] = {}
        self._ml_pool_cache: Dict[str, List[str]] = {}
        self._active_dictionary = self.dictionary

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def _content_lang(self) -> str:
        """The single language the start/chain words are drawn from for this episode.

        Word games are single-content-language (the chain is in one language);
        per-player UI language still varies via the locale layer. When players
        request different languages we take player 0's as the content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    def _lang_dict_and_pool(self, lang: str):
        """Return (dictionary, start-word pool) for the content language."""
        if lang == "en":
            return self.dictionary, self.word_list
        if lang not in self._ml_dict_cache:
            if lang in NON_ALPHABETIC_LANGS:
                raise ValueError(
                    f"Word Chains is a per-letter game (each word must start with "
                    f"the previous word's last letter and grow by one letter) and "
                    f"does not support the non-alphabetic language '{lang}'."
                )
            d = WordFreqDictionary(lang)
            pool = [w for w in d.sample_pool() if 2 <= len(w) <= 5]
            if not pool:
                raise ValueError(
                    f"No short (<=5-letter) words available for language '{lang}'."
                )
            self._ml_dict_cache[lang] = d
            self._ml_pool_cache[lang] = pool
        return self._ml_dict_cache[lang], self._ml_pool_cache[lang]

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        dictionary, pool = self._lang_dict_and_pool(self._content_lang())
        self._active_dictionary = dictionary
        starting_word = random.choice(pool)  # Pick a starting word of minimum length
        game_state={"current_word": starting_word, "used_words": set([starting_word]), "required_start_letter": starting_word[-1].lower(), "required_length": len(starting_word)+1} # Reset state
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(message=self.m("board", "next_word", start_letter=starting_word[-1].lower(), length=len(starting_word) + 1), observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("prompt", "intro", player_id=player_id, word=game_state['current_word'])

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        word_match = re.search(r"\[(\w+)\]", action) # Extract the word from the action
        reason = None
        if not word_match: reason=self.m("invalid", "wrong_format", player_id=self.state.current_player_id)
        else:
            word = word_match.group(1).lower()
            if len(word) != self.state.game_state["required_length"]: reason=self.m("invalid", "wrong_length", length=self.state.game_state['required_length'], word=word, count=len(word)) # Check if the word has the correct length
            elif not word.startswith(self.state.game_state["required_start_letter"]): reason=self.m("invalid", "wrong_start", start_letter=self.state.game_state['required_start_letter']) # Check if the word starts with the required letter
            elif not self._active_dictionary.is_valid(word): reason=self.m("invalid", "not_a_word", word=word) # Check if the word is a valid word
            elif word in self.state.game_state["used_words"]: reason=self.m("invalid", "already_used", word=word) # Check if the word has already been used
            else: # The move is valid: update the game state
                self.state.game_state["used_words"].add(word)
                self.state.game_state["current_word"] = word
                self.state.game_state["required_start_letter"] = word[-1].lower()
                self.state.game_state["required_length"] = len(word) + 1
                self.state.add_observation(message=self.m("message", "played", player_id=self.state.current_player_id, word=word), observation_type=ta.ObservationType.GAME_MESSAGE)
                self.state.add_observation(message=self.m("board", "next_word", start_letter=word[-1].lower(), length=len(word) + 1), observation_type=ta.ObservationType.GAME_BOARD)
        if reason: self.state.set_invalid_move(reason=reason)
        return self.state.step()
