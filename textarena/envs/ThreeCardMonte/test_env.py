"""Offline, deterministic tests for the Three-Card Monte environment.

Single-player game: cups are shuffled up-front (deterministically from the seed)
and the player guesses the final ball location with the cup number. The final ball
position is stored on the env as ``env.ball_pos`` after ``reset``, so we can
script both a correct guess (reward 1.0) and a wrong guess (reward 0.0).
"""

import pytest
from textarena.envs.ThreeCardMonte.env import ThreeCardMonteEnv


def _fresh(num_cups=3, steps=10):
    env = ThreeCardMonteEnv(num_cups=num_cups, steps=steps)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_sets_ball_position():
    env = _fresh()
    assert 0 <= env.ball_pos < env.num_cups
    assert env.state.current_player_id == 0
    assert not env.state.done


@pytest.mark.parametrize("num_players", [0, 2])
def test_reset_requires_exactly_one_player(num_players):
    with pytest.raises(AssertionError):
        ThreeCardMonteEnv().reset(num_players=num_players, seed=42)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_cups": 2},
        {"num_cups": True},
        {"steps": -1},
        {"steps": 1.5},
    ],
)
def test_constructor_rejects_invalid_bounds(kwargs):
    with pytest.raises(ValueError):
        ThreeCardMonteEnv(**kwargs)


def test_reset_emits_exact_shuffle_count_without_revealing_final_ball():
    env = _fresh(steps=4)
    messages = [message for _, message, _, _ in env.state.events]
    assert len([message for message in messages if message.startswith("Shuffle ")]) == 4
    assert not any("[X]" in message for message in messages if message.startswith("Cups:"))


def test_correct_guess_reward_one():
    env = _fresh()
    done, _ = env.step(str(env.ball_pos))
    assert done
    assert env.state.rewards == {0: 1.0}


def test_wrong_guess_reward_zero():
    env = _fresh()
    wrong = (env.ball_pos + 1) % env.num_cups
    done, _ = env.step(str(wrong))
    assert done
    assert env.state.rewards == {0: 0.0}


def test_bad_format_first_invalid_not_terminal():
    env = _fresh()
    done, _ = env.step("cup number two please")
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_guess_first_invalid_not_terminal():
    env = _fresh()
    done, _ = env.step(str(env.num_cups + 5))
    assert not done
    assert env.state.error_count == 1


def test_huge_numeric_guess_is_invalid_without_integer_conversion_crash():
    env = _fresh()
    before = env.ball_pos
    done, _ = env.step("9" * 10_000)
    assert not done
    assert env.ball_pos == before
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_second_invalid_move_ends_game_with_numeric_zero_reward():
    env = _fresh()
    done, _ = env.step("cup number two please")
    assert not done
    done, _ = env.step("still not a guess")
    assert done
    assert isinstance(env.state.rewards[0], float)
    assert env.state.rewards == {0: 0.0}


def test_repeat_reset_and_snapshot_restore_rng_state():
    env = _fresh(num_cups=5, steps=7)
    first_ball = env.ball_pos
    snap = env.snapshot()
    env.step(str((first_ball + 1) % env.num_cups))
    env.restore(snap)
    assert not env.state.done
    assert env.ball_pos == first_ball
    env.reset(num_players=1, seed=42)
    assert env.ball_pos == first_ball
