import re, random, copy
from typing import Any, Dict, List, Tuple, Optional

import nltk
from nltk.corpus import words
nltk.download('words')

import textarena as ta
from textarena.envs.Hangman.renderer import create_board_str
from textarena.envs.utils.word_lists import WordFreqDictionary, NON_ALPHABETIC_LANGS


class HangmanEnv(ta.Env):
    def __init__(self, hardcore: Optional[bool] = False):
        """
        Args:
            hardcore: Whether to play in hardcore mode.
        """
        super().__init__()
        self.hardcore = hardcore
        # English path is built eagerly and left exactly as before (no new deps,
        # byte-identical output). Non-English content languages are handled
        # lazily via the optional wordfreq backend (see _lang_pool).
        self.word_list = words.words("en") if hardcore else words.words("en-basic") ## load the word list (to be sampled from)
        self._ml_pool_cache: Dict[str, List[str]] = {}

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def _content_lang(self) -> str:
        """The single language the target word is drawn from for this episode.

        Word games are single-content-language (the target is in one language);
        per-player UI language still varies via the locale layer. When players
        request different languages we take player 0's as the content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    def _lang_pool(self, lang: str) -> List[str]:
        """Return the target-word pool for the content language."""
        if lang == "en":
            return self.word_list
        if lang not in self._ml_pool_cache:
            if lang in NON_ALPHABETIC_LANGS:
                raise ValueError(
                    f"Hangman is a per-letter guessing game and does not support "
                    f"the non-alphabetic language '{lang}'."
                )
            pool = WordFreqDictionary(lang).sample_pool()
            if not pool:
                raise ValueError(f"No words available for language '{lang}'.")
            self._ml_pool_cache[lang] = pool
        return self._ml_pool_cache[lang]

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed) ## initialize the game state
        pool = self._lang_pool(self._content_lang())
        target_word = random.choice(pool)
        game_state = {
            "target_word": target_word, "target_letters": list(target_word.upper()),
            "current_board": ["_" for _ in target_word], "guessed_letters": set(), "tries_left":6
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("prompt", "intro")

    def _observe_current_state(self) -> None:
        message = self.m("board", "status", board=self._render_current_board(), tries_left=self.state.game_state['tries_left'], guessed=', '.join(sorted(self.state.game_state['guessed_letters'])))
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_BOARD)

    def _render_current_board(self) -> str:
        lines = [" ".join(f"C{i:02}" for i in range(len(self.state.game_state["current_board"])))]
        row_str = ""  # Label for the single row
        for i, val in enumerate(self.state.game_state["current_board"]): row_str += f"  {val} "
        lines.append(row_str)
        return "\n"+"\n".join(lines)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """ Process the player's action and update the game state accordingly """
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) # Update the observations
        match = re.compile(r"\[([a-zA-Z]+)\]", re.IGNORECASE).search(action)

        if not match:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "wrong_format"))
        else:
            # for match in matches:
            letter = match.group(1).upper()  # Convert to uppercase for consistency
            if len(letter) > 1: # Player guessed full word
                if letter == self.state.game_state["target_word"].upper():
                    self.state.set_outcome(reward=1, reason=self.m("outcome", "win_word"))
                    self.state.game_state["current_board"] = self.state.game_state["target_letters"]  # reveal the word
                else:
                    self.state.add_observation(message=self.m("message", "wrong_word", letter=letter), observation_type=ta.ObservationType.GAME_MESSAGE)

            else: # Player guessed a single letter
                if letter in self.state.game_state["guessed_letters"]: # Check if the letter has been guessed before
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "already_guessed", letter=letter))
                else:
                    self.state.game_state["guessed_letters"].add(letter)
                    if letter in self.state.game_state["target_letters"]: # Check if the letter is in the target word
                        self._reveal_letter(letter) # Update the word progress to reveal this letter
                        self.state.add_observation(message=self.m("message", "letter_in", letter=letter), observation_type=ta.ObservationType.GAME_MESSAGE)
                    else:
                        self.state.game_state["tries_left"] -= 1
                        self.state.add_observation(message=self.m("message", "letter_not_in", letter=letter, tries_left=self.state.game_state['tries_left']), observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.state.add_observation(self._render_current_board(), observation_type=ta.ObservationType.GAME_BOARD)

            if self.state.game_state["tries_left"] == 0:                                            self.state.set_outcome(reward=self._get_percentage_completion(), reason=self.m("outcome", "out_of_tries", pct=f"{self._get_percentage_completion()*100:.2f}", target_word=self.state.game_state['target_word']))
            elif self.state.game_state["current_board"] == self.state.game_state["target_letters"]: self.state.set_outcome(reward=1, reason=self.m("outcome", "win_board"))
        return self.state.step()

    def _reveal_letter(self, letter: str) -> None:
        for i, char in enumerate(self.state.game_state["target_letters"]):
            if char == letter: self.state.game_state["current_board"][i] = letter

    def _get_percentage_completion(self) -> float:
        return sum(1 for a, b in zip(self.state.game_state["current_board"], self.state.game_state["target_word"]) if a.upper() == b.upper()) / len(self.state.game_state["target_word"])
