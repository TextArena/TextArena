import re, random
from typing import Optional, Tuple, List, Dict, Any

import textarena as ta
from textarena.envs.Mastermind.renderer import create_board_str

class MastermindEnv(ta.Env):
    def __init__(self, code_length: Optional[int] = 4, num_numbers: Optional[int] = 6, max_turns: Optional[int] = 20, duplicate_numbers: Optional[bool] = False):
        """
        Args:
            code_length (int): the number of options to get right
            max_turns (int): the number of turns until draw
            duplicate_numbers (bool): whether numbers can be duplicates
        """
        super().__init__()
        self.max_turns = max_turns
        self.code_length = code_length 
        self.num_numbers = num_numbers
        self.duplicate_numbers = duplicate_numbers
    
    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns) # Initialize game state variables
        sample_fn = random.choices if self.duplicate_numbers else random.sample # generate secret code 
        code = sample_fn(list(range(1, self.num_numbers + 1)), k=self.code_length)
        game_state={"secret_code":code, "guess": [], "code_length": self.code_length, "num_numbers": self.num_numbers, "duplicate_numbers": self.duplicate_numbers, "history": []}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        repeats = self.m("player_prompt", "with_repeats") if game_state['duplicate_numbers'] else self.m("player_prompt", "no_duplicates")
        return self.m("player_prompt", "intro", code_length=game_state['code_length'], num_numbers=game_state['num_numbers'], repeats=repeats, max_turns=f"{self.state.max_turns:.0f}")

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) # Update the observation with the player's action
        match = re.compile(r"\[(\d+(?:\s+\d+)*)\]").search(action) # e.g., [1 2 3 4]

        if match is None:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format"))
            return self.state.step()

        # Extract and validate the numbers from the action
        try:
            player_guess = list(map(int, match.group(1).split()))
        except ValueError:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "not_integers"))
            return self.state.step()

        # Validate guess length
        if len(player_guess) != self.state.game_state["code_length"]:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_length", code_length=self.state.game_state['code_length']))
            return self.state.step()

        # Validate number range
        if any(num < 1 or num > self.state.game_state["num_numbers"] for num in player_guess):
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "out_of_range", num_numbers=self.state.game_state['num_numbers']))
            return self.state.step()

        # Validate no duplicates if not allowed
        if not self.state.game_state["duplicate_numbers"] and len(set(player_guess)) != len(player_guess):
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "duplicates_not_allowed"))
            return self.state.step()

        # Check if the guess has been made before
        previous_guesses = [entry["guess"] for entry in self.state.game_state["history"]]
        if player_guess in previous_guesses:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "repeated_guess", guess=player_guess))
            return self.state.step()

        black_pegs, white_pegs = self._evaluate_guess(player_guess) # Evaluate the guess
        self.state.game_state["history"].append({"guess": player_guess, "black": black_pegs, "white": white_pegs})
        
        if black_pegs == self.state.game_state["code_length"]:  self.state.set_outcome(reward=1, reason=self.m("outcome", "win", black_pegs=black_pegs, code_length=self.state.game_state['code_length'])) # Check for win condition
        else:                                                   self.state.add_observation(from_id=ta.GAME_ID, message=self.m("game_action", "feedback", guess=match.group(1), black_pegs=black_pegs, white_pegs=white_pegs), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION) # Add feedback message to observations

        # check turn count
        if self.state.check_turn_limit():
            pct_completion = self._get_percentage_completion()
            self.state.set_outcome(reward=pct_completion, reason=self.m("outcome", "turn_limit", percent=f"{pct_completion*100:.2f}"))
        return self.state.step()
    
    def _evaluate_guess(self, player_guess: List[int]) -> Tuple[int, int]:
        black_pegs, white_pegs = 0, 0
        secret_copy = self.state.game_state["secret_code"].copy()
        guess_copy = player_guess.copy()
        # First pass: count black pegs and mark them as None
        for i in range(self.state.game_state["code_length"]):
            if guess_copy[i] == secret_copy[i]:
                black_pegs += 1
                secret_copy[i] = None
                guess_copy[i] = None
        # Second pass: count white pegs using the remaining numbers
        for i in range(self.state.game_state["code_length"]):
            if guess_copy[i] is not None and guess_copy[i] in secret_copy:
                white_pegs += 1
                secret_copy[secret_copy.index(guess_copy[i])] = None # Remove the first occurrence to prevent over-counting
        return black_pegs, white_pegs

    def _get_percentage_completion(self) -> float:
        """ Calculate a percentage completion score based on the player's latest performance """
        if not self.state.game_state["history"]: return 0.0
        latest_entry = self.state.game_state["history"][-1]
        return ((latest_entry["black"] * 1.0) + (latest_entry["white"] * 0.5)) / self.state.game_state["code_length"]