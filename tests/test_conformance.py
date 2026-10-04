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


@pytest.mark.parametrize(
    "env_id,spec",
    sorted((env_id, spec) for env_id, spec in ENV_REGISTRY.items() if not env_id.endswith("-mdp")),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_no_progress_play_earns_no_reward(env_id, spec):
    """Ending a single-player game through invalid moves alone must never pay out."""
    cls = _resolve_class(spec)
    dir_name = spec.entry_point.split(".envs.")[1].split(".")[0]
    if cls.max_players != 1:
        pytest.skip("single-player games only")
    if dir_name in SKIP:
        pytest.skip(SKIP[dir_name])
    for seed in range(3):
        env = ta.make(env_id)
        env.reset(num_players=1, seed=seed)
        done = False
        for _ in range(500):
            env.get_observation()
            done, _ = env.step("@@@ not a move @@@")
            if done:
                break
        assert done, "repeated invalid moves must end the game"
        rewards, _ = env.close()
        assert rewards[0] <= 0, f"no-progress play earned {rewards[0]} (seed {seed})"


_PATHOLOGICAL_LENGTH = 20_000
PATHOLOGICAL_ACTIONS = {
    "padded": " " * _PATHOLOGICAL_LENGTH + "x" + " " * 1000,
    "inner-spaces": "4" + " " * _PATHOLOGICAL_LENGTH + "x",
    "whitespace-mix": "\t\n " * (_PATHOLOGICAL_LENGTH // 3) + "x",
    "nested-brackets": "[" * (_PATHOLOGICAL_LENGTH // 2) + "x" + "]" * (_PATHOLOGICAL_LENGTH // 2),
}


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_long_pathological_actions_are_handled_quickly(env_id, spec):
    """Training workers step envs with raw model output, so parsing must stay linear-time."""
    import time

    cls, num_players = _load_env_or_skip(env_id, spec)
    for label, action in PATHOLOGICAL_ACTIONS.items():
        env = ta.make(env_id=env_id)
        env.reset(num_players=num_players, seed=0)
        env.get_observation()
        start = time.perf_counter()
        env.step(action)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.25, f"{label} input took {elapsed:.2f}s"


@pytest.mark.parametrize("env_id,spec", sorted(ENV_REGISTRY.items()), ids=lambda v: v if isinstance(v, str) else "")
def test_every_registered_variant_resets(env_id, spec):
    cls = _resolve_class(spec)
    num_players = _variant_player_count(spec, cls)
    env = ta.make(env_id)
    env.reset(num_players=num_players, seed=19)
    player_id, observation = env.get_observation()
    assert 0 <= player_id < num_players
    assert isinstance(observation, str)
