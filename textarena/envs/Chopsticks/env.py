import re
from typing import Optional, Dict, Any, Tuple

import textarena as ta

class ChopsticksEnv(ta.Env):
    def __init__(self, max_turns: int = 40):
        """
        args:
            max_turns (int): num of turns before draw.
        """
        self.max_turns = max_turns

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={"hands": {0: [1, 1], 1: [1, 1]}, "history": []}, player_prompt_function=self._prompt)
        self.state.add_observation(message=self.m("board", "current_board", hands_0=self.state.game_state['hands'][0], hands_1=self.state.game_state['hands'][1]), observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)
    def get_board_str(self) -> str:
        gs = self.state.game_state
        h0, h1 = gs["hands"][0], gs["hands"][1]
        s = f"Hands:\n  Player 0: [{h0[0]}, {h0[1]}]\n  Player 1: [{h1[0]}, {h1[1]}]\n"
        if gs["history"]: s += "History:\n" + "\n".join(f"  {entry}" for entry in gs["history"]) + "\n"
        return s

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid = self.state.current_player_id
        gs = self.state.game_state
        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        m_atk = re.compile(r"\[\s*attack\s+([01])\s+([01])\s*\]", re.IGNORECASE).search(action)
        if m_atk: # try attack
            my_idx, opp_idx = map(int, m_atk.groups())
            my_val = gs["hands"][pid][my_idx]
            opp_val = gs["hands"][1 - pid][opp_idx]

            # validation
            if my_val == 0:     self.state.set_invalid_move(reason=self.m("invalid_move", "my_hand_dead", my_idx=my_idx))
            elif opp_val == 0:  self.state.set_invalid_move(reason=self.m("invalid_move", "opp_hand_dead", opp_idx=opp_idx))
            else:
                new_val = my_val + opp_val
                gs["hands"][1-pid][opp_idx] = 0 if new_val >= 5 else new_val
                desc = self.m("game_action", "attack", player_id=pid, opp_id=1-pid, opp_idx=opp_idx, opp_val=opp_val, new_val=gs['hands'][1 - pid][opp_idx])
                self.state.add_observation(message=desc, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                gs["history"].append(self.m("history", "entry", player_id=pid, desc=desc))
                # check for win
                if gs["hands"][1 - pid] == [0, 0]: self.state.set_winner(player_id=pid, reason=self.m("outcome", "win"))
        else: # try split
            m_sp = re.compile(r"\[\s*split\s+(\d+)\s+(\d+)\s*\]", re.IGNORECASE).search(action)
            if m_sp: 
                L, R = map(int, m_sp.groups())
                cur_L, cur_R = gs["hands"][pid]
                total = cur_L + cur_R
                if L + R != total:              self.state.set_invalid_move(reason=self.m("invalid_move", "split_sum", total=total))
                elif (L, R) == (cur_L, cur_R):  self.state.set_invalid_move(reason=self.m("invalid_move", "split_no_change"))
                else:
                    gs["hands"][pid] = [L, R]
                    desc = self.m("game_action", "split", player_id=pid, L=L, R=R)
                    self.state.add_observation(message=desc, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    gs["history"].append(self.m("history", "entry", player_id=pid, desc=desc))
            else: self.state.set_invalid_move(reason=self.m("invalid_move", "invalid_command")) # invalid command
        self.state.add_observation(message=self.m("board", "current_board", hands_0=self.state.game_state['hands'][0], hands_1=self.state.game_state['hands'][1]), observation_type=ta.ObservationType.GAME_BOARD)
        if self.state.check_turn_limit(): self.state.set_draw(reason=self.m("outcome", "draw"))
        return self.state.step()