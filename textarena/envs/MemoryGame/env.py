import re, random
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta
from textarena.envs.MemoryGame.renderer import create_board_str

class MemoryGameEnv(ta.Env):
    """ Environment for Memory Game """
    def __init__(self, grid_size: Optional[int] = 4, max_turns: Optional[int] = 100):
        """
        Args:
            grid_size (int): The grid size used
        """
        self.grid_size = grid_size
        self.max_turns = max_turns

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)
        game_state = {"board": self._generate_board(), "matched_positions": set(), "score": {0: 0, 1: 0}, "scores": {0: {"Score": 0}, 1: {"Score": 0}}}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(message=self.m("board", "initial", board=self._render_board()), observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("prompt", "intro", player_id=player_id)
    
    def _generate_board(self) -> List[List[str]]:
        symbols = [chr(65 + i) for i in range((self.grid_size ** 2) // 2)] * 2
        random.shuffle(symbols)
        return [symbols[i * self.grid_size:(i + 1) * self.grid_size] for i in range(self.grid_size)]
    
    def _render_board(self) -> str:
        rendered_board = "  " + " ".join(str(c) for c in range(self.grid_size)) + "\n"
        for r in range(self.grid_size):
            row = f"{r} "
            for c in range(self.grid_size):
                if (r, c) in self.state.game_state["matched_positions"]: row += f"{self.state.game_state['board'][r][c]} "
                else: row += ". "
            rendered_board += row.strip() + "\n"
        return rendered_board
    
    def step(self, action: List[int]) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+)\]").search(action) # e.g. [0 1 1 0]
        rotate_player = True
        if match is None:
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format", player_id=player_id))
        else:
            r1, c1, r2, c2 = map(int, match.groups())
            if r1 < 0 or r1 >= self.grid_size or c1 < 0 or c1 >= self.grid_size or r2 < 0 or r2 >= self.grid_size or c2 < 0 or c2 >= self.grid_size: self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_bounds", player_id=player_id))
            elif (r1, c1) == (r2, c2): self.state.set_invalid_move(reason=self.m("invalid_move", "same_card", player_id=player_id))
            elif (r1, c1) in self.state.game_state["matched_positions"] or (r2, c2) in self.state.game_state["matched_positions"]: self.state.set_invalid_move(reason=self.m("invalid_move", "already_matched", player_id=player_id))
            else:
                if self.state.game_state['board'][r1][c1] == self.state.game_state['board'][r2][c2]:
                    rotate_player = False # do not rotate player if the cards match
                    self.state.game_state["score"][player_id] += 1 # update the score
                    self.state.game_state["matched_positions"].update([(r1, c1), (r2, c2)]) # update the matched positions
                    if len(self.state.game_state["matched_positions"]) == self.grid_size ** 2: # check if the game is over
                        if self.state.game_state["score"][0] == self.state.game_state["score"][1]: # check if there is a tie
                            self.state.set_draw(reason=self.m("outcome", "draw"))
                        else: # set the winner
                            winner_id = max(self.state.game_state["score"], key=self.state.game_state["score"].get)
                            self.state.set_winner(player_id=winner_id, reason=self.m("outcome", "win", winner_id=winner_id))

                    ## log the action
                    self.state.add_observation(message=self.m("game_message", "match", player_id=player_id, r1=r1, c1=c1, r2=r2, c2=c2), observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.state.add_observation(message=self.m("board", "current", board=self._render_board()), observation_type=ta.ObservationType.GAME_BOARD)
                else:
                    pos1 = self.state.game_state['board'][r1][c1]; pos2 = self.state.game_state['board'][r2][c2]
                    self.state.add_observation(message=self.m("game_message", "no_match", player_id=player_id, r1=r1, c1=c1, r2=r2, c2=c2, pos1=pos1, pos2=pos2), observation_type=ta.ObservationType.GAME_MESSAGE)

            if self.state.check_turn_limit(): # check turn limit
                reason = self.m("turn_limit", "reached", score0=self.state.game_state['score'][0], score1=self.state.game_state['score'][1])
                if self.state.game_state["score"][0] == self.state.game_state["score"][1]:
                    self.state.set_draw(reason=reason)
                else:
                    winner_id = max(self.state.game_state["score"], key=self.state.game_state["score"].get)
                    self.state.set_winner(player_id=winner_id, reason=self.m("turn_limit", "win", reason=reason, winner_id=winner_id))
        self.state.game_state["scores"] = {0: {"Score": self.state.game_state["score"][0]}, 1: {"Score": self.state.game_state["score"][1]}}
        return self.state.step(rotate_player=rotate_player)


    