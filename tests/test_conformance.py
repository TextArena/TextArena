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
- a rejected action changes nothing, snapshot/restore replays identically, and `ta.replay(env.record())`
  rebuilds the same game.
- long pathological inputs are handled quickly, and Python's global random state is never touched.

Per-game tests do not need to repeat these checks.
"""
import enum
import importlib
import json
import random
import re

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
    return cls, _player_count(cls, spec)


def _player_count(cls, spec):
    env = cls(**spec.kwargs)
    return env.default_num_players or env.min_players


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


def _comparable(value, seen=None):
    """A structure that compares equal for equal game states, including deep copies of them."""
    seen = set() if seen is None else seen
    if isinstance(value, (str, bytes, int, float, bool, type(None), enum.Enum, type)):
        return value
    if isinstance(value, random.Random):
        return ("rng", value.getstate())
    if isinstance(value, dict):
        return ("dict", tuple(sorted((repr(key), _comparable(item, seen)) for key, item in value.items())))
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, tuple(_comparable(item, seen) for item in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted(repr(_comparable(item, seen)) for item in value)))
    if callable(value):
        return ("callable", getattr(value, "__qualname__", type(value).__qualname__))
    if hasattr(value, "__dict__"):
        if id(value) in seen:
            return ("cycle", type(value).__qualname__)
        seen.add(id(value))
        return (type(value).__qualname__, _comparable(vars(value), seen))
    return repr(value)


def _game_view(env):
    """Everything a rejected action must leave untouched: the game state, the game's attributes and its rng."""
    excluded = {"state", "rng", *env.snapshot_excluded_attributes}
    attributes = {name: value for name, value in vars(env).items() if name not in excluded}
    return _comparable((env.state.game_state, attributes, env.rng))



def _trace(env, actions):
    trace = []
    for action in actions:
        trace.append(env.get_observation())
        done, _ = env.step(action)
        trace.append(done)
        if done:
            return trace + [env.state.rewards]
    return trace


# Common action shapes across the games, used to find accepted moves.
PROBE_ACTIONS = ACTION_POOL + [
    "e2e4", "d2d4", "4", "3", "5", "up", "down", "left", "right", "draw", "pass", "fold", "check", "raise 10",
    "bet 10", "hit", "stand", "cooperate", "defect", "rock", "paper", "E", "S", "10", "1 1 1", "1 2 3 4", "0 1",
    "A1", "a1 a2", "move W T1", "Broadcast: hello", "Accept", "accept 0", "guess apple", "stay", "play 0", "reveal 0 0",
]


_QUOTED = re.compile(r"'([^'\n]{1,40})'|\"([^\"\n]{1,40})\"|`([^`\n]{1,40})`|\[([^\]\n]{1,40})\]")


def _candidates(env, seen_text):
    """The common shapes above plus anything quoted in what the acting player has seen, where prompts give
    examples and boards often list the legal moves."""
    snapshot = env.snapshot()
    _, observation = env.get_observation()
    env.restore(snapshot)
    seen_text.extend(message for _, message, _ in observation)
    quoted = [next(group for group in match.groups() if group) for text in seen_text for match in _QUOTED.finditer(text)]
    return list(dict.fromkeys(list(reversed(quoted)) + PROBE_ACTIONS))


def _accepted_moves(env, steps):
    """Play up to `steps` actions the game accepts, undoing rejected attempts; returns the actions played."""
    played, seen_text = [], []
    for _ in range(steps):
        if env.state.done:
            break
        for action in _candidates(env, seen_text):
            snapshot, errors = env.snapshot(), env.state.error_count
            env.get_observation()
            env.step(action)
            if env.state.error_count <= errors:
                played.append(action)
                break
            env.restore(snapshot)
        else:
            break
    return played


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_rejected_actions_change_nothing(env_id, spec):
    """At several positions of a game, every candidate action the game rejects must leave it untouched."""
    cls, num_players = _load_env_or_skip(env_id, spec)
    rejected = 0
    for seed in range(2):
        env = cls(**spec.kwargs)
        env.reset(num_players=num_players, seed=seed)
        seen_text = []
        for _ in range(8):
            if env.state.done:
                break
            snapshot = env.snapshot()
            for action in _candidates(env, seen_text):
                env.get_observation()
                before, errors = _game_view(env), env.state.error_count
                env.step(action)
                if env.state.error_count == errors + 1 and env.state.error_count <= env.state.error_allowance:
                    rejected += 1
                    assert _game_view(env) == before, f"rejected {action!r} changed the game (seed {seed})"
                env.restore(snapshot)
            if not _accepted_moves(env, 1):
                break
    if not rejected:
        pytest.skip("the game accepted every candidate action")


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_snapshot_restore_replays_identically(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    env = cls(**spec.kwargs)
    env.reset(num_players=num_players, seed=5)
    _accepted_moves(env, 5)
    snapshot = env.snapshot()
    actions = _accepted_moves(env, 20) + ACTION_POOL
    env.restore(snapshot)
    first = _trace(env, actions)
    env.restore(snapshot)
    assert _trace(env, actions) == first


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_records_replay_the_same_game(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    env = cls(**spec.kwargs)
    env.reset(num_players=num_players)
    _accepted_moves(env, 15)
    _trace(env, ACTION_POOL)
    record = json.loads(json.dumps(env.record()))
    replayed = ta.replay(record)
    assert replayed.state.events == env.state.events
    assert (replayed.state.done, replayed.state.rewards) == (env.state.done, env.state.rewards)


@pytest.mark.parametrize("env_id,spec", _representative_specs(), ids=lambda v: v if isinstance(v, str) else "")
def test_global_random_state_is_never_touched(env_id, spec):
    cls, num_players = _load_env_or_skip(env_id, spec)
    random.seed(1234)
    expected = random.getstate()
    env = cls(**spec.kwargs)
    env.reset(num_players=num_players, seed=3)
    _trace(env, ACTION_POOL * 2)
    assert random.getstate() == expected


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
    "letter-then-spaces": "A" + " " * _PATHOLOGICAL_LENGTH + "x",
    "long-number": "1" * _PATHOLOGICAL_LENGTH + " x",
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
    num_players = _player_count(_resolve_class(spec), spec)
    env = ta.make(env_id)
    env.reset(num_players=num_players, seed=19)
    player_id, observation = env.get_observation()
    assert 0 <= player_id < num_players
    assert isinstance(observation, str)
