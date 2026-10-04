"""Deterministic offline tests for the PigDice environment.

The per-environment RNG is seeded at reset. With seed=42 the die roll sequence is:
    6, 1, 1, 6, 3, 2, ...
which lets us script exact roll/hold outcomes.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.PigDice.env import PigDiceEnv


def _fresh(winning_score=100, max_turns=500):
    env = PigDiceEnv(winning_score=winning_score, max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def test_roll_then_hold_wins():
    env = _fresh(winning_score=6)
    done, _ = env.step("roll")     # rolls a 6 -> turn total 6
    assert not done
    assert env.state.game_state["turn_total"] == 6
    done, _ = env.step("hold")     # banks 6 >= winning_score
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_bust_rolls_one_rotates_player():
    env = _fresh()
    env.step("roll")               # 6
    assert env.state.current_player_id == 0
    done, _ = env.step("roll")     # 1 -> bust, turn ends
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["turn_total"] == 0


def test_roll_results_are_recorded_in_public_game_history():
    env = _fresh()

    env.step("roll")  # 6
    env.step("roll")  # 1

    roll_events = [
        message
        for _, message, event_type, to_id in env.state.events
        if event_type == ta.ObservationType.GAME_ACTION_DESCRIPTION
        and message.startswith("Player 0 rolled")
    ]
    assert roll_events == ["Player 0 rolled a 6.", "Player 0 rolled a 1."]
    assert all(
        to_id == -1
        for _, message, event_type, to_id in env.state.events
        if event_type == ta.ObservationType.GAME_ACTION_DESCRIPTION
        and message.startswith("Player 0 rolled")
    )


def test_hold_banks_points_and_rotates():
    env = _fresh()
    env.step("roll")               # 6
    done, _ = env.step("hold")     # bank 6
    assert not done
    assert env.state.game_state["scores"][0] == 6
    assert env.state.current_player_id == 1


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("jump")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("jump")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert "either 'roll'" in env.action_format and "or 'hold'" in env.action_format
    for action in ("roll", "hold"):
        fresh = _fresh()
        fresh.step(action)
        assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_two_consecutive_invalids_end_game():
    env = _fresh()
    done, _ = env.step("nonsense")
    assert not done
    done, _ = env.step("nonsense again")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


@pytest.mark.parametrize("winning_score", (0, -1, 1.5, True))
def test_invalid_winning_scores_are_rejected(winning_score):
    with pytest.raises(ValueError):
        PigDiceEnv(winning_score=winning_score)


@pytest.mark.parametrize("max_turns", (0, -1, 1.5, True, None))
def test_invalid_turn_limits_are_rejected(max_turns):
    with pytest.raises(ValueError):
        PigDiceEnv(max_turns=max_turns)


@pytest.mark.parametrize("action", ("[roll", "roll]"))
def test_unbalanced_brackets_are_atomic_invalid_moves(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before
    assert env.roll_value is None


def test_balanced_case_insensitive_action_is_accepted():
    env = _fresh()

    done, _ = env.step("[ROLL]")

    assert not done
    assert env.state.game_state["turn_total"] == 6
    assert env.state.current_player_id == 0


def test_huge_invalid_action_is_atomic_and_does_not_consume_rng():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step("r" * 100_000)

    assert not done
    assert env.state.game_state == before
    assert env.roll_value is None

    done, _ = env.step("roll")

    assert not done
    assert env.state.game_state["turn_total"] == 6


def test_end_turn_clears_roll_state_on_bust_and_hold():
    env = _fresh()
    env.step("roll")  # 6
    env.step("roll")  # 1, bust

    assert env.roll_value is None
    assert env.state.game_state["turn_total"] == 0
    assert env.state.game_state["turn_rolls"] == []

    env.step("roll")  # Player 1 rolls 1 and busts immediately.
    assert env.roll_value is None
    assert env.state.game_state["turn_rolls"] == []


def test_winning_hold_clears_turn_state_and_renders_final_scores():
    env = _fresh(winning_score=6)
    env.step("roll")

    done, _ = env.step("hold")

    assert done
    assert env.state.turn == 2
    assert env.state.game_state == {
        "scores": [6, 0],
        "turn_total": 0,
        "turn_rolls": [],
    }
    assert env.roll_value is None
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert "Player 0: '6'" in final_board
    assert "turn total is 0" in final_board


def test_reset_clears_last_roll_and_all_game_state():
    env = _fresh()
    env.step("roll")
    assert env.roll_value == 6

    env.reset(num_players=2, seed=42)

    assert env.roll_value is None
    assert env.state.game_state == {
        "scores": [0, 0],
        "turn_total": 0,
        "turn_rolls": [],
    }
    assert env.state.current_player_id == 0


def test_board_renderer_uses_configured_goal():
    env = _fresh(winning_score=6)

    board = env.get_board_str()

    assert "Goal: 6 points" in board
    assert "Goal: 100 points" not in board


def test_exact_action_limit_uses_only_banked_scores():
    env = _fresh(max_turns=1)
    env.state.game_state["scores"] = [5, 0]

    done, _ = env.step("roll")  # unbanked 6 does not alter the score

    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.game_state["scores"] == [5, 0]
    assert env.state.game_state["turn_total"] == 6
    assert env.state.rewards == {0: 1, 1: -1}


def test_exact_action_limit_draws_tied_scores():
    env = _fresh(max_turns=1)

    done, _ = env.step("roll")

    assert done
    assert env.state.turn == 1
    assert env.state.game_state["scores"] == [0, 0]
    assert env.state.rewards == {0: 0, 1: 0}


def test_snapshot_restores_rng_state_and_environment_attributes():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("roll")
    assert env.roll_value == 6

    env.restore(snapshot)
    done, _ = env.step("roll")

    assert not done
    assert env.roll_value == 6
    assert env.state.game_state["turn_total"] == 6
