import re, nltk, random
from nltk import pos_tag
from nltk.corpus import words
from typing import Optional, Tuple, List, Dict, Any

import textarena as ta
from textarena.envs.Wordle.renderer import create_board_str
from textarena.envs.utils.word_lists import (
    EnglishDictionary,
    WordFreqDictionary,
    NON_ALPHABETIC_LANGS,
)

try:
    pos_tag(['test'])
except LookupError:
    nltk.download('averaged_perceptron_tagger_eng', quiet=True)

try:
    words.words()
except LookupError:
    nltk.download('words', quiet=True)

class WordleEnv(ta.Env):
    def __init__(self, word_length: int = 5, num_guesses: int = 6, hardcore: Optional[bool] = False):
        """ Initializes the Wordle environment """
        super().__init__()
        self.word_length = word_length
        self.num_guesses = num_guesses
        self.hardcore = hardcore
        # English path is built eagerly and left exactly as before (no new deps,
        # byte-identical output). Non-English content languages are handled
        # lazily via the optional wordfreq backend (see _lang_dict_and_pool).
        self._load_word_list(hardcore=hardcore)
        self.dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True)
        self._ml_dict_cache: Dict[str, Any] = {}
        self._ml_pool_cache: Dict[str, List[str]] = {}
        self._active_dictionary = self.dictionary

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def _content_lang(self) -> str:
        """The single language the secret word is drawn from for this episode.

        Word games are single-content-language (the secret is in one language);
        per-player UI language still varies via the locale layer. When players
        request different languages we take player 0's as the content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    def _lang_dict_and_pool(self, lang: str):
        """Return (dictionary, secret-word pool) for the content language."""
        if lang == "en":
            return self.dictionary, self.word_list
        if lang not in self._ml_dict_cache:
            if lang in NON_ALPHABETIC_LANGS:
                raise ValueError(
                    f"Wordle gives per-letter feedback and does not support the "
                    f"non-alphabetic language '{lang}'."
                )
            d = WordFreqDictionary(lang)
            pool = d.sample_pool(length=self.word_length)
            if not pool:
                raise ValueError(
                    f"No {self.word_length}-letter words available for language '{lang}'."
                )
            self._ml_dict_cache[lang] = d
            self._ml_pool_cache[lang] = pool
        return self._ml_dict_cache[lang], self._ml_pool_cache[lang]

    def _check_word(self, word: str) -> bool:
        return self._active_dictionary.is_valid(word)

    def _load_word_list(self, hardcore: bool = False) -> None:
        """ Load the word list based on the 'hardcore' parameter """
        word_list = words.words("en") if hardcore else words.words("en-basic") # Get word list
        self.word_list = [word for word in word_list if pos_tag([word])[0][1] in ["NN"] and len(word) == self.word_length] # Filter words based on POS tags

    def reset(self, num_players: int = 1, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        lang = self._content_lang()
        dictionary, pool = self._lang_dict_and_pool(lang)
        self._active_dictionary = dictionary
        game_state = {"secret_word": random.choice(pool), "guess_history": [], "word_length": self.word_length, "num_guesses": self.num_guesses}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("prompt", "intro", word_length=game_state["word_length"], num_guesses=game_state["num_guesses"])

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\w+)\]", action) # Extract the guess using regex

        if match is None:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "wrong_format"))
            return self.state.step()

        word = match.group(1).lower()
        if len(word) != self.state.game_state["word_length"]:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "wrong_length", word_length=self.state.game_state["word_length"]))
            return self.state.step()

        # Check if the word has been guessed before
        previous_words = [guess_word for guess_word, _ in self.state.game_state["guess_history"]]
        if word in previous_words:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "already_guessed", word=word))
            return self.state.step()

        if not self._check_word(word):
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "not_a_word", word=word))
            return self.state.step()


        feedback = self._evaluate_guess(word) # Evaluate the word
        self.state.game_state["guess_history"].append((word, feedback)) # Save the guess and feedback

        # Update board views
        self.state.game_state["rendered_board"] = self._render_board()
        self.state.game_state["player_view"] = self._render_player_view(player_id)

        # Check for win condition (all letters green)
        if all(f == "G" for f in feedback):
            self.state.set_outcome(reward=1, reason=self.m("outcome", "win"))
        else:
            self.state.add_observation(message=self.m("feedback", "submitted", word=word, view=self._render_player_view(player_id), guesses_left=self.state.game_state['num_guesses'] - self.state.turn - 1), observation_type=ta.ObservationType.GAME_MESSAGE)

        # check if max num guesses reached
        if len(self.state.game_state["guess_history"]) >= self.num_guesses and not self.state.done:
            pct_complete = self._get_percentage_completion()
            self.state.set_outcome(reward=pct_complete, reason=self.m("outcome", "turn_limit", pct=round(pct_complete * 100), secret=self.state.game_state['secret_word']))

        return self.state.step()

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
        feedback = [None] * self.state.game_state["word_length"]
        secret_list = list(self.state.game_state["secret_word"])
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
        history = self.state.game_state["guess_history"]
        if not history:
            return "No guesses yet."

        output = []
        for word, feedback in history:
            letters_row = "| Letter  | " + " ".join(word.upper()) + " |"
            divider_row = "|---------|" + "--" * self.state.game_state['word_length'] + "--"
            status_row = "| Status  | " + " ".join(feedback) + " |"
            output.append(f"{letters_row}\n{divider_row}\n{status_row}\n")

        return "\n".join(output)

    def _render_player_view(self, player_id: int) -> str:
        """ Renders a simplified player view (letters and feedback only). """
        if not self.state.game_state["guess_history"]:
            return "No guesses yet."

        # Get the most recent guess
        word, feedback = self.state.game_state["guess_history"][-1]
        word_row = " ".join(word.upper())
        feedback_row = " ".join(feedback)
        return f"{word_row}\n{feedback_row}"

    def _get_percentage_completion(self) -> float:
        """
        Compute completion based on the most recent guess for RL training.
        This encourages the model to maximize immediate performance.
        Returns a float ∈ [0.0, 1.0]
        """
        if not self.state.game_state.get("guess_history", []):
            return 0.0

        # Get the most recent guess feedback
        _, latest_feedback = self.state.game_state["guess_history"][-1]

        # Calculate the percentage of letters that are green (correct position) and yellow (correct letter, wrong position)
        greens = sum(1 for f in latest_feedback if f == "G")
        yellows = sum(1 for f in latest_feedback if f == "Y") * 0.5  # Yellow letters count as half for completion

        # Calculate the percentage completion based on the number of green and yellow letters
        return (greens + yellows) / self.state.game_state["word_length"]
