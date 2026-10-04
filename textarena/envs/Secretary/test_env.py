"""Offline deterministic tests for the single-player Secretary problem env."""
import pytest
from textarena.envs.Secretary.env import SecretaryEnv


def _fresh(N=5):
    env = SecretaryEnv(N=N)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["draws"]) == 5
    # reset() already revealed the first value, advancing current_idx to 1.
    assert gs["current_idx"] == 1
    assert not env.state.done


@pytest.mark.parametrize("num_players", [0, 2])
def test_reset_requires_exactly_one_player(num_players):
    with pytest.raises(ValueError):
        SecretaryEnv().reset(num_players=num_players, seed=42)


@pytest.mark.parametrize("N", [0, -1, True, 1.5])
def test_N_must_be_a_positive_integer(N):
    with pytest.raises(ValueError):
        SecretaryEnv(N=N)


def test_only_current_value_is_revealed():
    env = _fresh()
    draws = env.state.game_state["draws"]
    messages = "\n".join(message for _, message, _, _ in env.state.events)
    assert f"{draws[0]:.4f}" in messages
    assert all(f"{value:.4f}" not in messages for value in draws[1:])


def test_accepting_the_maximum_wins():
    env = _fresh()
    draws = env.state.game_state["draws"]
    k = max(range(len(draws)), key=lambda i: draws[i])  # index of the max value
    done = False
    for _ in range(k):  # skip up to (but not including) the max
        done, _ = env.step("continue")
        assert not done
    done, _ = env.step("accept")
    assert done
    assert env.state.rewards == {0: 1.0}
    assert env.state.game_state["accepted_idx"] == k


def test_accepting_non_maximum_loses():
    env = _fresh()
    draws = env.state.game_state["draws"]
    k = min(range(len(draws)), key=lambda i: draws[i])  # index of the min value
    done = False
    for _ in range(k):
        done, _ = env.step("continue")
        assert not done
    done, _ = env.step("accept")
    assert done
    assert env.state.rewards == {0: 0.0}
    assert env.state.game_state["accepted_idx"] == k


def test_forced_to_take_final_value():
    env = _fresh()
    draws = env.state.game_state["draws"]
    # Continue through every value; the env auto-resolves on the final draw.
    done = False
    for _ in range(len(draws)):
        done, _ = env.step("continue")
    assert done
    expected = 1.0 if draws[-1] == max(draws) else 0.0
    assert env.state.rewards == {0: expected}
    assert env.state.game_state["accepted_idx"] == len(draws) - 1


def test_single_draw_continue_forces_acceptance_in_bounds():
    env = _fresh(N=1)
    done, _ = env.step("continue")
    assert done
    assert env.state.game_state["accepted_idx"] == 0
    assert env.state.rewards == {0: 1.0}


def test_actions_are_case_insensitive_but_strict():
    env = _fresh()
    done, _ = env.step("ACCEPT")
    assert done
    assert env.state.game_state["accepted_idx"] == 0


def test_invalid_format_increments_error():
    env = _fresh()
    before_idx = env.state.game_state["current_idx"]
    done, _ = env.step("skip")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_idx"] == before_idx
    assert env.state.game_state["accepted_idx"] is None


def test_repeated_invalid_moves_score_like_a_loss():
    env = _fresh()
    env.step("skip")
    done, _ = env.step("skip")
    assert done
    assert env.state.rewards == {0: 0.0}
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.state.game_info[0]["reason"].startswith("Invalid Move:")


def test_value_messages_state_position_and_flag_the_final_value():
    env = _fresh(N=3)
    draws = env.state.game_state["draws"]
    for position in range(3):
        if position:
            env.step("continue")
        _, observation = env.get_observation()
        text = "\n".join(message for _, message, _ in observation)
        assert f"The current value ({position + 1} of 3) is {draws[position]:.4f}." in text
        assert ("This is the final value" in text) == (position == 2)


@pytest.mark.parametrize("seed", range(20))
def test_draws_are_exactly_the_displayed_values(seed):
    env = SecretaryEnv(N=10)
    env.reset(num_players=1, seed=seed)
    assert all(value == float(f"{value:.4f}") for value in env.state.game_state["draws"])


def test_snapshot_restore_and_repeat_reset_restore_sequence_position():
    env = _fresh()
    original_draws = env.state.game_state["draws"].copy()
    snap = env.snapshot()
    env.step("continue")
    env.restore(snap)
    assert env.state.game_state["current_idx"] == 1
    assert env.state.game_state["accepted_idx"] is None
    env.reset(num_players=1, seed=42)
    assert env.state.game_state["draws"] == original_draws
    assert env.state.game_state["current_idx"] == 1
