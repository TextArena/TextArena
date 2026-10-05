import re
from typing import Any, Dict, Union

import textarena as ta


class SecretaryEnv(ta.GameEnv):
    min_players = 1
    max_players = 1

    action_space = re.compile(r'(accept|continue)', re.IGNORECASE)

    N = ta.Param(20, "The number of values.", min=1)

    def setup(self) -> Dict[str, Any]:
        # Values are kept at the 4 decimals shown to the player, so the comparisons they see are exact.
        return dict(draws=[round(self.rng.random(), 4) for _ in range(self.N)], accepted_idx=None, current_idx=0)

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

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: 0.0}, reason=f"Invalid Move: {reason}")

    def _show_next_value(self):
        idx = self.game_state["current_idx"]
        if idx >= self.N:
            raise RuntimeError("No unrevealed secretary values remain")
        message = f"The current value ({idx + 1} of {self.N}) is {self.game_state['draws'][idx]:.4f}."
        if idx == self.N - 1:
            message += " This is the final value: you get it whether you reply 'accept' or 'continue'."
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.game_state['current_idx'] += 1

    def _resolve(self, accepted_at: int) -> ta.Outcome:
        draws = self.game_state["draws"]
        if not 0 <= accepted_at < len(draws):
            raise RuntimeError("Accepted draw index is out of bounds")
        self.game_state["accepted_idx"] = accepted_at
        won = draws[accepted_at] == max(draws)
        message = f"You accepted value {draws[accepted_at]:.4f} at draw {accepted_at + 1}/{self.N}. The best overall was {max(draws):.4f}. "
        return self.outcome({0: 1.0 if won else 0.0}, reason=message + ("Perfect choice! 🎉" if won else "Not the maximum."))
