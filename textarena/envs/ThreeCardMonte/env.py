import random, re
from typing import Dict, Optional, Any

import textarena as ta


class ThreeCardMonteEnv(ta.Env):
    _ACTION_RE = re.compile(r"\[\s*(\d+)\s*\]")

    def __init__(self, num_cups: int = 3, steps: int = 10):
        super().__init__()
        assert num_cups >= 3, "Need at least three cups."
        self.num_cups = num_cups
        self.steps = steps
        self.ball_pos: int
        self.awaiting_guess: bool


    def reset(self, num_players: int, seed: Optional[int] = None):
        rng = random.Random(seed)
        self.ball_pos = rng.randrange(self.num_cups) # Ball starts under a random cup

        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={}, player_prompt_function=self._prompt)

        # Announce starting position
        start_line = " ".join("[X]" if idx == self.ball_pos else f"[{idx}]" for idx in range(self.num_cups))
        self.state.add_observation(self.m("game_message", "ball_starts", line=start_line), observation_type=ta.ObservationType.GAME_MESSAGE)

        # Run the shuffle sequence up-front
        for step in range(1, self.steps + 1):
            i, j = rng.sample(range(self.num_cups), 2)  # distinct cups
            if self.ball_pos == i:      self.ball_pos = j
            elif self.ball_pos == j:    self.ball_pos = i
            self.state.add_observation(self.m("game_message", "shuffle", step=step, steps=self.steps, i=i, j=j), observation_type=ta.ObservationType.GAME_MESSAGE)

        # Show final cup indices and ask for guess
        self.awaiting_guess = True
        self._show_cups(prompt=self.m("game_message", "guess_now"))

    def step(self, action: str):
        m = self._ACTION_RE.fullmatch(action.strip())
        if not m: self.state.set_invalid_move(0.0, self.m("invalid_move", "wrong_format")); return self.state.step()
        guess = int(m.group(1))
        if not (0 <= guess < self.num_cups): self.state.set_invalid_move(0.0, self.m("invalid_move", "out_of_range", max_index=self.num_cups-1)); return self.state.step()
        reward = 1.0 if guess == self.ball_pos else 0.0
        self.state.set_outcome(reward, self.m("outcome", "win") if reward else self.m("outcome", "lose", ball_pos=self.ball_pos))
        self._show_cups(prompt=self.m("game_message", "reveal", ball_pos=self.ball_pos))
        return self.state.step()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro")

    def _show_cups(self, prompt: str):
        cup_line = " ".join(f"[{idx}]" for idx in range(self.num_cups))
        self.state.add_observation(self.m("game_message", "cups", line=cup_line, prompt=prompt), observation_type=ta.ObservationType.GAME_MESSAGE)