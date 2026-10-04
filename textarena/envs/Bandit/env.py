import re
import math
from numbers import Real
from typing import Any, Dict, List, Optional, Union

import textarena as ta


class BanditEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    max_button_chars = 128
    max_action_chars = 256
    _ACTION_RE = re.compile(
        r"^\s*(?P<legacy>\[)?\s*(?P<button>[^\[\]]+?)\s*(?(legacy)\])\s*$"
    )

    def __init__(
        self,
        buttons: Optional[List[str]] = None,
        p_gap: float = 0.2,
        num_turns: int = 20,
        include_summary: bool = False,
    ):
        if buttons is None:
            buttons = ["red", "blue", "green", "yellow", "purple"]
        if (
            not isinstance(buttons, (list, tuple))
            or not buttons
            or any(
                not isinstance(button, str)
                or not button.strip()
                or button != button.strip()
                or "\n" in button
                or "\r" in button
                or len(button) > self.max_button_chars
                for button in buttons
            )
            or len(set(buttons)) != len(buttons)
            or any("[" in button or "]" in button for button in buttons)
        ):
            raise ValueError(
                "buttons must be a non-empty sequence of unique, non-empty names "
                f"of at most {self.max_button_chars} characters without brackets."
            )
        if (
            isinstance(p_gap, bool)
            or not isinstance(p_gap, Real)
            or not math.isfinite(float(p_gap))
            or not 0 <= p_gap <= 0.8
        ):
            raise ValueError("p_gap must be a finite number between 0 and 0.8.")
        if isinstance(num_turns, bool) or not isinstance(num_turns, int) or num_turns < 0:
            raise ValueError("num_turns must be a non-negative integer.")
        if not isinstance(include_summary, bool):
            raise TypeError("include_summary must be a boolean.")
        self.buttons = list(buttons)
        self.num_turns = num_turns
        self.max_turns = num_turns + 1  # exploration pulls plus one final decision
        self.p_gap = float(p_gap)
        self.include_summary = include_summary

    def setup(self) -> Dict[str, Any]:
        ground_truth = self.rng.choice(self.buttons)
        return {
            "ground_truth": {b: 0.5 + self.p_gap / 2 if b == ground_truth else self.rng.uniform(0.1, 0.5 - self.p_gap / 2) for b in self.buttons},
            "history": {b: [] for b in self.buttons},
        }

    def prompt(self, player_id: int) -> str:
        return (
            f'You are in a room with {len(self.buttons)} buttons: {", ".join(self.buttons)}. Each button is associated with a Bernoulli distribution with a fixed but unknown mean; the means for the buttons could be different.\n'
            'For each button, when you press it, you will get a reward that is sampled from associated distribution.\n'
            f'You have {self.num_turns} time steps and, on each time step, you can choose any button and receive the reward.\n'
            f'Your goal is to strategically choose buttons at each time step to collect information about their reward distribution, that will let you choose the button with the highest mean reward correctly at the end of {self.num_turns} turns.\n'
            f"On each turn, reply with the name of the button you want to press, e.g. '{self.buttons[0]}'."
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(move, str) or len(move) > self.max_action_chars:
            return self.invalid("Submit one button name.")
        match = self._ACTION_RE.fullmatch(move)
        if match is None:
            return self.invalid("Submit a bare button name or enclose the entire name in brackets.")
        button = match.group("button")
        if button not in self.buttons:
            return self.invalid("An invalid button has been selected.")

        if self.state.turn >= self.num_turns:  # final decision turn
            if button == max(self.game_state['ground_truth'], key=self.game_state['ground_truth'].get):
                return self.outcome({0: 1.0}, reason="Congratulations! You chose the correct button.")
            return self.outcome({0: -self._regret(button)}, reason="You chose an incorrect button.")

        reward = 1.0 if self.rng.random() < self.game_state['ground_truth'][button] else 0.0
        self.game_state['history'][button].append(reward)
        self.broadcast(f"You pressed the {button} button and received a reward of {reward}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if self.include_summary:
            self.broadcast(f'Summary:\n{self._observe_statistics()}', ta.ObservationType.GAME_BOARD)
        if self.state.turn == self.num_turns - 1:
            self.broadcast("You have exhausted your budget for trying out different choices and observe their rewards. Now make a deduction about what the best choice is.", ta.ObservationType.GAME_MESSAGE)
        return None

    def _observe_statistics(self) -> str:
        lines = []
        for button in self.buttons:
            N = len(self.game_state['history'][button]); R = sum(self.game_state['history'][button]) / N if N > 0 else 0.0
            lines.append(f"{button}: {R:.2f} (played {N} times)")
        return "\n".join(lines)

    def _regret(self, button: str) -> float:
        return max(self.game_state['ground_truth'].values()) - self.game_state['ground_truth'][button]
