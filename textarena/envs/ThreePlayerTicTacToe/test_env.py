"""Offline, deterministic tests for the Three-Player Tic Tac Toe environment.

Three players (symbols A/B/C) take turns on a 5x5 board; the first to make a line
of four wins. Player 0 (A) claims cells 0,1,2,3 (top row) while players 1 and 2
play out of the way, giving A a scripted, deterministic win.
"""

from textarena.envs.ThreePlayerTicTacToe.env import ThreePlayerTicTacToeEnv


def _fresh():
    env = ThreePlayerTicTacToeEnv()
    env.reset(num_players=3, seed=42)
    return env


def test_reset_requires_three_players():
    import pytest

    env = ThreePlayerTicTacToeEnv()
    for num_players in (2, 4):
        with pytest.raises(ValueError):
            env.reset(num_players=num_players, seed=42)


def test_reset_empty_board():
    env = _fresh()
    board = env.state.game_state["board"]
    assert len(board) == 5 and all(len(r) == 5 for r in board)
    assert all(cell == "" for row in board for cell in row)
    assert env.state.current_player_id == 0


def test_player0_makes_a_line_of_four_and_wins():
    env = _fresh()
    # Interleave: A -> 0,1,2,3 ; B and C park in lower rows.
    moves = ["0", "5", "10",
             "1", "6", "11",
             "2", "7", "12",
             "3"]
    done = False
    for m in moves:
        done = env.step(m)
    assert done
    assert env.state.rewards == {0: 1, 1: -1, 2: -1}


def test_player0_diagonal_line_wins_complete_game():
    env = _fresh()
    moves = ["0", "1", "4", "6", "2", "5", "12", "3", "7", "18"]
    for move in moves:
        done = env.step(move)
    assert done
    assert env.state.rewards == {0: 1, 1: -1, 2: -1}
    assert env.state.game_state["board"][3][3] == "A"


def test_occupied_cell_first_invalid_not_terminal():
    env = _fresh()
    env.step("0")          # P0 takes cell 0
    done = env.step("0")  # P1 tries the same cell
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_cell_first_invalid_not_terminal():
    env = _fresh()
    done = env.step("25")  # only 0-24 valid
    assert not done
    assert env.state.error_count == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("not a number")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice
    assert env.action_format == "a cell number from 0 to 24, for example '4'"

    fresh = _fresh()
    fresh.step("4")
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_huge_numeric_cell_is_invalid_without_integer_conversion_crash():
    env = _fresh()
    before = [row.copy() for row in env.state.game_state["board"]]
    done = env.step("9" * 10_000)
    assert not done
    assert env.state.game_state["board"] == before
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_two_consecutive_invalids_award_others():
    env = _fresh()
    done = env.step("not a number")
    assert not done and env.state.error_count == 1
    done = env.step("still not a number")
    assert done
    # Offender (player 0) loses; the other two win.
    assert env.state.rewards == {0: -1, 1: 1, 2: 1}


def test_render_and_snapshot_track_available_cells_across_reset():
    env = _fresh()
    snap = env.snapshot()
    env.step("0")
    assert "Available Moves:" in env.render(1)
    assert "0" not in env.render(1).split("Available Moves: ", 1)[1].split(", ")
    env.restore(snap)
    assert env.state.game_state["board"][0][0] == ""
    assert env.state.current_player_id == 0
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["board"] == [[""] * 5 for _ in range(5)]
