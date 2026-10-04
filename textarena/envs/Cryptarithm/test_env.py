"""Deterministic game-logic tests for Cryptarithm (single player)."""
import copy

import pytest

from textarena.envs.Cryptarithm.env import CryptarithmEnv


def _fresh(equation="A + B = C"):
    env = CryptarithmEnv(equation=equation)
    env.reset(num_players=1, seed=42)
    return env


def test_correct_mapping_wins():
    env = _fresh()  # A + B = C  ->  1 + 2 = 3
    for action in ["A 1", "B 2", "C 3"]:
        done, _ = env.step(action)
    assert done and env.state.rewards == {0: 1.0}


def test_complete_but_wrong_mapping_can_be_corrected():
    env = _fresh()
    for action in ["A 1", "B 2", "C 9"]:  # 1 + 2 != 9
        done, _ = env.step(action)
    assert not done
    assert env.state.game_state["mapping"] == {"A": 1, "B": 2, "C": 9}

    done, _ = env.step("C 3")
    assert done and env.state.rewards == {0: 1.0}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("A")  # missing digit
    assert not done and env.state.error_count == 1


def test_letter_not_in_puzzle_rejected():
    env = _fresh()
    done, _ = env.step("Z 1")  # Z is not part of the equation
    assert not done and env.state.error_count == 1


def test_leading_digit_zero_rejected():
    env = _fresh()
    done, _ = env.step("A 0")  # A is a leading letter, cannot be 0
    assert not done and env.state.error_count == 1


def test_duplicate_digit_rejected():
    env = _fresh()
    env.step("A 1")  # valid assignment resets error count
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("B 1")  # digit 1 already used by A
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["[A 1", "A 1]", "A 1 trailing", "A1"])
def test_parser_rejects_noncanonical_actions(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_paired_legacy_brackets_remain_valid():
    env = _fresh()
    done, _ = env.step("[A, 1]")
    assert not done
    assert env.state.game_state["mapping"] == {"A": 1}


@pytest.mark.parametrize(
    "equation",
    [
        "A + B",  # no equals sign
        "A + = B",  # empty addend
        "ABCDEFGHIJ + K = L",  # more than ten letters
        "A + A = A",  # only A=0 works, but leading zero is illegal
    ],
)
def test_invalid_or_unsolvable_equations_are_rejected(equation):
    with pytest.raises(ValueError):
        CryptarithmEnv(equation=equation)


@pytest.mark.parametrize(
    "equation",
    [
        "A" * (CryptarithmEnv.MAX_WORD_LENGTH + 1) + " = A",
        " + ".join(["A"] * (CryptarithmEnv.MAX_ADDENDS + 1)) + " = A",
        "+".join(["A" * 40] * 11) + "=" + "A" * 40,
        " " * (CryptarithmEnv.MAX_EQUATION_LENGTH + 1),
    ],
)
def test_oversized_equations_are_rejected_before_solving(equation):
    with pytest.raises(ValueError):
        CryptarithmEnv(equation=equation)


def test_reset_and_snapshot_restore_independent_state():
    env = _fresh()
    env.step("A 1")
    snapshot = env.snapshot()
    env.step("B 2")
    env.restore(snapshot)

    assert env.state.game_state["mapping"] == {"A": 1}
    env.step("B 2")
    assert env.state.game_state["mapping"] == {"A": 1, "B": 2}

    env.reset(num_players=1, seed=42)
    assert env.state.game_state == {"mapping": {}, "digit_used": {}}


def test_turn_limit_counts_last_action_and_awards_bounded_progress():
    env = CryptarithmEnv(equation="A + B = C", max_turns=1)
    env.reset(num_players=1, seed=42)
    done, _ = env.step("A 1")
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.rewards == {0: 1 / 3}
