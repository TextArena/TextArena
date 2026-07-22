import re
from typing import Optional, Dict, Any, Tuple

import textarena as ta


class IteratedMatchingPenniesEnv(ta.Env):
    def __init__(self, num_rounds: int = 5):
        self.num_rounds = num_rounds
        self._choice_re = re.compile(r"\[\s*(heads|h|tails|t)\s*\]", re.IGNORECASE) # regex to parse [heads], [tails], or shorthand [h], [t]

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"round": 1, "points": {0:0, 1:0}, "moves": {}, "history": []}
        self.state.reset(game_state=game_state, player_prompt_function=self._make_prompt)

    def _make_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        role = self.m("roles", "matcher") if player_id == 0 else self.m("roles", "mismatcher")
        return self.m("player_prompt", "intro", player_id=player_id, role=role, num_rounds=self.num_rounds)

    def get_board_str(self) -> str:
        gs = self.state.game_state
        s = f"Round {gs['round']}/{self.num_rounds}\n"
        if gs["history"]:
            s += "History:\n"
            for i, past in enumerate(gs["history"], start=1):
                s += (f"  Round {i}: " + ", ".join(f"P{pid}→{choice}" for pid, choice in past.items()) + "\n")
        return s

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid = self.state.current_player_id
        m = self._choice_re.search(action)
        if not m: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            token = m.group(1).lower()
            choice = "heads" if token in ("heads", "h") else "tails"
            self.state.game_state["moves"][pid] = choice
            if len(self.state.game_state["moves"]) == 2:
                moves = self.state.game_state["moves"]
                same = (moves[0] == moves[1])
                winner = 0 if same else 1
                self.state.game_state["history"].append(moves.copy())
                verdict = self.m("round", "verdict_match") if same else self.m("round", "verdict_mismatch")
                self.state.add_observation(message=self.m("round", "result", p0_choice=moves[0], p1_choice=moves[1], verdict=verdict), observation_type=ta.ObservationType.GAME_MESSAGE)
                self.state.game_state["points"][winner] += 1
                self.state.game_state["round"] += 1
                self.state.game_state["moves"].clear()
                if self.state.game_state["round"] > self.num_rounds:
                    p0, p1 = self.state.game_state["points"][0], self.state.game_state["points"][1]
                    if p0 > p1:     self.state.set_winner(0, reason=self.m("outcome", "win", player_id=0))
                    elif p1 > p0:   self.state.set_winner(1, reason=self.m("outcome", "win", player_id=1))
                    else:           self.state.set_draw(reason=self.m("outcome", "draw"))
        return self.state.step()
