"""The two ways a player can see a game.

- `CurrentTurnObservationWrapper` (``Game-v0``): only the messages produced since the player's previous turn,
  for agents that keep the conversation history themselves.
- `MDPObservationWrapper` (``Game-v0-mdp``): everything needed to act in a single observation, so each step is
  an MDP step: the prompt, every game message so far and the latest board. Raw player actions are included unless
  the game sets ``mdp_includes_actions = False`` because its board and messages already capture the state.
"""
from typing import Dict, List, Optional

import textarena as ta
from textarena.core import Env, Message, ObservationWrapper, Observations, ObservationType

__all__ = ["CurrentTurnObservationWrapper", "MDPObservationWrapper"]


def _sender_name(env: Env, sender_id: int) -> str:
    if sender_id == ta.GAME_ID:
        return "GAME"
    return env.state.role_mapping.get(sender_id, f"Player {sender_id}")


def _format(env: Env, messages: List[Message]) -> str:
    return "\n".join(f"[{_sender_name(env, sender_id)}] {message}" for sender_id, message, _ in messages)


class CurrentTurnObservationWrapper(ObservationWrapper):
    """Only the messages that are new since the player's previous turn."""

    def observation(self, player_id: int, observation: Optional[Observations]) -> str:
        return _format(self.env, observation or [])


class MDPObservationWrapper(ObservationWrapper):
    """The prompt, all messages so far and only the latest board, in one observation."""

    def __init__(self, env: Env):
        super().__init__(env)
        self.history: Dict[int, List[Message]] = {}

    def reset(self, num_players: Optional[int] = None, seed: Optional[int] = None):
        self.history.clear()
        return super().reset(num_players=num_players, seed=seed)

    def observation(self, player_id: int, observation: Optional[Observations]) -> str:
        messages = self.history.setdefault(player_id, [])
        messages.extend(observation or [])
        include_actions = getattr(self.env, "mdp_includes_actions", True)
        last_board = max((i for i, (_, _, kind) in enumerate(messages) if kind == ObservationType.GAME_BOARD), default=None)
        return _format(self.env, [
            message for i, message in enumerate(messages)
            if (message[2] != ObservationType.GAME_BOARD or i == last_board)
            and (include_actions or message[2] != ObservationType.PLAYER_ACTION)
        ])
