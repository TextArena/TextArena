"""Offline, deterministic tests for the Sudoku environment.

Sudoku is a single-player puzzle. The full solution is stored on the env as
``env.full_grid`` and the (partially filled) starting board as ``env.game_board``,
so we can script a guaranteed win by filling every empty cell with the correct
digit. We use a high clue count (few empty cells) to keep the test fast.
Moves use 1-indexed bare ``row col number``.
"""
import copy
import random

import pytest

from textarena.envs.Sudoku.env import SudokuEnv


def _fresh(clues: int = 70, max_turns: int = 200):
    env = SudokuEnv(clues=clues, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _empty_cells(env):
    return [(i, j) for i in range(9) for j in range(9) if env.game_board[i][j] == 0]


def test_reset_structure():
    env = _fresh()
    assert len(env.game_board) == 9 and all(len(r) == 9 for r in env.game_board)
    assert env.state.game_state["completed"] is False
    # The starting board is a strict subset of the full solution.
    for i in range(9):
        for j in range(9):
            if env.game_board[i][j] != 0:
                assert env.game_board[i][j] == env.full_grid[i][j]


@pytest.mark.parametrize("clues", [70, 40, 30, 20])
def test_generator_produces_exact_requested_clue_count(clues):
    env = _fresh(clues=clues)
    assert sum(cell != 0 for row in env.game_board for cell in row) == clues


@pytest.mark.parametrize("seed", range(50))
def test_generated_boards_are_valid_and_deterministic(seed):
    first = SudokuEnv(clues=17)
    second = SudokuEnv(clues=17)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert first.game_state == second.game_state
    expected = set(range(1, 10))
    assert all(set(row) == expected for row in first.full_grid)
    assert all(
        {first.full_grid[row][col] for row in range(9)} == expected
        for col in range(9)
    )
    for box_row in range(0, 9, 3):
        for box_col in range(0, 9, 3):
            assert {
                first.full_grid[row][col]
                for row in range(box_row, box_row + 3)
                for col in range(box_col, box_col + 3)
            } == expected


def test_reset_does_not_consume_global_rng():
    random.seed(551)
    expected = random.getstate()
    _fresh()
    assert random.getstate() == expected


def test_full_solution_wins():
    env = _fresh()
    empties = _empty_cells(env)
    assert empties, "expected at least one empty cell to fill"
    done = False
    for (i, j) in empties:
        num = env.full_grid[i][j]
        done, _ = env.step(f"{i + 1} {j + 1} {num}")
    assert done
    assert env.state.game_state["completed"] is True
    assert env.state.rewards == {0: 1}


def test_bad_format_is_invalid():
    env = _fresh()
    done, _ = env.step("row 1 col 1 = 5")
    assert not done
    assert env.state.error_count == 1


def test_out_of_bounds_rejected():
    env = _fresh()
    done, _ = env.step("10 10 5")
    assert not done
    assert env.state.error_count == 1


def test_overwrite_prefilled_rejected():
    env = _fresh()
    # Find a pre-filled cell and attempt to write to it.
    filled = next((i, j) for i in range(9) for j in range(9) if env.game_board[i][j] != 0)
    i, j = filled
    done, _ = env.step(f"{i + 1} {j + 1} {env.full_grid[i][j]}")
    assert not done
    assert env.state.error_count == 1


def test_wrong_number_rejected():
    env = _fresh()
    (i, j) = _empty_cells(env)[0]
    correct = env.full_grid[i][j]
    wrong = 1 if correct != 1 else 2
    done, _ = env.step(f"{i + 1} {j + 1} {wrong}")
    assert not done
    assert env.state.error_count == 1
    # Board must not have been mutated by the rejected move.
    assert env.state.game_state["board"][i][j] == 0


@pytest.mark.parametrize("brackets", ["left", "right"])
def test_mismatched_brackets_are_invalid_and_atomic(brackets):
    env = _fresh()
    row, col = _empty_cells(env)[0]
    number = env.full_grid[row][col]
    action = (
        f"[{row + 1} {col + 1} {number}"
        if brackets == "left"
        else f"{row + 1} {col + 1} {number}]"
    )
    before = copy.deepcopy(env.game_state["board"])
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["board"] == before
    assert env.state.turn == 0


def test_matched_brackets_are_accepted():
    env = _fresh()
    row, col = _empty_cells(env)[0]
    number = env.full_grid[row][col]
    env.step(f"[{row + 1} {col + 1} {number}]")
    assert env.game_state["board"][row][col] == number


def test_oversized_numeric_action_is_invalid_without_mutation():
    env = _fresh()
    before = copy.deepcopy(env.game_state["board"])
    done, _ = env.step(f"{'9' * env.max_action_chars} 1 1")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["board"] == before


def test_runtime_renderer_reflects_moves_and_uses_numeric_rows():
    env = _fresh()
    i, j = _empty_cells(env)[0]
    before = env.get_board_str()

    env.step(f"{i + 1} {j + 1} {env.full_grid[i][j]}")
    after = env.get_board_str()

    assert after != before
    assert "A" not in after
    assert "\n1" in after


def test_turn_limit_scores_only_player_filled_cells():
    env = _fresh(clues=70, max_turns=1)
    row, col = _empty_cells(env)[0]
    done, _ = env.step(f"{row + 1} {col + 1} {env.full_grid[row][col]}")
    assert done
    assert env.state.rewards == {0: pytest.approx(1 / 11)}
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


def test_snapshot_restore_recovers_live_board_without_aliasing_initial_board():
    env = _fresh()
    snapshot = env.snapshot()
    row, col = _empty_cells(env)[0]
    env.step(f"{row + 1} {col + 1} {env.full_grid[row][col]}")
    assert env.game_state["board"][row][col] != env.game_board[row][col]
    env.restore(snapshot)
    assert env.game_state["board"][row][col] == 0
    assert env.game_board[row][col] == 0
    assert env.get_board_str() in env.render(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"clues": 16},
        {"clues": 81},
        {"clues": 17.5},
        {"clues": True},
        {"max_turns": 0},
        {"max_turns": True},
        {"max_turns": None},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SudokuEnv(**kwargs)
