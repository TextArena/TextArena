
import re, numpy
from typing import Optional, Tuple, Dict, Any

import textarena as ta
from textarena.envs.SpellingBee.renderer import create_board_str
from textarena.envs.utils.word_lists import EnglishDictionary

class SpellingBeeEnv(ta.Env):
    def __init__(self, num_letters: int):
        """
        Args:
            num_letters (int): Number of unique allowed letters.
        """
        super().__init__()
        self.num_letters = num_letters
        self.dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True)

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int = 2, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"allowed_letters": self._generate_allowed_letters(), "word_history": []}, player_prompt_function=self._prompt)

    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return (
            f"You are Player {player_id} in the Spelling Bee Game.\nAllowed Letters: {''.join(sorted(game_state['allowed_letters']))}\n"
            "Each word must be at least as long as the previous word.\nRepeated words are not allowed.\n"
            "Wrap your word in square brackets, e.g., '[example]'.\n"
        )

    def _generate_allowed_letters(self) -> set:
        assert self.num_letters <= 26, "num_letters cannot exceed 26." 
        letter_frequencies = { # Frequency of letters in the English language (rough estimates)
            'a': 8.17, 'b': 1.49, 'c': 2.78, 'd': 4.25, 'e': 12.70, 'f': 2.23, 'g': 2.02, 'h': 6.09, 'i': 7.00, 'j': 0.15, 'k': 0.77, 'l': 4.03, 'm': 2.41, 
            'n': 6.75, 'o': 7.51, 'p': 1.93, 'q': 0.10, 'r': 5.99, 's': 6.33, 't': 9.06, 'u': 2.76, 'v': 0.98, 'w': 2.36, 'x': 0.15, 'y': 1.97, 'z': 0.07
        }
        probs = [w / sum(list(letter_frequencies.values())) for w in list(letter_frequencies.values())] # Convert weights to probabilities that sum to 1.
        return set(numpy.random.choice(list(letter_frequencies.keys()), size=self.num_letters, replace=False, p=probs))

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\w+)\]", action.strip().lower()) # extract provided word
        reason = None
        if match:
            word = match.group(1)
            # check if the word is longer/equal than the last word, and not a repeated word
            if len(self.state.game_state["word_history"])!=0 and len(word) < len(self.state.game_state["word_history"][-1]): reason="The submitted word is shorter than the previous word."
            elif word in self.state.game_state["word_history"]: reason="The submitted word has been submitted before."
            elif not (self.dictionary.is_english_word(word)): reason="The submitted word is not a valid english word."
            elif not set(word).issubset(self.state.game_state["allowed_letters"]): reason="The submitted word contains illegal characters."
            else: self.state.game_state["word_history"].append(word); self.state.add_observation(message=f"Player {self.state.current_player_id} submitted the word: {word}", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else: reason="The submitted word does not follow the proper format. Please make sure to use squared brackets."
        if reason: self.state.set_invalid_move(reason=reason)
        return self.state.step()
