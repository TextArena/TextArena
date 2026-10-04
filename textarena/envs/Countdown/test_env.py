"""Deterministic game-logic tests for Countdown (single player)."""
import copy

import pytest

from textarena.envs.Countdown.env import CountdownEnv


def _fresh(numbers=None, target=6):
    # Passing numbers/target avoids seed-dependent randomness.
    env = CountdownEnv(numbers=numbers if numbers is not None else [2, 3], target=target)
    env.reset(num_players=1, seed=42)
    return env


def test_exact_target_wins():
    env = _fresh(numbers=[2, 3], target=6)
    done, _ = env.step("0 1 *")  # 2 * 3 = 6
    assert done and env.state.rewards == {0: 1.0}
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def test_valid_move_reduces_number_pool():
    env = _fresh(numbers=[10, 4, 2], target=999)
    done, _ = env.step("0 1 +")  # 10 + 4 = 14, pool shrinks 3 -> 2
    assert not done and len(env.numbers) == 2


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("0 1")  # missing operator
    assert not done and env.state.error_count == 1


def test_illegal_same_index_rejected():
    env = _fresh()
    done, _ = env.step("0 0 +")  # indices must differ
    assert not done and env.state.error_count == 1


def test_non_integer_division_rejected():
    env = _fresh(numbers=[2, 3], target=6)
    done, _ = env.step("1 0 /")  # 3 / 2 is not an integer
    assert not done and env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("0 0 +")  # second consecutive invalid
    assert done and env.state.game_info[0]["invalid_move"] is True


def test_bracketed_and_bare_actions_have_the_same_result():
    bare = _fresh(numbers=[2, 3, 4], target=99)
    bracketed = _fresh(numbers=[2, 3, 4], target=99)
    bare.step("0 1 +")
    bracketed.step("[0 1 +]")
    assert bare.game_state == bracketed.game_state


@pytest.mark.parametrize("action", ["[0 1 +", "0 1 +]"])
def test_unmatched_brackets_are_rejected_atomically(action):
    env = _fresh(numbers=[2, 3, 4], target=99)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(action)
    assert not done
    assert env.state.turn == 0
    assert env.game_state == before


def test_parser_rejects_trailing_text_atomically():
    env = _fresh(numbers=[2, 3, 4], target=99)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("0 1 + please")
    assert not done
    assert env.state.turn == 0
    assert env.game_state == before


def test_division_by_generated_zero_is_rejected_atomically():
    env = _fresh(numbers=[2, 2, 1], target=99)
    env.step("0 1 -")
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("0 1 /")
    assert not done
    assert env.game_state == before
    assert env.state.turn == 1


def test_non_text_action_and_oversized_result_are_rejected_atomically():
    env = _fresh(numbers=[1_000_000, 1], target=5)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(None)
    assert not done
    assert env.game_state == before
    env.reset(num_players=1, seed=42)
    done, _ = env.step("0 1 +")
    assert not done
    assert env.game_state == before


def test_exhausting_numbers_uses_best_historical_value():
    env = _fresh(numbers=[10, 4], target=20)
    done, _ = env.step("0 1 +")
    assert done
    assert env.game_state["best_value"] == 14
    assert env.state.rewards == {0: pytest.approx(0.994)}


def test_turn_limit_records_only_completed_valid_turns():
    env = CountdownEnv(numbers=[2, 3, 4], target=99, max_turns=1)
    env.reset(num_players=1, seed=42)
    done, _ = env.step("0 1 +")
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def test_reset_snapshot_and_render_are_fresh_and_pure():
    configured = [2, 3, 4]
    env = CountdownEnv(numbers=configured, target=99)
    configured[0] = 999
    env.reset(num_players=1, seed=1)
    assert env.numbers == [2, 3, 4]
    snapshot = env.snapshot()
    before = copy.deepcopy(env.game_state)
    rendered = env.render(0)
    assert "TARGET: 99" in rendered
    assert env.game_state == before
    env.step("0 1 +")
    env.restore(snapshot)
    assert env.game_state == before
    env.reset(num_players=1, seed=1)
    assert env.numbers == [2, 3, 4]


def test_seeded_generation_is_isolated_and_deterministic():
    first = CountdownEnv()
    second = CountdownEnv()
    first.reset(num_players=1, seed=7)
    second.reset(num_players=1, seed=7)
    assert first.orig_numbers == second.orig_numbers
    assert first.target == second.target


@pytest.mark.parametrize(
    "kwargs",
    [
        {"numbers": []},
        {"numbers": [1]},
        {"numbers": [1, 0]},
        {"numbers": [1, True]},
        {"numbers": [1_000_001, 1]},
        {"target": 0},
        {"target": 1_000_001},
        {"max_turns": 0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        CountdownEnv(**kwargs)


def test_player_bounds_are_enforced():
    env = CountdownEnv(numbers=[2, 3], target=6)
    with pytest.raises(AssertionError):
        env.reset(num_players=0)
    with pytest.raises(AssertionError):
        env.reset(num_players=2)
