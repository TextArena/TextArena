"""Deterministic game-logic tests for Alquerque-v0."""
from textarena.envs.Alquerque.env import AlquerqueEnv


def _fresh():
    env = AlquerqueEnv()
    env.reset(num_players=2, seed=42)
    return env


def _clear(board):
    for r in range(5):
        for c in range(5):
            board[r][c] = ""


def test_reset_initial_board():
    env = _fresh()
    board = env.state.game_state["board"]
    # Black occupies top two rows, Red the bottom two, middle row empty.
    assert all(board[0][c] == "B" and board[1][c] == "B" for c in range(5))
    assert all(board[2][c] == "" for c in range(5))
    assert all(board[3][c] == "R" and board[4][c] == "R" for c in range(5))
    assert env.state.current_player_id == 0


def test_forward_move_mutates_board_and_rotates():
    env = _fresh()
    # cell 17 = row3,col2 (R) -> cell 12 = row2,col2 (empty), a legal forward step.
    done, _ = env.step("17 12")
    assert not done
    board = env.state.game_state["board"]
    assert board[2][2] == "R" and board[3][2] == ""
    assert env.state.current_player_id == 1  # turn rotated
    assert env.get_board_str() == env._render_board()


def test_capture_awards_score_and_removes_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # cell 12
    board[2][1] = "B"  # cell 11 (adjacent enemy)
    # Jump R over B (cell 11) landing on cell 10 (row2,col0).
    done, _ = env.step("12 10")
    assert done  # Black now has no pieces -> Red wins
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["score"] == [10, 0]


def test_disconnected_diagonal_is_rejected_atomically():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[4][1] = "R"  # b1 is not joined diagonally to a2.
    before = [row[:] for row in board]

    done, _ = env.step("b1 a2")

    assert not done
    assert board == before
    assert env.state.current_player_id == 0


def test_available_capture_is_mandatory():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"
    board[2][1] = "B"
    before = [row[:] for row in board]

    done, _ = env.step("c3 c4")

    assert not done
    assert board == before


def test_multi_capture_path_is_atomic_and_must_be_completed():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # c3
    board[2][1] = "B"  # b3
    board[3][1] = "B"  # b2
    before = [row[:] for row in board]

    done, _ = env.step("c3 a3")
    assert not done
    assert board == before

    done, _ = env.step("c3 -> a3 -> c1")
    assert done
    assert board[4][2] == "R"
    assert board[2][1] == board[3][1] == ""
    assert env.state.game_state["score"] == [20, 0]
    assert env.state.rewards == {0: 1, 1: -1}


def test_mover_becoming_blocked_does_not_end_opponents_turn():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[1][2] = "R"  # c4 can make one final forward move to c5.
    board[0][0] = "B"  # Black still has a legal move from a5.

    done, _ = env.step("c4 c5")

    assert not done
    assert env.state.current_player_id == 1
    assert board[0][2] == "R"


def test_turn_limit_uses_capture_score_then_draws_ties():
    env = _fresh()
    env.state.game_state["score"] = [20, 10]
    assert env.on_turn_limit().rewards == {0: 1, 1: -1}

    env.state.game_state["score"] = [20, 20]
    assert env.on_turn_limit().rewards == {0: 0, 1: 0}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("not a move at all")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # offender keeps the turn


def test_illegal_but_wellformatted_move_rejected():
    env = _fresh()
    # cell 20 = row4,col0 (R) jumping to cell 10 over own piece at row3,col0 -> illegal.
    done, _ = env.step("20 10")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_huge_numeric_coordinate_is_rejected_without_exception():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]

    done, _ = env.step(f"{'9' * 5000} 12")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["board"] == before


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage again")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
