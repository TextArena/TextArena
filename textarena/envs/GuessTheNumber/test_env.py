"""Deterministic game-logic tests for GuessTheNumber-v0 (single player).

The target is drawn randomly at reset, so we read it out of the game
state to build deterministic scripted plays rather than hardcoding a value.
"""
import copy
import math

import pytest

import textarena as ta
from textarena.envs.GuessTheNumber.env import GuessTheNumberEnv


def _fresh(**kwargs):
    env = GuessTheNumberEnv(**kwargs)
    env.reset(num_players=1, seed=42)
    return env


def test_correct_guess_wins():
    env = _fresh()
    target = env.state.game_state["game_number"]
    done, _ = env.step(str(target))
    assert done
    assert env.state.rewards[0] == 1


def test_correct_guess_on_last_allowed_turn_wins():
    env = _fresh(min_number=7, max_number=7, max_turns=1)
    done, _ = env.step("7")
    assert done
    assert env.state.turn == 1
    assert env.state.rewards == {0: 1}


def test_wrong_guess_gives_hint_and_continues():
    env = _fresh()
    target = env.state.game_state["game_number"]
    wrong = target + 1 if target < env.max_number else target - 1
    done, _ = env.step(str(wrong))
    assert not done
    assert len(env.state.game_state["guess_history"]) == 1
    _, hint = env.state.game_state["guess_history"][-1]
    assert hint in ("higher", "lower")


def test_hint_direction_is_correct():
    env = _fresh()
    target = env.state.game_state["game_number"]
    if target > env.min_number:
        env.step(str(env.min_number))  # guess below target
        assert env.state.game_state["guess_history"][-1][1] == "higher"


def test_out_of_range_guess_is_invalid():
    env = _fresh()
    done, _ = env.step(str(env.max_number + 5))
    assert not done
    assert env.state.error_count == 1


def test_bad_format_is_invalid():
    env = _fresh()
    done, _ = env.step("I think it is seven")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_number": 5, "max_number": 4, "max_turns": 3},
        {"min_number": 1.5, "max_number": 4, "max_turns": 3},
        {"min_number": 1, "max_number": 4, "max_turns": 0},
        {"min_number": True, "max_number": 4, "max_turns": 3},
    ],
)
def test_invalid_bounds_are_rejected(kwargs):
    with pytest.raises(ValueError):
        GuessTheNumberEnv(**kwargs)


def test_negative_and_explicit_positive_guesses_are_parseable():
    env = _fresh(min_number=-2, max_number=-2, max_turns=1)
    done, _ = env.step("-2")
    assert done and env.state.rewards == {0: 1}

    env = _fresh(min_number=2, max_number=2, max_turns=1)
    done, _ = env.step("+2")
    assert done and env.state.rewards == {0: 1}


def test_unicode_decimal_digits_are_parsed_consistently():
    env = _fresh(min_number=12, max_number=12, max_turns=1)
    done, _ = env.step("١٢")
    assert done and env.state.rewards == {0: 1}


def test_correct_guess_is_recorded_in_history_and_renderer():
    env = _fresh()
    target = env.state.game_state["game_number"]
    env.step(str(target))
    assert env.state.game_state["guess_history"] == [(target, "correct")]
    assert f"Target Number: {target}" in env.get_board_str()
    assert "Correct" in env.get_board_str()


def test_renderer_hides_target_during_play():
    env = _fresh(min_number=100, max_number=200)
    target = str(env.state.game_state["game_number"])
    assert f"Target Number: {target}" not in env.get_board_str()
    assert "Target Number: ?" in env.get_board_str()


def test_events_and_snapshot_history_do_not_reveal_live_target():
    env = _fresh(min_number=1000, max_number=9999)
    target = env.state.game_state["game_number"]
    wrong = target + 1 if target < env.max_number else target - 1
    env.step(str(wrong))
    snapshot = env.snapshot()

    for state in (env.state, snapshot["state"]):
        visible_text = "\n".join(
            message
            for _, message, event_type, _ in state.events
            if event_type in {
                ta.ObservationType.PROMPT,
                ta.ObservationType.GAME_MESSAGE,
                ta.ObservationType.GAME_BOARD,
            }
        )
        assert f"Target: {target}" not in visible_text
        assert f"Target Number: {target}" not in visible_text


def test_duplicate_guess_is_atomic():
    env = _fresh()
    target = env.state.game_state["game_number"]
    guess = target + 1 if target < env.max_number else target - 1
    env.step(str(guess))
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(str(guess))
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 1


def test_turn_limit_counts_guesses_exactly():
    env = _fresh(min_number=1, max_number=10, max_turns=2)
    env.state.game_state["game_number"] = 10
    env.step("1")
    done, _ = env.step("2")
    assert done
    assert env.state.turn == 2
    assert len(env.state.game_state["guess_history"]) == 2
    assert 0 <= env.state.rewards[0] <= 1


def test_extremely_large_integer_is_invalid_not_an_exception():
    env = _fresh()
    done, _ = env.step("9" * 5000)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["guess_history"] == []


def test_single_value_range_has_well_defined_completion():
    env = _fresh(min_number=7, max_number=7, max_turns=1)
    env.state.game_state["guess_history"] = [(7, "correct")]
    assert env._get_percentage_completion() == 1.0


def test_extreme_integer_bounds_have_finite_bounded_completion():
    bound = 10**1000
    env = _fresh(min_number=-bound, max_number=bound, max_turns=1)
    env.state.game_state["game_number"] = bound
    env.state.game_state["guess_history"] = [(-bound, "higher")]
    completion = env._get_percentage_completion()
    assert math.isfinite(completion)
    assert completion == 0.0


def test_snapshot_restores_history_and_target():
    env = _fresh()
    target = env.state.game_state["game_number"]
    snapshot = env.snapshot()
    guess = target + 1 if target < env.max_number else target - 1
    env.step(str(guess))
    env.restore(snapshot)
    assert env.state.game_state["game_number"] == target
    assert env.state.game_state["guess_history"] == []
    assert env.state.turn == 0


def test_step_after_terminal_is_idempotent():
    env = _fresh()
    target = env.state.game_state["game_number"]
    env.step(str(target))
    before = copy.deepcopy(env.state.__dict__)
    done, info = env.step(str(target))
    assert done and info == {}
    assert env.state.__dict__ == before
