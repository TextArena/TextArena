"""Observation wrappers.

TextArena registers exactly two variants of every environment:

- ``EnvId-v0`` (default) uses `CurrentTurnObservationWrapper`: the agent sees
  only the messages produced since its last turn. This is the natural
  "conversation" interface — history is the agent's own responsibility.

- ``EnvId-v0-mdp`` uses one of the two state-complete wrappers below, chosen
  per environment, so that a single observation contains everything needed to
  act (i.e. the interaction becomes an MDP):

  * `FullHistoryObservationWrapper` — the full transcript (prompt, player
    actions, game messages), with only the latest board render kept since
    older boards are superseded state. For conversation and negotiation games
    where the dialogue itself is the state.

  * `BoardObservationWrapper` — like the above but without raw player
    actions: prompt, game messages/action descriptions, and the latest board.
    For board games whose render (plus announcements) captures the full state.
"""
from typing import Dict, List, Optional, Tuple

import textarena as ta
from textarena.core import Env, ObservationWrapper, Observations, ObservationType

__all__ = ["CurrentTurnObservationWrapper", "FullHistoryObservationWrapper", "BoardObservationWrapper"]


def _sender_name(env: Env, sender_id: int) -> str:
    if sender_id == ta.GAME_ID:
        return "GAME"
    return env.state.role_mapping.get(sender_id, f"Player {sender_id}")


class CurrentTurnObservationWrapper(ObservationWrapper):
    """Formats only the current turn's new messages as a string."""

    def observation(self, player_id: int, observation: Optional[Observations]) -> str:
        if not observation:
            return ""
        return "\n".join(f"[{_sender_name(self.env, sender_id)}] {message}" for sender_id, message, _ in observation)


class _AccumulatingObservationWrapper(ObservationWrapper):
    """Shared machinery: accumulate each player's message deltas across turns."""

    # Observation types excluded from the rendered transcript.
    exclude: Tuple[ObservationType, ...] = ()

    def __init__(self, env: Env):
        super().__init__(env)
        self.full_observations: Dict[int, List[Tuple[int, str, ObservationType]]] = {}

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.full_observations.clear()
        return super().reset(num_players=num_players, seed=seed)

    def observation(self, player_id: int, observation: Optional[Observations]) -> str:
        if observation:
            self.full_observations.setdefault(player_id, []).extend(observation)
        return self._render(player_id)

    def _render(self, player_id: int) -> str:
        messages = self.full_observations.get(player_id, [])
        # only the latest board is state; older renders are superseded
        last_board_idx = max((i for i, (_, _, t) in enumerate(messages) if t == ObservationType.GAME_BOARD), default=None)
        lines = []
        for i, (sender_id, message, obs_type) in enumerate(messages):
            if obs_type in self.exclude:
                continue
            if obs_type == ObservationType.GAME_BOARD and i != last_board_idx:
                continue
            lines.append(f"[{_sender_name(self.env, sender_id)}] {message}")
        return "\n".join(lines)


class FullHistoryObservationWrapper(_AccumulatingObservationWrapper):
    """Complete transcript: prompt, all actions and messages, latest board."""
    exclude = ()


class BoardObservationWrapper(_AccumulatingObservationWrapper):
    """Game-driven state only: prompt, game messages, latest board — no raw player actions."""
    exclude = (ObservationType.PLAYER_ACTION,)
