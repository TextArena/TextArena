"""Deterministic game-logic tests for Checkers-v0."""
import copy

import pytest

from textarena.envs.Checkers.env import CheckersEnv


def _fresh(max_turns=50):
    env = CheckersEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def _clear(board):
    for r in range(8):
        for c in range(8):
            board[r][c] = "."


def test_reset_board_layout():
    env = _fresh()
    board = env.state.game_state["board"]
    assert sum(cell.lower() == "b" for row in board for cell in row) == 12
    assert sum(cell.lower() == "r" for row in board for cell in row) == 12
    assert env.state.current_player_id == 0


def test_simple_move_and_rotation():
    env = _fresh()
    done, _ = env.step("5 0 4 1")  # Red advances diagonally forward
    assert not done
    board = env.state.game_state["board"]
    assert board[4][1] == "r" and board[5][0] == "."
    assert env.state.current_player_id == 1


def test_capture_removes_jumped_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    board[4][3] = "b"  # place an enemy piece to jump
    done, _ = env.step("5 2 3 4")
    assert not done
    assert board[3][4] == "r"      # red landed here
    assert board[4][3] == "."      # jumped black removed


def test_capture_is_mandatory_and_invalid_move_is_atomic():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[5][2] = "r"
    board[4][3] = "b"
    before = copy.deepcopy(board)
    done, _ = env.step("5 0 4 1")
    assert not done
    assert board == before
    assert env.state.current_player_id == 0


def test_multi_jump_keeps_turn_and_forces_same_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    done, _ = env.step("5 0 3 2")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.game_state["forced_piece"] == (3, 2)
    assert env.state.game_state["valid_moves"] == ["3 2 1 4"]
    done, _ = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_turn_limit_waits_for_forced_capture_chain_to_finish():
    env = _fresh(max_turns=1)
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    board[0][1] = "b"  # keeps Black alive and mobile after the chain

    done, _ = env.step("5 0 3 2")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.game_state["forced_piece"] == (3, 2)

    done, _ = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_man_cannot_capture_backward_but_king_can():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "r"
    board[4][3] = "b"
    before = copy.deepcopy(board)
    env.step("3 2 5 4")
    assert board == before

    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "R"
    board[4][3] = "b"
    done, _ = env.step("3 2 5 4")
    assert done  # the only Black piece was captured
    assert board[5][4] == "R"


def test_promotion_ends_capture_turn():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][1] = "r"
    board[1][2] = "b"
    board[1][4] = "b"  # newly crowned king could jump this only on a later turn
    done, _ = env.step("2 1 0 3")
    assert not done
    assert board[0][3] == "R"
    assert env.state.game_state["forced_piece"] is None
    assert env.state.current_player_id == 1


def test_valid_move_generation_and_turn_limit_draw():
    env = _fresh(max_turns=1)
    assert "5 0 4 1" in env.state.game_state["valid_moves"]
    done, _ = env.step("5 0 4 1")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_snapshot_restore_recovers_forced_capture_state():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    snapshot = env.snapshot()
    env.step("5 0 3 2")
    env.restore(snapshot)
    assert env.state.current_player_id == 0
    assert env.state.game_state["forced_piece"] is None
    assert env.state.game_state["board"][5][0] == "r"


def test_capturing_last_piece_wins():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "r"
    board[2][3] = "b"  # black's only remaining piece
    done, _ = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("move up")
    assert not done
    assert env.state.error_count == 1


def test_illegal_move_increments_error_count():
    env = _fresh()
    done, _ = env.step("5 0 3 0")  # straight two-square move is illegal
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


@pytest.mark.parametrize("max_turns", [0, -1, 1.5, True])
def test_invalid_turn_limit_rejected(max_turns):
    with pytest.raises(ValueError):
        CheckersEnv(max_turns=max_turns)
