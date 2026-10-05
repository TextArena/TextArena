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
    with pytest.raises(ValueError):
        ThreeCardMonteEnv().reset(num_players=num_players, seed=42)


def test_reset_emits_exact_shuffle_count_without_revealing_final_ball():
    env = _fresh(steps=4)
    messages = [message for _, message, _, _ in env.state.events]
    assert len([message for message in messages if message.startswith("Shuffle ")]) == 4
    assert not any("[X]" in message for message in messages if message.startswith("Cups:"))


def test_correct_guess_reward_one():
    env = _fresh()
    done = env.step(str(env.ball_pos))
    assert done
    assert env.state.rewards == {0: 1.0}


def test_wrong_guess_reward_zero():
    env = _fresh()
    wrong = (env.ball_pos + 1) % env.num_cups
    done = env.step(str(wrong))
    assert done
    assert env.state.rewards == {0: 0.0}


def test_bad_format_first_invalid_not_terminal():
    env = _fresh()
    done = env.step("cup number two please")
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_guess_first_invalid_not_terminal():
    env = _fresh()
    done = env.step(str(env.num_cups + 5))
    assert not done
    assert env.state.error_count == 1


def test_second_invalid_move_ends_game_with_numeric_zero_reward():
    env = _fresh()
    done = env.step("cup number two please")
    assert not done
    done = env.step("still not a guess")
    assert done
    assert isinstance(env.state.rewards[0], float)
    assert env.state.rewards == {0: 0.0}
