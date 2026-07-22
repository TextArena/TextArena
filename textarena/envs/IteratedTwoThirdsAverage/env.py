import re
from typing import Optional, Dict, Any, Tuple

import textarena as ta

class IteratedTwoThirdsAverageEnv(ta.Env):
    def __init__(self, num_rounds: int=5, min_guess: float=0.0, max_guess: float=100.0):
        self.num_rounds = num_rounds
        self.min_guess = min_guess
        self.max_guess = max_guess

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"round": 1, "points": {0:0, 1:0}, "guesses": {}, "history": []}, player_prompt_function=self._prompt)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, num_rounds=self.num_rounds, min_guess=self.min_guess, max_guess=self.max_guess)

    def get_board_str(self) -> str:
        s = f"Round {self.state.game_state['round']}/{self.num_rounds}\n"
        if self.state.game_state["history"]:
            s += "History:\n"
            for i, past in enumerate(self.state.game_state["history"], start=1): s += (f"  Round {i}: " + ", ".join(f"P{pid}→{guess}" for pid, guess in past.items()) + "\n")
        return s

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid = self.state.current_player_id
        m = re.compile(r"\[\s*([0-9]+(?:\.[0-9]*)?)\s*\]").search(action)
        if not m: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            guess = float(m.group(1))
            if not (self.min_guess <= guess <= self.max_guess): self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_range", min_guess=self.min_guess, max_guess=self.max_guess))
            else: # accept guess
                self.state.game_state["guesses"][pid] = guess
                if len(self.state.game_state["guesses"]) == 2:
                    guesses = self.state.game_state["guesses"]
                    avg = sum(guesses.values()) / 2.0
                    target = (2.0 / 3.0) * avg
                    d0 = abs(guesses[0] - target); d1 = abs(guesses[1] - target) # compute distances
                    self.state.game_state["history"].append(guesses.copy()) # update history
                    self.state.add_observation(message=self.m("round", "result", p0_guess=guesses[0], p1_guess=guesses[1], target=f"{target:.2f}"), observation_type=ta.ObservationType.GAME_MESSAGE)
                    # decide round winner
                    if d0 < d1:     winner = 0
                    elif d1 < d0:   winner = 1
                    else:           winner = None
                    if winner is None: self.state.add_observation(message=self.m("round", "draw"), observation_type=ta.ObservationType.GAME_MESSAGE)
                    else:
                        self.state.game_state["points"][winner] += 1
                        self.state.add_observation(message=self.m("round", "win", winner=winner), observation_type=ta.ObservationType.GAME_MESSAGE)
                    # prepare next round
                    self.state.game_state["round"] += 1
                    self.state.game_state["guesses"].clear()
                    # check end-of-game
                    if self.state.game_state["round"] > self.num_rounds:
                        p0 = self.state.game_state["points"][0]
                        p1 = self.state.game_state["points"][1]
                        if p0 > p1:     self.state.set_winner(player_id=0, reason=self.m("outcome", "win", player_id=0))
                        elif p1 > p0:   self.state.set_winner(player_id=1, reason=self.m("outcome", "win", player_id=1))
                        else:           self.state.set_draw(reason=self.m("outcome", "draw"))
        return self.state.step()
