import re, random
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.PigDice.renderer import create_board_str

class PigDiceEnv(ta.Env):
    def __init__(self, winning_score: int = 100, max_turns: int = 500):
        """
        Args:
            winning_score (int): The score needed to win.
            max_turns (int): Maximum number of turns before the game ends.
        """
        super().__init__()
        self.winning_score = winning_score
        self.max_turns = max_turns
        self.roll_value = None

    def get_board_str(self):
        return create_board_str(scores=self.state.game_state["scores"], turn_total=self.state.game_state["turn_total"], current_player=self.state.current_player_id, current_roll=self.roll_value)

    def reset(self, num_players: int, seed: Optional[int] = None) -> None:
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={"scores": [0]*num_players, "turn_total": 0, "turn_rolls": []}, player_prompt_function=self._prompt)
        self._add_current_board_observation()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, winning_score=self.winning_score)
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[(roll|hold)\]", re.IGNORECASE).search(action.strip()) # Parse the action using regex
        if not match:
            self.state.set_invalid_move(reason=self.m("invalid_move", "invalid_action"))
            return self.state.step(rotate_player=False) 
        action = match.group(1).lower() # Extract the actual action
        # Execute the action
        if action == "roll": self._perform_roll(self.state.current_player_id)
        elif action == "hold": self._perform_hold(self.state.current_player_id)
        self._add_current_board_observation()
        return self.state.step(rotate_player=False)
    
    def _add_current_board_observation(self):
        score = self.m('board', 'player', score_0=self.state.game_state['scores'][0], score_1=self.state.game_state['scores'][1])
        observation = self.m("board", "current_total_scores", scores=score, turn_total=self.state.game_state['turn_total'])
        semi_observation = self.m('board', 'roll_history', observation=observation, roll_history=', '.join(self.state.game_state['turn_rolls'])) if self.state.game_state['turn_rolls'] else self.m('board', 'first_roll', observation=observation)
        full_observations = self.m('board', 'available_actions', observation=semi_observation)
        self.state.add_observation(message=full_observations, observation_type=ta.ObservationType.GAME_BOARD)
        
    def _determine_winner(self, scores):
        if scores[0] > scores[1]: return 0
        elif scores[0] < scores[1]: return 1
        return None

    def _rotate_to_next_player(self):
        scores = self.state.game_state['scores']
        # End game if the turn limit is reached
        if self.state.check_turn_limit():
            winner_id = self._determine_winner(scores)
            if winner_id is None: self.state.set_draw(reason=self.m("outcome", "draw", scores=scores))
            else: self.state.set_winner(player_id=winner_id, reason=self.m("outcome", "winner_by_turn_limit", winner_id=winner_id, scores=scores))
            return
        # End game if the winning score is reached
        if any(score >= self.winning_score for score in scores):
            winner_id = 0 if scores[0] > scores[1] else 1
            self.state.set_winner(player_id=winner_id, reason=self.m("outcome", "winner_by_score", winner_id=winner_id, winning_score=self.winning_score))
            return
        # Otherwise, continue the game
        self.state.game_state["turn_total"] = 0
        self.state.game_state["turn_rolls"] = []
        next_player_id = (self.state.current_player_id + 1) % self.state.num_players
        self.state.manually_set_current_player_id(new_player_id=next_player_id)

    def _perform_roll(self, player_id: int) -> None:
        """ Perform the dice roll logic """
        roll_value = random.randint(1, 6)
        self.roll_value = roll_value
        if roll_value == 1: # Bust! Lose the turn total, end the turn
            self.state.add_observation(message=self.m("actions", "player_busted", player_id=player_id, turn_total=self.state.game_state['turn_total']), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self._rotate_to_next_player()
        else: # Accumulate turn total
            self.state.game_state["turn_total"] += roll_value
            self.state.game_state["turn_rolls"].append(f"'{roll_value}'")

    def _perform_hold(self, player_id: int) -> None:
        # Add turn total to player's score
        self.state.game_state['scores'][player_id] += self.state.game_state['turn_total']
        self.state.add_observation(message=self.m("actions", "player_hold", player_id=player_id, turn_total=self.state.game_state['turn_total']), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._rotate_to_next_player()

