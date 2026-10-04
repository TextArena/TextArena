"""Deterministic offline tests for the PegJump (peg solitaire) environment."""
import copy
import re

import pytest

from textarena.envs.PegJump.env import PegJumpEnv


def _fresh(initial_empty=1):
    env = PegJumpEnv(initial_empty=initial_empty)
    env.reset(num_players=1, seed=42)
    return env


def test_scripted_win_one_peg_left():
    env = _fresh()
    # Reduce the board to two pegs (holes 1 & 2) with hole 4 empty; (1,2,4) is legal.
    board = [False] * 16
    board[1] = True
    board[2] = True
    env.state.game_state["board"] = board
    done, _ = env.step("1 4")
    assert done
    assert env.state.rewards == {0: 1.0}
    assert env.state.game_state["board"].count(True) == 1


def test_valid_move_decrements_peg_count():
    env = _fresh()  # 14 pegs, hole 1 empty
    assert env.state.game_state["board"].count(True) == 14
    done, _ = env.step("4 1")  # 4 jumps over 2 into empty 1
    assert not done
    assert env.state.game_state["board"].count(True) == 13


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("jump 4 to 1")
    assert not done
    assert env.state.error_count == 1


def test_illegal_move_from_empty_hole_rejected():
    env = _fresh()  # hole 1 is empty
    done, _ = env.step("1 4")  # source hole 1 has no peg
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalids_end_game():
    env = _fresh()
    done, _ = env.step("nonsense")
    assert not done
    done, _ = env.step("more nonsense")
    assert done
    # No legal jumps were completed, so the opening has no completion credit.
    assert env.state.rewards == {0: 0.0}


def test_completion_tracks_the_thirteen_required_jumps():
    env = _fresh()
    assert env._get_percentage_completion() == 0.0

    env.step("4 1")
    assert env._get_percentage_completion() == pytest.approx(1 / 13)


def test_full_legal_solution_from_standard_opening():
    env = _fresh(initial_empty=1)
    solution = [
        (4, 1), (9, 2), (11, 4), (2, 7), (12, 5), (3, 8), (7, 9),
        (10, 3), (1, 6), (14, 12), (6, 13), (12, 14), (15, 13),
    ]
    for turn, (source, target) in enumerate(solution, start=1):
        done, _ = env.step(f"{source} {target}")
        assert done is (turn == len(solution))
    assert env.state.rewards == {0: 1.0}
    assert env.state.turn == 13
    assert env.state.game_info[0]["turn_count"] == 13


def test_every_configurable_opening_has_a_legal_one_peg_solution():
    moves = PegJumpEnv(initial_empty=1).ALLOWED_MOVES

    def can_solve(mask, memo):
        if bin(mask).count("1") == 1:
            return True
        if mask in memo:
            return memo[mask]
        for source, over, target in moves:
            source_bit = 1 << (source - 1)
            over_bit = 1 << (over - 1)
            target_bit = 1 << (target - 1)
            if mask & source_bit and mask & over_bit and not mask & target_bit:
                next_mask = (mask ^ source_bit ^ over_bit) | target_bit
                if can_solve(next_mask, memo):
                    memo[mask] = True
                    return True
        memo[mask] = False
        return False

    for initial_empty in range(1, 16):
        board_mask = ((1 << 15) - 1) ^ (1 << (initial_empty - 1))
        assert can_solve(board_mask, {})


def test_move_geometry_is_exactly_the_triangular_lattice():
    env = _fresh()
    expected = {
        (1, 2, 4), (1, 3, 6), (2, 4, 7), (2, 5, 9), (3, 5, 8),
        (3, 6, 10), (4, 5, 6), (4, 7, 11), (4, 8, 13), (5, 8, 12),
        (5, 9, 14), (6, 9, 13), (6, 10, 15), (7, 8, 9), (8, 9, 10),
        (11, 12, 13), (12, 13, 14), (13, 14, 15),
    }
    assert set(env._BASE_TRIPLES) == expected
    assert set(env.ALLOWED_MOVES) == expected | {(target, over, source) for source, over, target in expected}


def test_bottom_row_jump_is_legal_and_bent_jump_is_not():
    env = _fresh()
    board = [False] * 16
    board[11] = board[12] = True
    env.state.game_state["board"] = board
    done, _ = env.step("11 13")
    assert done and env.state.game_state["board"][13]

    env = _fresh()
    board = [False] * 16
    board[7] = board[11] = True
    env.state.game_state["board"] = board
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("7 13")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["[4 1", "4 1]", "jump 4 1", "4", "4 1 trailing"])
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_paired_legacy_brackets_remain_valid():
    env = _fresh()
    done, _ = env.step("[4, 1]")
    assert not done
    assert env.state.game_state["board"].count(True) == 13


def test_snapshot_and_repeat_reset_restore_board():
    env = _fresh()
    initial = copy.deepcopy(env.state.game_state)
    snapshot = env.snapshot()
    env.step("4 1")
    env.restore(snapshot)
    assert env.state.game_state == initial

    env.reset(num_players=1, seed=999)
    assert env.state.game_state == initial


@pytest.mark.parametrize("initial_empty", [0, 16, True])
def test_invalid_opening_rejected(initial_empty):
    with pytest.raises(ValueError):
        PegJumpEnv(initial_empty=initial_empty)


@pytest.mark.parametrize("initial_empty", range(1, 16))
def test_prompt_example_is_a_legal_opening_jump(initial_empty):
    env = _fresh(initial_empty=initial_empty)
    _, observation = env.get_observation()
    prompt = observation[0][1]
    example = re.search(r"e\.g\. '(\d+ \d+)'", prompt).group(1)
    done, _ = env.step(example)
    assert not done and env.state.error_count == 0
    assert env.state.game_state["board"].count(True) == 13


def test_render_lists_exactly_the_legal_jumps():
    env = _fresh(initial_empty=5)
    assert "Legal jumps: 12 5, 14 5" in env.render(0)
    for jump in ("12 5", "14 5"):
        probe = _fresh(initial_empty=5)
        probe.step(jump)
        assert probe.state.error_count == 0

    env.state.game_state["board"] = [False] * 16
    env.state.game_state["board"][1] = True
    assert "Legal jumps: none" in env.render(0)


@pytest.mark.parametrize(
    "action,reason",
    [
        ("1 4", "hole 1 has no peg"),
        ("4 6", "hole 6 is not empty"),
        ("4 9", "not two holes away"),
        ("16 14", "numbered 1 to 15"),
    ],
)
def test_illegal_jumps_explain_why(action, reason):
    env = _fresh(initial_empty=1)
    env.get_observation()
    env.step(action)
    _, observation = env.get_observation()
    assert any(reason in message for _, message, _ in observation)
    assert env.state.error_count == 1


def test_last_available_jump_terminates_with_partial_reward():
    env = _fresh()
    board = [False] * 16
    board[1] = board[2] = board[15] = True
    env.state.game_state["board"] = board
    done, _ = env.step("1 4")
    assert done
    assert not env._has_move()
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.rewards[0] == pytest.approx(12 / 13)
