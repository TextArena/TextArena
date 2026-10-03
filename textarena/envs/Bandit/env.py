import re
import random
from typing import List, Optional, Tuple, Dict, Any

import textarena as ta


class BanditEnv(ta.Env):
    def __init__(self, buttons: List[str] = ['red', 'blue', 'green', 'yellow', 'purple'], p_gap: float = 0.2, num_turns: int = 20, include_summary: bool = False):
        self.buttons = buttons
        self.num_turns = num_turns
        self.p_gap = p_gap
        self.action_space = re.compile(rf"\[{'|'.join(self.buttons)}\]")
        self.include_summary = include_summary

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.SinglePlayerState(num_players=num_players, max_turns=self.num_turns, seed=seed)
        ground_truth = random.choice(self.buttons)
        self.state.reset(game_state={"ground_truth": {b: 0.5 + self.p_gap / 2 if b == ground_truth else random.uniform(0.1, 0.5 - self.p_gap / 2) for b in self.buttons}, "history": {b: [] for b in self.buttons}}, player_prompt_function=self._generate_player_prompt)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("player_prompt", "intro", num_buttons=len(self.buttons), buttons=", ".join(self.buttons), num_turns=self.num_turns)

    def _observe_statistics(self) -> str:
        lines = []
        for button in self.buttons:
            N = len(self.state.game_state['history'][button]); R = sum(self.state.game_state['history'][button]) / N if N > 0 else 0.0
            lines.append(self.m("board", "stat_line", button=button, reward=f"{R:.2f}", count=N))
        return "\n".join(lines)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r'\[(.*)\]', action)
        if match is None: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            button = match.group(1)
            if button in self.buttons:
                if self.state.turn == self.num_turns:
                    if button == self.state.game_state['ground_truth']: self.state.set_outcome(reward=1.0, reason=self.m("outcome", "win")) 
                    else:                                               self.state.set_outcome(reward=self._regret(button), reason=self.m("outcome", "lose")) 
                else:
                    reward = 1.0 if random.random() < self.state.game_state['ground_truth'][button] else 0.0
                    self.state.game_state['history'][button].append(reward)
                    self.state.add_observation(message=self.m("game_action", "pressed", button=button, reward=reward), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self.include_summary: self.state.add_observation(message=self.m("board", "summary", stats=self._observe_statistics()), observation_type=ta.ObservationType.GAME_BOARD)
            else:
                self.state.set_invalid_move(reason=self.m("invalid_move", "invalid_button"))

        if self.state.turn == self.num_turns - 1:
            self.state.add_observation(message=self.m("game_message", "final_decision"), observation_type=ta.ObservationType.GAME_MESSAGE)
            
        return self.state.step()

    def _regret(self, button: str) -> float: return max(self.state.game_state['ground_truth'].values()) - self.state.game_state['ground_truth'][button]