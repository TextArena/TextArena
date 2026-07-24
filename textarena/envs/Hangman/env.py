import re, random, copy
from typing import Any, Dict, List, Tuple, Optional

import nltk
from nltk.corpus import words
nltk.download('words')

import textarena as ta
from textarena.envs.Hangman.renderer import create_board_str


class HangmanEnv(ta.Env):
    def __init__(self, hardcore: Optional[bool] = False):
        """ 
        Args:
            hardcore: Whether to play in hardcore mode.
        """
        super().__init__()
        self.hardcore = hardcore
        self.word_list = words.words("en") if hardcore else words.words("en-basic") ## load the word list (to be sampled from)

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed) ## initialize the game state
        target_word = random.choice(self.word_list)
        game_state = {
            "target_word": target_word, "target_letters": list(target_word.upper()), 
            "current_board": ["_" for _ in target_word], "guessed_letters": set(), "tries_left":6
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are playing Hangman. The objective of the game is to guess the word by providing one letter guesses or the entire word.\n"
            "Each column is numbered. The cells that need to be populated with letters are represented by '_'.\n\n"
            "There are two ways you can answer. You can provide one letter guesses in the format of '[L]', or you can guess the entire word in the format of '[LIGHT]'.\n"
            "If the given letter is in the word, it will be revealed in the grid.\n"
            "If the given word is correct, you win.\n"
            "As you play, the history of your choices will be appended below. Use the information to figure out the word and win.\n"
            "You have 6 incorrect tries before the game ends.\n\n"
        )
    
    def _observe_current_state(self) -> None:
        message = f"Current board:\n{self._render_current_board()}\nYou have {self.state.game_state['tries_left']} tries left.\nGuessed letters: {', '.join(sorted(self.state.game_state['guessed_letters']))}"
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
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=f"Invalid move format. You did not respond with a valid 'letter' or 'word'.")
        else:
            # for match in matches:
            letter = match.group(1).upper()  # Convert to uppercase for consistency
            if len(letter) > 1: # Player guessed full word
                if letter == self.state.game_state["target_word"].upper():
                    self.state.set_outcome(reward=1, reason=f"Congratulations! You completed the Hangman puzzle.")
                    self.state.game_state["current_board"] = self.state.game_state["target_letters"]  # reveal the word
                else:
                    self.state.add_observation(message=f"Your guess of '{letter}' is not the target word.", observation_type=ta.ObservationType.GAME_MESSAGE)

            else: # Player guessed a single letter
                if letter in self.state.game_state["guessed_letters"]: # Check if the letter has been guessed before
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=f"You guessed the letter '{letter}' which has already been guessed.") 
                else:
                    self.state.game_state["guessed_letters"].add(letter)
                    if letter in self.state.game_state["target_letters"]: # Check if the letter is in the target word
                        self._reveal_letter(letter) # Update the word progress to reveal this letter
                        self.state.add_observation(message=f"Your guess of {letter} is in the word", observation_type=ta.ObservationType.GAME_MESSAGE)
                    else:
                        self.state.game_state["tries_left"] -= 1
                        self.state.add_observation(message=f"Your guess of {letter} is not in the word. You have {self.state.game_state['tries_left']} lives left.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.state.add_observation(self._render_current_board(), observation_type=ta.ObservationType.GAME_BOARD)

            if self.state.game_state["tries_left"] == 0:                                            self.state.set_outcome(reward=self._get_percentage_completion(), reason=f"You are out of tries. You guessed {self._get_percentage_completion()*100:.2f} percentage of the characters correctly. The target word was : {self.state.game_state['target_word']}")
            elif self.state.game_state["current_board"] == self.state.game_state["target_letters"]: self.state.set_outcome(reward=1, reason=f"Congratulations! You have completed the Hangman puzzle.")
        return self.state.step()
    
    def _reveal_letter(self, letter: str) -> None:
        for i, char in enumerate(self.state.game_state["target_letters"]):
            if char == letter: self.state.game_state["current_board"][i] = letter

    def _get_percentage_completion(self) -> float:
        return sum(1 for a, b in zip(self.state.game_state["current_board"], self.state.game_state["target_word"]) if a.upper() == b.upper()) / len(self.state.game_state["target_word"])

    
