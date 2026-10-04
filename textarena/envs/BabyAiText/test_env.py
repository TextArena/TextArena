"""Deterministic tests for BabyAiText using an injected fake backend."""
import copy
from types import SimpleNamespace

import pytest

import textarena.envs.BabyAiText.env as babyai_module
from textarena.envs.BabyAiText.env import BabyAiTextEnv


class _Backend:
    def __init__(self, *, done_after=None, modern_api=False, malformed_reset=False):
        self.done_after = done_after
        self.modern_api = modern_api
        self.malformed_reset = malformed_reset
        self.steps = []
        self.reset_seeds = []
        self.position = 0
        self.mission = "reach the goal"
        self.carrying = None
        self.env = SimpleNamespace(env="FAKE GRID")

    def reset(self, seed=None):
        self.reset_seeds.append(seed)
        self.position = 0
        self.steps = []
        if self.malformed_reset:
            return "bad reset"
        return (
            {"position": 0},
            {"mission": self.mission, "descriptions": ["You are at the start"]},
        )

    def step(self, action_id):
        self.steps.append(action_id)
        self.position += 1
        done = self.done_after is not None and self.position >= self.done_after
        obs = {"position": self.position}
        info = {"descriptions": [f"Position {self.position}"]}
        if self.modern_api:
            return obs, 1 if done else 0, done, False, info
        return obs, 1 if done else 0, done, info

    def __str__(self):
        return "FAKE BACKEND"


def _fresh(*, backend=None, max_turns=20, seed=42, bot_class=None):
    backend = backend or _Backend()
    env = BabyAiTextEnv(
        max_turns=max_turns,
        seed=seed,
        backend=backend,
        bot_class=bot_class,
    )
    env.reset(num_players=1, seed=seed)
    return env


def test_reset_populates_mission():
    env = _fresh()
    assert "mission" in env.state.game_state
    assert "descriptions" in env.state.game_state
    assert env.state.current_player_id == 0


def test_invalid_action_returns_negative_reward():
    env = _fresh()
    done, info = env.step("fly to the moon")  # not in the action space
    assert not done
    assert info["reward"] == -1
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert env.baby_ai_text_env.steps == []


def test_non_text_and_oversized_actions_are_invalid_without_backend_mutation():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(None)
    assert not done
    assert env.game_state == before
    assert env.baby_ai_text_env.steps == []
    env.reset(num_players=1, seed=42)
    done, _ = env.step("x" * (env.max_action_chars + 1))
    assert not done
    assert env.game_state == before
    assert env.baby_ai_text_env.steps == []


def test_valid_action_is_accepted():
    env = _fresh()
    done, info = env.step("  TURN LEFT  ")
    assert not done
    assert info["reward"] == 0
    assert env.game_state["position"] == 1
    assert env.game_state["descriptions"] == ["Position 1"]
    assert env.state.turn == 1


def test_two_invalid_actions_end_with_loss_without_backend_mutation():
    env = _fresh()
    env.step("invalid")
    done, _ = env.step("still invalid")
    assert done
    assert env.state.rewards == {0: -1}
    assert env.state.turn == 0
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.baby_ai_text_env.steps == []


@pytest.mark.parametrize("modern_api", [False, True])
def test_backend_terminal_result_supports_both_gym_apis(modern_api):
    env = _fresh(backend=_Backend(done_after=1, modern_api=modern_api))
    done, info = env.step("go forward")
    assert done
    assert info["reward"] == 1
    assert env.state.rewards == {0: 1}
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def test_backend_truncation_is_reported_as_a_loss():
    class Backend(_Backend):
        def step(self, action_id):
            self.steps.append(action_id)
            self.position += 1
            return (
                {"position": self.position},
                0,
                False,
                True,
                {"descriptions": ["Time expired"]},
            )

    env = _fresh(backend=Backend())
    done, info = env.step("go forward")
    assert done
    assert info["reward"] == -1
    assert env.state.rewards == {0: -1}


def test_malformed_backend_step_is_retryable_and_rolls_back_backend_and_wrapper():
    class Backend(_Backend):
        def step(self, action_id):
            super().step(action_id)
            return {"position": self.position}, 0, False, {"descriptions": [object()]}

    backend = Backend()
    env = _fresh(backend=backend)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("turn left")
    assert not done
    assert env.state.error_count == 0
    assert env.state.turn == 0
    assert env.game_state == before
    assert backend.position == 0
    assert backend.steps == []


