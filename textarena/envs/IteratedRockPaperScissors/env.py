import re
from typing import Optional, Dict, Tuple, Any

import textarena as ta
from textarena.envs.IteratedRockPaperScissors.renderer import create_board_str

class IteratedRockPaperScissorsEnv(ta.Env):
    def __init__(self, num_rounds: int = 5):
        self.num_rounds = num_rounds

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"round": 1, "points": {0:0,1:0}, "moves": {0:None,1:None}, "history": []}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, num_rounds=self.num_rounds)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        move = self._parse_action(action)
        if move not in {"rock", "paper", "scissors"}:
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            self.state.game_state["moves"][player_id] = move
            self.state.add_observation(from_id=player_id, to_id=player_id, message=self.m("game_action", "selects", player_id=player_id, move=move), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            
            if self.state.game_state["moves"][1-player_id] != None: # Resolve the round
                p0_move = self.state.game_state["moves"][0]
                p1_move = self.state.game_state["moves"][1]
                result = self._resolve_round(p0_move, p1_move)
                self.state.game_state["history"].append({0:p0_move,1:p1_move})
                self.state.game_state["round"] += 1
                self.state.game_state["moves"] = {0:None, 1:None}

                if result == 0: 
                    self.state.add_observation(message=self.m("message", "round_draw"), observation_type=ta.ObservationType.GAME_MESSAGE)
                else:
                    self.state.add_observation(message=self.m("message", "round_win", winner=result-1), observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.state.game_state["points"][result-1] += 1

                if self.state.game_state["round"] > self.num_rounds: # Check end condition
                    wins = self.state.game_state.get("points", {0: 0, 1: 0})
                    if wins[0] > wins[1]:   self.state.set_winner(player_id=0, reason=self.m("outcome", "p0_wins"))
                    elif wins[1] > wins[0]: self.state.set_winner(player_id=1, reason=self.m("outcome", "p1_wins"))
                    else:                   self.state.set_draw(self.m("outcome", "draw"))
        
        return self.state.step()

    def _parse_action(self, action: str) -> str:
        match = re.search(r"\[(rock|r|paper|p|scissors|s)\]", action.strip().lower())
        if not match: return ""
        return {"r": "rock", "p": "paper", "s": "scissors"}.get(match.group(1), match.group(1))

    def _resolve_round(self, p0: str, p1: str) -> int:
        if p0 == p1: return 0
        return 1 if {"rock": "scissors", "paper": "rock", "scissors": "paper",}[p0] == p1 else 2