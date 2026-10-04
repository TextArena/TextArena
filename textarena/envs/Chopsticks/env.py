import re
from typing import Any, Dict, Optional, Union

import textarena as ta


class ChopsticksEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, max_turns: int = 40):
        """
        args:
            max_turns (int): num of turns before draw.
        """
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.max_turns = max_turns

    def setup(self) -> Dict[str, Any]:
        return {"hands": {0: [1, 1], 1: [1, 1]}, "history": []}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Chopsticks. On your turn, choose one of:\n"
            "  + Attack:  'attack M O'  where M=your hand (0 or 1), O=opponent hand (0 or 1).\n"
            "    - Opponent's hand count increases by your hand; if >=5, it becomes 0.\n"
            "  + Split:   'split L R'  to redistribute your total fingers into L and R (L+R = your total).\n"
            "Reply with exactly one of those commands."
        )

    def render(self, player_id: int) -> str:
        hands = self.game_state["hands"]
        return f"Current Board:\nPlayer 0: {hands[0]}\nPlayer 1: {hands[1]}"

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        m_atk = re.compile(r"^\s*\[?\s*attack\s+([01])\s+([01])\s*\]?\s*$", re.IGNORECASE).search(action)
        if m_atk:
            my_idx, opp_idx = map(int, m_atk.groups())
            my_val = gs["hands"][player_id][my_idx]
            opp_val = gs["hands"][1 - player_id][opp_idx]
            if my_val == 0: return self.invalid(f"Your hand {my_idx} is dead.")
            if opp_val == 0: return self.invalid(f"Opponent hand {opp_idx} is already dead.")
            new_val = my_val + opp_val
            gs["hands"][1 - player_id][opp_idx] = 0 if new_val >= 5 else new_val
            desc = f"P{player_id} attacks P{1 - player_id}’s hand {opp_idx}: it goes from {opp_val} to {gs['hands'][1 - player_id][opp_idx]}."
            self.broadcast(desc, ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["history"].append(desc)
            if gs["hands"][1 - player_id] == [0, 0]:
                return self.winner(player_id, reason="Both opponent hands dead.")
            return None

        m_sp = re.compile(r"^\s*\[?\s*split\s+([0-4])\s+([0-4])\s*\]?\s*$", re.IGNORECASE).search(action)
        if m_sp:
            L, R = map(int, m_sp.groups())
            cur_L, cur_R = gs["hands"][player_id]
            total = cur_L + cur_R
            if L + R != total: return self.invalid(f"Split must sum to {total}.")
            if sorted((L, R)) == sorted((cur_L, cur_R)):
                return self.invalid("Split must change your hand distribution, not only swap hand indices.")
            gs["hands"][player_id] = [L, R]
            desc = f"P{player_id} splits into [{L}, {R}]."
            self.broadcast(desc, ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["history"].append(desc)
            return None

        return self.invalid("Invalid move. Use 'attack M O' or 'split L R'.")

    def get_board_str(self) -> str:
        gs = self.game_state
        h0, h1 = gs["hands"][0], gs["hands"][1]
        s = f"Hands:\n  Player 0: [{h0[0]}, {h0[1]}]\n  Player 1: [{h1[0]}, {h1[1]}]\n"
        if gs["history"]: s += "History:\n" + "\n".join(f"  {entry}" for entry in gs["history"]) + "\n"
        return s
