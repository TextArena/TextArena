import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.WordChains.renderer import create_board_str
from textarena.utils.word_lists import get_basic_english_words, get_english_words, is_english_word


class WordChainsEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    snapshot_excluded_attributes = ("word_list",)

    def __init__(self):
        basic_words = sorted(word for word in get_basic_english_words() if len(word) <= 5)
        next_shapes = {(word[0], len(word)) for word in get_english_words()}
        # Never start from a word for which the first player has no legal move.
        self.word_list = [
            word for word in basic_words if (word[-1], len(word) + 1) in next_shapes
        ]
        if not self.word_list:
            raise ValueError("The dictionary contains no playable Word Chains starting words.")

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        starting_word = self.rng.choice(self.word_list)
        return {
            "current_word": starting_word,
            "used_words": {starting_word},
            "required_start_letter": starting_word[-1],
            "required_length": len(starting_word) + 1,
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in the Word Chains Game.\nPlayers take turns to provide valid English words that:\n"
            "1. Start with the last letter of the previous word\n2. Must be exactly one letter longer than the previous word\n"
            "3. Cannot be a word that was previously used\n\nTwo consecutive invalid submissions eliminate you.\n"
            f"Reply with just your word, e.g. 'apple', 'monkey', etc.\nThe starting word is '{self.game_state['current_word']}'."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        return f"Next word must:\n1. Start with '{gs['required_start_letter']}'\n2. Be exactly {gs['required_length']} letters long"

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if not re.fullmatch(r"[a-zA-Z]+", action):
            return self.invalid(f"Player {player_id} did not provide a word in the valid format.")
        word = action.lower()
        if len(word) != gs["required_length"]:
            return self.invalid(f"The word must be exactly {gs['required_length']} letters long. '{word}' has {len(word)} characters.")
        if not word.startswith(gs["required_start_letter"]):
            return self.invalid(f"The word must start with '{gs['required_start_letter']}'.")
        if not is_english_word(word):
            return self.invalid(f"'{word}' is not a valid English word.")
        if word in gs["used_words"]:
            return self.invalid(f"The word '{word}' has already been used.")
        # The move is valid: update the game state
        gs["used_words"].add(word)
        gs["current_word"] = word
        gs["required_start_letter"] = word[-1].lower()
        gs["required_length"] = len(word) + 1
        self.broadcast(f"Player {player_id} played: '{word}'", ta.ObservationType.GAME_MESSAGE)
        return None
