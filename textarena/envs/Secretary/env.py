import re
from typing import Any, Dict, Union

import textarena as ta


class SecretaryEnv(ta.GameEnv):
    min_players = 1
    max_players = 1

    def __init__(self, N: int = 20):
        if isinstance(N, bool) or not isinstance(N, int) or N < 1:
            raise ValueError("N must be a positive integer")
        self.N = N
        self.action_space = re.compile(r'\[?\s*(accept|continue)\s*\]?', re.IGNORECASE)

    def setup(self) -> Dict[str, Any]:
        return dict(draws=[self.rng.random() for _ in range(self.N)], accepted_idx=None, current_idx=0)

    def prompt(self, player_id: int) -> str:
        return (
            f"You will observe {self.N} hidden values sequentially.\nAt each step reply 'accept' to pick the *current* value, "
            "or 'continue' to skip it and see the next one.\nIf you never accept, you are forced to take the final value.\n"
            "You win (reward = 1) **only** if the value you ultimately pick is the highest of all."
        )

    def on_start(self):
        self._show_next_value()

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self.action_space.fullmatch(move.strip())
        if m is None:
            return self.invalid("Action must be either 'accept' or 'continue'.")

        choice = m.group(1).lower()
        # Auto-accept on the very last turn if no decision yet
        if self.game_state['current_idx'] >= self.N or choice == "accept":
            return self._resolve(accepted_at=self.game_state['current_idx'] - 1)
        self._show_next_value()
        return None

    def _show_next_value(self):
        if self.game_state["current_idx"] >= self.N:
            raise RuntimeError("No unrevealed secretary values remain")
        self.broadcast(f"The current value is {self.game_state['draws'][self.game_state['current_idx']]:.4f}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.game_state['current_idx'] += 1

    def _resolve(self, accepted_at: int) -> ta.Outcome:
        draws = self.game_state["draws"]
        if not 0 <= accepted_at < len(draws):
            raise RuntimeError("Accepted draw index is out of bounds")
        self.game_state["accepted_idx"] = accepted_at
        won = draws[accepted_at] == max(draws)
        message = f"You accepted value {draws[accepted_at]:.4f} at draw {accepted_at + 1}/{self.N}. The best overall was {max(draws):.4f}. "
        return self.outcome({0: 1.0 if won else 0.0}, reason=message + ("Perfect choice! 🎉" if won else "Not the maximum."))
