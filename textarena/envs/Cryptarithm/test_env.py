"""Deterministic game-logic tests for Cryptarithm (single player)."""
import copy
import re

import pytest

import textarena as ta
from textarena.envs.Cryptarithm.env import CryptarithmEnv
from textarena.envs.registration import ENV_REGISTRY

REGISTERED_IDS = sorted(
    env_id for env_id, spec in ENV_REGISTRY.items()
    if spec.entry_point == "textarena.envs.Cryptarithm.env:CryptarithmEnv"
)
# The only solution of SEND + MORE = MONEY: 9567 + 1085 = 10652.
MONEY = {"S": 9, "E": 5, "N": 6, "D": 7, "M": 1, "O": 0, "R": 8, "Y": 2}


def _fresh(equation="A + B = C"):
    env = CryptarithmEnv(equation=equation)
    env.reset(num_players=1, seed=42)
    return env


def _play_then_two_invalid_moves(env, actions):
    for action in actions:
        done, _ = env.step(action)
        assert not done and env.state.error_count == 0
    env.step("Z 1")
    done, _ = env.step("Z 2")
    assert done
    return env.state.rewards[0]


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


def test_invalid_move_reports_reason_and_escalation_awards_progress():
    env = _fresh()
    env.step("A 1")
    before = len(env.state.events)
    done, _ = env.step("Z 1")
    assert not done
    new_events = env.state.events[before:]
    assert any(event[:3] == (0, "Z 1", ta.ObservationType.PLAYER_ACTION) for event in new_events)
    assert any(
        kind == ta.ObservationType.GAME_ADMIN and "Letter Z not in puzzle." in message
        for _, message, kind, _ in new_events
    )

    done, _ = env.step("Z 2")  # second consecutive invalid move escalates
    assert done
    assert env.state.rewards == {0: 1 / 3}
    assert env.state.game_info[0]["reason"] == "Invalid Move: Letter Z not in puzzle."


def test_clearing_a_letter_lets_a_full_ten_letter_mapping_be_corrected():
    env = _fresh("SATURN + URANUS + NEPTUNE + PLUTO = PLANETS")
    solution = {"A": 2, "E": 9, "L": 6, "N": 3, "O": 8, "P": 4, "R": 0, "S": 1, "T": 7, "U": 5}
    wrong = dict(solution, A=7, T=2)  # every digit is now in use
    for letter, digit in wrong.items():
        done, _ = env.step(f"{letter} {digit}")
        assert not done
    assert env.state.error_count == 0

    done, _ = env.step("A -")
    assert not done and env.state.error_count == 0
    assert "A" not in env.game_state["mapping"] and 7 not in env.game_state["digit_used"]
    done, _ = env.step("T 7")
    assert not done
    done, _ = env.step("[a, 2]")
    assert done and env.state.rewards == {0: 1.0}


def test_clearing_an_unassigned_letter_is_invalid_and_atomic():
    env = _fresh()
    env.step("A 1")
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("B -")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_prompt_states_the_puzzle_rules_and_a_legal_example():
    env = CryptarithmEnv()  # SEND + MORE = MONEY, which has no letter A
    env.reset(num_players=1, seed=0)
    prompt = env.prompt(0)
    assert "SEND + MORE = MONEY" in prompt
    assert "cannot be 0 (here: M, S)" in prompt
    assert "You have 100 moves." in prompt
    example = re.search(r"e\.g\. '([^']+)'", prompt).group(1)
    done, _ = env.step(example)
    assert not done and env.state.error_count == 0 and len(env.state.game_state["mapping"]) == 1


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


def test_arbitrary_assignments_earn_nothing():
    env = _fresh("SEND + MORE = MONEY")
    wrong = {"S": 1, "E": 2, "N": 3, "D": 4, "M": 5, "O": 6, "R": 7}  # 7 of 8 letters, none correct
    assert not any(MONEY[letter] == digit for letter, digit in wrong.items())
    assert _play_then_two_invalid_moves(env, [f"{l} {d}" for l, d in wrong.items()]) == 0


def test_partial_credit_counts_correct_letters():
    env = _fresh("SEND + MORE = MONEY")
    assert _play_then_two_invalid_moves(env, ["S 9", "M 1", "O 0", "E 4"]) == pytest.approx(3 / 8)


def test_complete_but_wrong_mapping_earns_its_correct_letters():
    env = _fresh("SEND + MORE = MONEY")
    swapped = dict(MONEY, R=MONEY["Y"], Y=MONEY["R"])
    assert _play_then_two_invalid_moves(env, [f"{l} {d}" for l, d in swapped.items()]) == pytest.approx(6 / 8)


@pytest.mark.parametrize(
    "actions,expected",
    [
        (["A 1", "B 5"], 2 / 3),  # 1 + 5 = 6
        (["A 1", "B 2", "C 9"], 2 / 3),  # 1 + 2 = 3 matches A and B
        (["A 5", "B 7"], 1 / 3),  # no solution has both; 5 + 1 = 6 and 1 + 7 = 8 each match one
        (["C 2"], 0),  # the sum of two different nonzero digits is at least 3
    ],
)
def test_best_matching_solution_counts_when_there_are_several(actions, expected):
    env = _fresh("A + B = C")
    assert _play_then_two_invalid_moves(env, actions) == pytest.approx(expected)


def test_assigning_and_clearing_a_letter_earns_nothing():
    env = CryptarithmEnv(max_turns=4)
    env.reset(num_players=1, seed=0)
    for action in ["S 9", "S -", "S 9", "S -"]:
        done, _ = env.step(action)
    assert done and env.state.game_info[0]["reason"] == "Move limit reached."
    assert env.state.rewards == {0: 0}


def test_board_shows_how_many_letters_are_assigned_not_how_many_are_correct():
    env = _fresh("SEND + MORE = MONEY")
    for action in ["S 1", "E 2", "N 3", "D 4", "M 5", "O 6", "R 7"]:
        env.step(action)
    assert env.render(0).endswith("Assigned: 7/8 (88%)")
    env.step("Y 8")
    assert env.render(0).endswith("Assigned: 8/8 (100%)")