def test_malformed_done_flag_is_invalid_and_atomic():
    class Backend(_Backend):
        def step(self, action_id):
            super().step(action_id)
            return {"position": self.position}, 0, "yes", {"descriptions": ["bad flag"]}

    backend = Backend()
    env = _fresh(backend=backend)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("turn left")
    assert not done
    assert env.state.error_count == 0
    assert env.state.turn == 0
    assert env.game_state == before
    assert backend.position == 0


def test_turn_limit_is_a_loss():
    env = _fresh(backend=_Backend(done_after=None), max_turns=2)
    env.step("turn left")
    done, info = env.step("turn right")
    assert done
    assert info["reward"] == -1
    assert env.state.rewards == {0: -1}
    assert env.state.turn == 2


def test_reset_forwards_seed_and_restores_fresh_backend_state():
    backend = _Backend()
    env = _fresh(backend=backend, seed=7)
    env.step("go forward")
    env.reset(num_players=1, seed=11)
    assert backend.reset_seeds == [7, 11]
    assert env.game_state["position"] == 0
    assert backend.steps == []


def test_failed_second_reset_restores_previous_episode_atomically():
    class Backend(_Backend):
        def __init__(self):
            super().__init__()
            self.reset_count = 0

        def reset(self, seed=None):
            self.reset_count += 1
            result = super().reset(seed=seed)
            if self.reset_count == 2:
                self.position = 99
                raise RuntimeError("reset failed")
            return result

    backend = Backend()
    env = _fresh(backend=backend)
    env.step("go forward")
    state_before = env.state
    game_state_before = copy.deepcopy(env.game_state)
    with pytest.raises(RuntimeError, match="backend reset failed"):
        env.reset(num_players=1, seed=9)
    assert env.state is state_before
    assert env.game_state == game_state_before
    assert backend.position == 1
    assert backend.steps == [2]


def test_snapshot_restores_wrapper_and_backend_state():
    backend = _Backend()
    env = _fresh(backend=backend)
    snapshot = env.snapshot()
    assert "baby_ai_text_env" not in snapshot["attributes"]
    expected = copy.deepcopy(env.game_state)
    env.step("go forward")
    env.restore(snapshot)
    assert env.baby_ai_text_env is backend
    assert env.game_state == expected
    assert env.baby_ai_text_env.position == 0
    assert env.baby_ai_text_env.steps == []


def test_snapshot_after_action_replays_backend_transition():
    env = _fresh()
    env.step("go forward")
    snapshot = env.snapshot()
    env.step("turn left")
    expected_state = copy.deepcopy(env.game_state)
    expected_steps = list(env.baby_ai_text_env.steps)
    env.restore(snapshot)
    env.step("turn left")
    assert env.game_state == expected_state
    assert env.baby_ai_text_env.steps == expected_steps


def test_board_and_inventory_are_current_and_pure():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert "Goal: reach the goal" in board
    assert "FAKE GRID" in board
    assert "Inventory: empty" in board
    assert env.game_state == before


def test_gold_path_uses_a_copy_and_returns_text_actions():
    class Bot:
        def __init__(self, backend):
            self.backend = backend

        def replan(self, previous):
            return 0

    backend = _Backend(done_after=1)
    env = _fresh(backend=backend, bot_class=Bot)
    assert env.gold_path() == ["turn left"]
    assert backend.steps == []


def test_missing_optional_dependencies_have_a_clear_error(monkeypatch):
    monkeypatch.setattr(babyai_module, "gym", None)
    monkeypatch.setattr(babyai_module, "babyai_text", None)
    with pytest.raises(ImportError, match="inject a compatible backend"):
        BabyAiTextEnv()


def test_malformed_backend_reset_has_a_clear_error():
    env = BabyAiTextEnv(backend=_Backend(malformed_reset=True))
    with pytest.raises(RuntimeError, match="pair of mappings"):
        env.reset(num_players=1, seed=1)


@pytest.mark.parametrize("max_turns", [0, -1, True])
def test_invalid_turn_limit_is_rejected(max_turns):
    with pytest.raises(ValueError):
        BabyAiTextEnv(max_turns=max_turns, backend=_Backend())


def test_player_bounds_are_enforced():
    env = BabyAiTextEnv(backend=_Backend())
    with pytest.raises(AssertionError):
        env.reset(num_players=0)
    with pytest.raises(AssertionError):
        env.reset(num_players=2)
