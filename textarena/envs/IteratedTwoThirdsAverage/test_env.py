"""Deterministic offline tests for IteratedTwoThirdsAverage.

Two-player game. Each round both players guess a number; target = (2/3)*avg,
closest guess wins the round. After ``num_rounds`` the player with more round
wins takes the game (winner {w:1, l:-1}; draw {0:0, 1:0}).
"""

import pytest
import textarena as ta

from textarena.envs.IteratedTwoThirdsAverage.env import IteratedTwoThirdsAverageEnv


def _fresh(num_rounds=1, **kwargs):
    env = IteratedTwoThirdsAverageEnv(num_rounds=num_rounds, **kwargs)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.state.done is False
    assert env.state.game_state["round"] == 1
    assert env.state.rewards is None


def test_player0_wins_single_round():
    # g0=10, g1=20 -> avg=15, target=10 -> P0 exact, P0 wins.
    env = _fresh(num_rounds=1)
    done, _ = env.step("10")
    assert done is False
    assert env.state.current_player_id == 1  # rotated to P1
    done, _ = env.step("20")
    assert done is True
    assert env.state.rewards == {0: 1, 1: -1}


def test_player1_wins_single_round():
    # g0=20, g1=10 -> avg=15, target=10 -> P1 exact, P1 wins.
    env = _fresh(num_rounds=1)
    env.step("20")
    done, _ = env.step("10")
    assert done is True
    assert env.state.rewards == {0: -1, 1: 1}


def test_draw_equal_guesses():
    # Equal guesses -> equal distance -> round draw -> overall draw.
    env = _fresh(num_rounds=1)
    env.step("50")
    done, _ = env.step("50")
    assert done is True
    assert env.state.rewards == {0: 0, 1: 0}


def test_invalid_format_then_recover():
    env = _fresh(num_rounds=1)
    done, _ = env.step("not a number")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # no rotation on invalid
    # Valid resubmission proceeds.
    done, _ = env.step("10")
    assert done is False
    assert env.state.current_player_id == 1


def test_out_of_range_guess_rejected():
    env = _fresh(num_rounds=1)
    done, _ = env.step("200")  # max_guess=100
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_second_consecutive_invalid_loses():
    env = _fresh(num_rounds=1)
    env.step("garbage")
    done, _ = env.step("still garbage")
    assert done is True
    # Offender is P0; invalid-move escalation gives the opponent the win.
    assert env.state.rewards == {0: -1, 1: 1}


def test_two_round_game_p0_sweeps():
    # P0 wins both rounds -> overall winner P0.
    env = _fresh(num_rounds=2)
    # round 1: P0 exact
    env.step("10")
    env.step("20")
    assert env.state.done is False
    assert env.state.game_state["round"] == 2
    # round 2: P0 exact again
    env.step("10")
    done, _ = env.step("20")
    assert done is True
    assert env.state.rewards == {0: 1, 1: -1}


def test_negative_decimal_and_exponent_guesses_supported_by_bounds():
    env = _fresh(min_guess=-10, max_guess=10)
    env.step("-1e0")
    done, _ = env.step("+1.0")
    assert done
    assert env.state.game_state["history"] == [{0: -1.0, 1: 1.0}]
    assert env.state.rewards == {0: 0, 1: 0}


def test_tiny_distinct_distances_do_not_collapse_to_a_draw():
    env = _fresh(min_guess=0, max_guess=1)
    env.step("0")
    done, _ = env.step("1e-13")
    assert done
    assert env.state.game_state["points"] == {0: 1, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_subnormal_distances_do_not_underflow_to_a_draw():
    env = _fresh(min_guess=0, max_guess=5e-324)
    env.step("0")
    done, _ = env.step("5e-324")
    assert done
    assert env.state.game_state["points"] == {0: 1, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_extreme_finite_guesses_do_not_overflow_target_math():
    env = _fresh(min_guess=0, max_guess=1e308)
    env.step("9e307")
    done, _ = env.step("1e308")
    assert done
    assert env.state.game_state["points"] == {0: 1, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_round_results_report_running_score_to_both_players():
    env = _fresh(num_rounds=3)
    env.step("10"); env.step("20")  # target 10 -> P0
    env.step("50"); env.step("50")  # draw
    for pid in (0, 1):
        messages = [message for _, message, _ in env.state.observations[pid]]
        assert "Score after round 1/3: Player 0 1, Player 1 0." in messages
        assert "Round is a draw." in messages
        assert "Score after round 2/3: Player 0 1, Player 1 0." in messages


def test_prompt_states_how_the_game_is_won():
    assert "The player who wins more rounds wins the game; equal round wins is a draw." in _fresh().prompt(1)


def test_pending_guess_is_hidden_and_duplicate_is_atomic():
    env = _fresh()
    env.step("17")
    assert not any(
        event[0] == 0 and event[2] == ta.ObservationType.PLAYER_ACTION
        for event in env.state.events
    )
    assert "17" not in env.get_board_str()

    result = env.apply(0, "9")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state["guesses"] == {0: 17.0}


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_guess_is_rejected_atomically(player_id):
    env = _fresh()
    before = env.state.game_state.copy()
    result = env.apply(player_id, "17")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_terminal_state_keeps_last_round_and_turn_count():
    env = _fresh()
    env.step("10")
    done, _ = env.step("20")
    assert done
    assert env.state.game_state["round"] == 1
    assert env.state.turn == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_guess": float("nan")},
        {"max_guess": float("inf")},
        {"max_guess": 10**1000},
        {"min_guess": 2, "max_guess": 1},
        {"num_rounds": 10**5000},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        IteratedTwoThirdsAverageEnv(**kwargs)
