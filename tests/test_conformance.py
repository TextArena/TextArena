"""Engine conformance suite.

Runs a set of generic checks against every registered `ta.GameEnv`. Per-game
rule tests live next to each env in `textarena/envs/<Dir>/test_env.py`; this
suite only verifies the contracts every game must satisfy:

- reset/step/get_observation/close round-trips without exceptions for an
  arbitrary action stream, and the game terminates (possibly by invalid-move
  escalation) or keeps responding sanely.
- rewards and game_info have the documented shape once the game is done.
- identical seeds and action streams produce identical outcomes (determinism).
- the observation stream is consumed exactly once (no duplicates, no losses).
"""
import importlib

import pytest

import textarena as ta
from textarena.engine import GameEnv
from textarena.envs.registration import ENV_REGISTRY

# Envs excluded from conformance runs, with reasons.
SKIP = {
    "Debate": "outcome requires an LLM jury (network)",
    "ScenarioPlanning": "outcome requires an LLM jury (network)",
    "GuessWho": "requires an OpenRouter gamemaster agent (network)",
    "TwentyQuestions": "requires an OpenRouter gamemaster agent (network)",
}

# Some registered configurations require a specific player count.
NUM_PLAYERS_OVERRIDE = {
    "ScorableGames": 6,
}

# A generic action pool: enough shapes that most games either accept some of
# them or terminate via invalid-move escalation.
ACTION_POOL = [
    "0", "1", "2", "a1", "roll", "call", "Bid: 1, 2", "accept",
    "I will think about it 3", "b2 c3", "hold", "nonsense",
]


def _representative_specs():
    """One registry entry per underlying env class, preferring the default id."""
    by_entry = {}
    for env_id, spec in ENV_REGISTRY.items():
        key = str(spec.entry_point)
        if key not in by_entry or len(env_id) < len(by_entry[key][0]):
            by_entry[key] = (env_id, spec)
    return sorted(by_entry.values())


def _resolve_class(spec):
    module_path, class_name = spec.entry_point.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _load_env_or_skip(env_id, spec):
    dir_name = spec.entry_point.split(".envs.")[1].split(".")[0]
    if dir_name in SKIP:
        pytest.skip(SKIP[dir_name])
    cls = _resolve_class(spec)
    assert isinstance(cls, type) and issubclass(cls, GameEnv), f"{spec.entry_point} must subclass GameEnv"
    return cls, NUM_PLAYERS_OVERRIDE.get(dir_name, cls.min_players)


def _variant_player_count(spec, cls):
    if "num_players" in spec.kwargs:
        return spec.kwargs["num_players"]
    if "default_num_players" in spec.kwargs:
        return spec.kwargs["default_num_players"]
    if ".ScorableGames." in spec.entry_point:
        probe = cls(**spec.kwargs)
        probe._load_game_configuration()
        return len(probe.player_configs)
    return cls.min_players


def _rollout(env_id, num_players, seed, max_steps=300):
    env = ta.make(env_id=env_id)
    env.reset(num_players=num_players, seed=seed)
    trace = []
    done = False
    for step_idx in range(max_steps):
        player_id, obs = env.get_observation()
        assert obs is not None
        done, info = env.step(ACTION_POOL[step_idx % len(ACTION_POOL)])
        assert isinstance(done, bool) and isinstance(info, dict)
        trace.append((step_idx, player_id, done))
        if done:
            break
    rewards, game_info = env.close()
    return env, done, trace, rewards, game_info


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_rollout_contract(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    env, done, trace, rewards, game_info = _rollout(env_id, num_players, seed=123)

    assert isinstance(game_info, dict) and set(game_info.keys()) == set(range(num_players))
    for pid_info in game_info.values():
        assert {"role", "invalid_move", "turn_count"} <= set(pid_info.keys())
    if done:
        assert isinstance(rewards, dict)
        assert set(rewards.keys()) == set(range(num_players))
        assert all(isinstance(r, (int, float)) for r in rewards.values())


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_seeded_determinism(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    _, done_a, trace_a, rewards_a, _ = _rollout(env_id, num_players, seed=7)
    _, done_b, trace_b, rewards_b, _ = _rollout(env_id, num_players, seed=7)
    assert done_a == done_b
    assert trace_a == trace_b
    assert rewards_a == rewards_b


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_observations_consumed_exactly_once(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    env = cls(**spec.kwargs)  # unwrapped
    env.reset(num_players=num_players, seed=11)
    pid, first = env.get_observation()
    _, second = env.get_observation()
    assert first, "first observation for a player must not be empty"
    assert second == [], "calling get_observation twice must not replay messages"


@pytest.mark.parametrize("env_id,spec", sorted(ENV_REGISTRY.items()), ids=lambda v: v if isinstance(v, str) else "")
def test_every_registered_variant_resets(env_id, spec):
    cls = _resolve_class(spec)
    num_players = _variant_player_count(spec, cls)
    env = ta.make(env_id)
    env.reset(num_players=num_players, seed=19)
    player_id, observation = env.get_observation()
    assert 0 <= player_id < num_players
    assert isinstance(observation, str)
