from typing import Any, Dict, Optional, Union

import textarena as ta


def _valid_buttons(buttons) -> bool:
    return bool(buttons) and len(set(buttons)) == len(buttons) and all(
        isinstance(button, str) and button and button == button.strip() and len(button) <= 128
        and not any(char in button for char in "[]\n\r")
        for button in buttons
    )


class BanditEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_action_chars = 256

    buttons = ta.Param(
        ["red", "blue", "green", "yellow", "purple"], "The button names.", check=_valid_buttons,
        rule="a list of unique, non-empty names of at most 128 characters, without square brackets, line breaks, "
             "or leading or trailing spaces",
    )
    p_gap = ta.Param(
        0.2, "The minimum lead of the best button's mean over every other button. Smaller gaps make the best button "
             "harder to identify.", min=0, max=0.8,
    )
    num_turns = ta.Param(
        20, "The number of presses before the final answer. With 0, your first reply is the final answer.", min=0,
    )
    include_summary = ta.Param(False, "Show the per-button averages after every press.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_turns = self.num_turns + 1  # exploration pulls plus one final decision

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
            f"On each turn, reply with the name of the button you want to press, e.g. '{self.buttons[0]}'.\n"
            f"After your {self.num_turns} presses, reply with the name of the button you believe has the highest mean reward. "
            "That final answer ends the game: a correct answer scores 1, and a wrong one scores minus the gap between the best mean and the mean of the button you chose."
        )

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        if not isinstance(action, str) or len(action) > self.max_action_chars:
            return None
        return super().action_echo_target(player_id, action)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if not isinstance(move, str) or len(move) > self.max_action_chars:
            return self.invalid("Submit one button name.")
        button = self._resolve_button(move)
        if button is None:
            return self.invalid(f"An invalid button has been selected. Choose one of: {', '.join(self.buttons)}.")

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
            self.broadcast("You have exhausted your budget for trying out different choices and observe their rewards. Now make a deduction about what the best choice is and reply with the name of that button.", ta.ObservationType.GAME_MESSAGE)
        return None

    def _resolve_button(self, name: str) -> Optional[str]:
        if name in self.buttons:
            return name
        matches = [button for button in self.buttons if button.casefold() == name.casefold()]
        return matches[0] if len(matches) == 1 else None

    def _observe_statistics(self) -> str:
        lines = []
        for button in self.buttons:
            N = len(self.game_state['history'][button]); R = sum(self.game_state['history'][button]) / N if N > 0 else 0.0
            lines.append(f"{button}: {R:.2f} (played {N} times)")
        return "\n".join(lines)

    def _regret(self, button: str) -> float:
        return max(self.game_state['ground_truth'].values()) - self.game_state['ground_truth'][button]
