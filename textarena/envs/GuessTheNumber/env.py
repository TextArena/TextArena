# import re, random, copy
# from typing import Any, Dict, Optional, Tuple, Union

# import textarena as ta
# from textarena.envs.GuessTheNumber.renderer import create_board_str

# class GuessTheNumberEnv(ta.Env):
#     def __init__(self, min_number: int = 1, max_number: int = 20, max_turns: int = 20):
#         """
#         Args:
#            min_number: The lower bound
#            max_number: The upper bound
#            max_turns: The number of guesses
#         """
#         super().__init__()
#         self.min_number = min_number
#         self.max_number = max_number 
#         self.max_turns = max_turns

#     def get_board_str(self): return create_board_str(game_state=self.state.game_state)
#     def reset(self, num_players: int, seed: Optional[int] = None):
#         self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)
#         self.game_number = random.randint(self.min_number, self.max_number) ## load the game number
#         self.guessed_numbers = set()
#         self.state.reset(game_state={"game_number": self.game_number, "guess_history": []}, player_prompt_function=self._prompt)
    
#     def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
#         return (
#             f"You are Player {player_id}. You are playing Guess The Number.\n"
#             f"You have to guess the number between {self.min_number} and {self.max_number} within {self.max_turns} turns.\n"
#             "As you enter your guess, the game will provide you with hints such as 'higher' or 'lower'.\n"
#             "You may provide your response in any manner. Only the number that is wrapped in square brackets will be considered as your guess. For example, [5].\n"
#             "As you play, the history of your guesses will be appended below. Use the information to complete the game before you run out of guesses.\n"
#             "Enter your guess."
#         )
    
#     def step(self, action: str) -> Tuple[bool, ta.Info]:
#         player_id = self.state.current_player_id
#         self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) ## update the observation
#         action_search_pattern = re.compile(r"\[(\d+)\]") # e.g. [5]
#         match = action_search_pattern.search(action)

#         if not match:   self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=f"Invalid move format. Player {player_id} did not respond with valid '[number]'.")
#         else:
#             player_guess = int(match.group(1))
#             if player_guess < self.min_number or player_guess > self.max_number:    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=f"Invalid move. Player {player_id} guessed a number outside the range specified.")
#             elif player_guess in self.guessed_numbers:                              self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=f"Invalid move. Player {player_id} has already guessed the number.")
#             else:
#                 self.guessed_numbers.add(player_guess)
#                 if player_guess == self.game_number:
#                     self.state.set_outcome(reward=1, reason=f"Congratulations! You guessed the correct number.")
#                 else:
#                     hint = "lower" if player_guess > self.game_number else "higher"
#                     self.state.add_observation(message=f"The target number is {hint}.", observation_type=ta.ObservationType.GAME_MESSAGE)
#                     self.state.game_state["guess_history"].append((player_guess, hint))
#             if self.state.check_turn_limit(): self.state.set_outcome(reward=self._get_percentage_completion(), reason=f"The turn limit has been reached. Guess: {player_guess}, Target: {self.state.game_state['game_number']}") # check turn limit
#         return self.state.step()
    
#     def _get_percentage_completion(self) -> float:
#         """ Get the percentage completion of the game based on how close the last guess was to the target number """
#         if not self.state.game_state["guess_history"]: return 0.0
#         last_guess, _ = self.state.game_state["guess_history"][-1]
#         distance = abs(last_guess - self.state.game_state["game_number"])
#         return 1 - (distance / (self.max_number - self.min_number))



import re, random, copy
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.GuessTheNumber.renderer import create_board_str

class GuessTheNumberEnv(ta.Env):
    def __init__(self, min_number: int = 1, max_number: int = 20, max_turns: int = 20):
        """
        Args:
           min_number: The lower bound
           max_number: The upper bound
           max_turns: The number of guesses
        """
        super().__init__()
        self.min_number = min_number
        self.max_number = max_number 
        self.max_turns = max_turns

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)
        self.game_number = random.randint(self.min_number, self.max_number) ## load the game number
        self.guessed_numbers = set()
        self.state.reset(game_state={"game_number": self.game_number, "guess_history": []}, player_prompt_function=self._prompt)
    
    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, min_number=self.min_number, max_number=self.max_number, max_turns=self.max_turns)
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) ## update the observation
        action_search_pattern = re.compile(r"\[(\d+)\]") # e.g. [5]
        match = action_search_pattern.search(action)

        if not match:   self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format", player_id=player_id))
        else:
            player_guess = int(match.group(1))
            if player_guess < self.min_number or player_guess > self.max_number:    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "out_of_range", player_id=player_id))
            elif player_guess in self.guessed_numbers:                              self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "already_guessed", player_id=player_id))
            else:
                self.guessed_numbers.add(player_guess)
                if player_guess == self.game_number:
                    self.state.set_outcome(reward=1, reason=self.m("outcome", "win"))
                else:
                    hint = "lower" if player_guess > self.game_number else "higher"
                    self.state.add_observation(message=self.m("game_message", f"target_{hint}"), observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.state.game_state["guess_history"].append((player_guess, hint))
            if self.state.check_turn_limit(): self.state.set_outcome(reward=self._get_percentage_completion(), reason=self.m("outcome", "turn_limit", guess=player_guess, target=self.state.game_state['game_number'])) # check turn limit
        return self.state.step()
    
    def _get_percentage_completion(self) -> float:
        """ Get the percentage completion of the game based on how close the last guess was to the target number """
        if not self.state.game_state["guess_history"]: return 0.0
        last_guess, _ = self.state.game_state["guess_history"][-1]
        distance = abs(last_guess - self.state.game_state["game_number"])
        return 1 - (distance / (self.max_number - self.min_number))