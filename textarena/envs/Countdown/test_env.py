"""Deterministic game-logic tests for Countdown (single player)."""
import copy

import pytest

import textarena as ta
from textarena.envs.Countdown.env import CountdownEnv
from textarena.envs.registration import ENV_REGISTRY

REGISTERED_IDS = sorted(
    env_id for env_id, spec in ENV_REGISTRY.items() if spec.entry_point == "textarena.envs.Countdown.env:CountdownEnv"
)
REGISTERED_KWARGS = ENV_REGISTRY["Countdown-v0"].kwargs  # numbers 100 75 6 4 3 2, target 532


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
    assert env.state.rewards == {0: pytest.approx((10 - 6) / 10)}  # 10 was 10 away, 14 is 6 away


@pytest.mark.parametrize("env_id", REGISTERED_IDS)
@pytest.mark.parametrize("seed", range(5))
def test_immediate_invalid_policy_scores_zero_on_registered_configs(env_id, seed):
    env = ta.make(env_id)
    env.reset(num_players=1, seed=seed)
    for _ in range(5):
        done, _ = env.step("@@@ not a move @@@")
        if done:
            break
    assert done
    assert env.close()[0] == {0: 0}


@pytest.mark.parametrize("seed", range(10))
def test_immediate_invalid_policy_scores_zero_on_random_draws(seed):
    env = CountdownEnv()
    env.reset(num_players=1, seed=seed)
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done and env.state.rewards == {0: 0}


def test_partial_progress_is_measured_from_the_closest_starting_number():
    env = CountdownEnv(**REGISTERED_KWARGS)
    env.reset(num_players=1, seed=0)
    assert "Current progress score: 0.000" in env.render(0)
    env.step("0 2 *")  # 100 * 6 = 600, 68 away
    env.step("4 0 -")  # 600 - 75 = 525, 7 away
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    # 100 is the closest starting number, 432 away from 532.
    assert env.state.rewards == {0: pytest.approx((432 - 7) / 432)}
    assert 0 < env.state.rewards[0] < 1


def test_values_no_closer_than_the_starting_numbers_score_zero():
    env = CountdownEnv(**REGISTERED_KWARGS, max_turns=2)
    env.reset(num_players=1, seed=0)
    env.step("4 5 +")  # 3 + 2 = 5
    done, _ = env.step("0 1 -")  # 100 - 75 = 25
    assert done and "Turn limit" in env.state.game_info[0]["reason"]
    assert env.state.rewards == {0: 0}


def test_registered_puzzle_solved_still_scores_one():
    env = ta.make("Countdown-v0")
    env.reset(num_players=1, seed=0)
    for action in ["0 1 +", "0 3 /", "0 1 +", "0 1 *", "0 1 +"]:  # 175, 3, 7, 525, 532
        done, _ = env.step(action)
    assert done and env.close()[0] == {0: 1.0}


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


def _invalid_reason(env, action):
    before = len(env.state.events)
    done, _ = env.step(action)
    assert not done
    reasons = [message for _, message, _, _ in env.state.events[before:] if "attempted an invalid move" in message]
    assert len(reasons) == 1
    return reasons[0]


def test_rejected_operations_report_the_actual_reason():
    env = _fresh(numbers=[1000, 1001, 2], target=999)
    assert "results must stay between -1,000,000 and 1,000,000" in _invalid_reason(env, "0 1 *")
    env = _fresh(numbers=[1000, 1001, 2], target=999)
    assert "1001 / 2 is not a whole number." in _invalid_reason(env, "1 2 /")
    env = _fresh(numbers=[2, 2, 1], target=99)
    env.step("0 1 -")
    assert "Division by zero is not allowed." in _invalid_reason(env, "0 1 /")


# Seeds whose first random target equals one of the drawn starting numbers.
@pytest.mark.parametrize("seed", [769, 1936, 3420])
def test_random_target_is_never_a_starting_number(seed):
    env = CountdownEnv()
    env.reset(num_players=1, seed=seed)
    assert env.target not in env.orig_numbers
    assert 100 <= env.target <= 999
    assert env.game_state["best_value"] != env.target


def test_configured_target_is_never_among_random_starting_numbers():
    for seed in range(10):
        env = CountdownEnv(target=100)
        env.reset(num_players=1, seed=seed)
        assert env.target == 100 and 100 not in env.orig_numbers


def test_prompt_states_target_and_limit_and_its_example_is_legal():
    env = CountdownEnv(numbers=[2, 3], target=7, max_turns=5)
    env.reset(num_players=1, seed=0)
    prompt = env.prompt(0)
    assert "target 7" in prompt and "after 5 moves" in prompt and "'0 1 +'" in prompt
    assert "fraction of the starting gap you closed" in prompt
    done, _ = env.step("0 1 +")
    assert done and env.state.error_count == 0 and env.game_state["numbers"] == [5]


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
        {"numbers": [1] * (CountdownEnv.max_numbers + 1)},
        {"numbers": [2, 3], "target": 3},
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
