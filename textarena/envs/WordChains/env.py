import re, random 
from typing import Any, Dict, Optional, Tuple 

import nltk 
from nltk.corpus import words 
nltk.download("words")

import textarena as ta 
from textarena.envs.WordChains.renderer import create_board_str
from textarena.envs.utils.word_lists import EnglishDictionary


class WordChainsEnv(ta.Env):
    def __init__(self):
        self.word_list = list((set(word.lower() for word in words.words()))) # Ensure NLTK words are loaded
        self.word_list = [word for word in self.word_list if len(word) <= 5] # only conserd words shorter then 6 characters
        self.dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True) # Initialize dictionaries for US and UK English

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        starting_word = random.choice(self.word_list)  # Pick a starting word of minimum length
        game_state={"current_word": starting_word, "used_words": set([starting_word]), "required_start_letter": starting_word[-1].lower(), "required_length": len(starting_word)+1} # Reset state
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(message=f"Next word must:\n1. Start with '{starting_word[-1].lower()}'\n2. Be exactly {len(starting_word) + 1} letters long", observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in the Word Chains Game.\nPlayers take turns to provide valid English words that:\n"
            "1. Start with the last letter of the previous word\n2. Must be longer than the previous word\n"
            "3. Cannot be a word that was previously used\n\nIf you provide an invalid word, repeat a word, or fail to follow the rules, you lose.\n"
            f"Please wrap your word in square brackets, e.g., '[apple]', '[monkey]', etc.\nThe starting word is [{game_state['current_word']}]."
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        word_match = re.search(r"\[(\w+)\]", action) # Extract the word from the action
        reason = None
        if not word_match: reason=f"Player {self.state.current_player_id} did not provide a word in the valid format."
        else:
            word = word_match.group(1).lower()
            if len(word) != self.state.game_state["required_length"]: reason=f"The word must be exactly {self.state.game_state['required_length']} letters long. '{word}' has {len(word)} characters." # Check if the word has the correct length
            elif not word.startswith(self.state.game_state["required_start_letter"]): reason=f"The word must start with '{self.state.game_state['required_start_letter']}'." # Check if the word starts with the required letter
            elif not self.dictionary.is_english_word(word): reason=f"'{word}' is not a valid English word." # Check if the word is a valid English word
            elif word in self.state.game_state["used_words"]: reason=f"The word '{word}' has already been used." # Check if the word has already been used
            else: # The move is valid: update the game state
                self.state.game_state["used_words"].add(word)
                self.state.game_state["current_word"] = word
                self.state.game_state["required_start_letter"] = word[-1].lower()
                self.state.game_state["required_length"] = len(word) + 1
                self.state.add_observation(message=f"Player {self.state.current_player_id} played: [{word}]", observation_type=ta.ObservationType.GAME_MESSAGE)
                self.state.add_observation(message=f"Next word must:\n1. Start with '{word[-1].lower()}'\n2. Be exactly {len(word) + 1} letters long", observation_type=ta.ObservationType.GAME_BOARD)
        if reason: self.state.set_invalid_move(reason=reason)
        return self.state.step()