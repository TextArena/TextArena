import re
from typing import Any, Dict, Union

import textarena as ta


class ThreeCardMonteEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    _ACTION_RE = re.compile(r"(\d+)")

    def __init__(self, num_cups: int = 3, steps: int = 10):
        if isinstance(num_cups, bool) or not isinstance(num_cups, int) or num_cups < 3:
            raise ValueError("num_cups must be an integer of at least 3")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 0:
            raise ValueError("steps must be a non-negative integer")
        self.num_cups = num_cups
        self.steps = steps

    @property
    def ball_pos(self) -> int:
        return self.game_state["ball_pos"]

    def setup(self) -> Dict[str, Any]:
        return {"ball_pos": self.rng.randrange(self.num_cups)}  # Ball starts under a random cup

    def prompt(self, player_id: int) -> str:
        return "Track the hidden ball 'X' while the cups are shuffled.\nAfter shuffling, guess its location by replying with the cup number, e.g. '1'."

    def on_start(self):
        # Announce starting position
        start_line = " ".join("[X]" if idx == self.game_state["ball_pos"] else f"[{idx}]" for idx in range(self.num_cups))
        self.broadcast(f"Ball starts: {start_line}", ta.ObservationType.GAME_MESSAGE)

        # Run the shuffle sequence up-front
        for step in range(1, self.steps + 1):
            i, j = self.rng.sample(range(self.num_cups), 2)  # distinct cups
            if self.game_state["ball_pos"] == i:    self.game_state["ball_pos"] = j
            elif self.game_state["ball_pos"] == j:  self.game_state["ball_pos"] = i
            self.broadcast(f"Shuffle {step}/{self.steps}: swapped cups {i} and {j}.", ta.ObservationType.GAME_MESSAGE)

        # Show final cup indices and ask for guess
        self._show_cups(prompt="(Guess NOW!)")

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self._ACTION_RE.fullmatch(move.strip())
        if not m:
            return self.invalid("Bad action. Reply with a cup number, e.g. '1'.")
        normalized = m.group(1).lstrip("0") or "0"
        if len(normalized) > len(str(self.num_cups - 1)):
            return self.invalid(f"Index out of range 0-{self.num_cups-1}.")
        guess = int(normalized)
        if not (0 <= guess < self.num_cups):
            return self.invalid(f"Index out of range 0-{self.num_cups-1}.")
        ball_pos = self.game_state["ball_pos"]
        reward = 1.0 if guess == ball_pos else 0.0
        self._show_cups(prompt=f"(Reveal: ball under {ball_pos})")
        return self.outcome({0: reward}, reason="Correct! You found the ball." if reward else f"Wrong — ball was under cup {ball_pos}.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: 0.0}, reason=f"Invalid Move: {reason}")

    def _show_cups(self, prompt: str):
        cup_line = " ".join(f"[{idx}]" for idx in range(self.num_cups))
        self.broadcast(f"Cups: {cup_line}  {prompt}", ta.ObservationType.GAME_MESSAGE)
