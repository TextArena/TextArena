"""Deterministic game-logic tests for Breakthrough-v0."""
import copy

import pytest

from textarena.envs.Breakthrough.env import BreakthroughEnv


def _fresh(board_size=8):
    env = BreakthroughEnv(board_size=board_size)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_builds_starting_board():
    env = _fresh()
    board = env.state.game_state["board"]
    assert all(board[0][c] == "W" and board[1][c] == "W" for c in range(8))
    assert all(board[6][c] == "B" and board[7][c] == "B" for c in range(8))
    assert env.state.current_player_id == 0


def test_forward_move_and_rotation():
    env = _fresh()
    done, _ = env.step("a2a3")  # White pawn from row1 to empty row2
    assert not done
    board = env.state.game_state["board"]
    assert board[2][0] == "W" and board[1][0] == ""
    assert env.state.current_player_id == 1


def test_diagonal_capture():
    env = _fresh()
    # Drop a black piece diagonally in front of a1 and capture it.
    env.state.game_state["board"][2][1] = "B"
    done, _ = env.step("a2b3")
    assert not done
    assert env.state.game_state["board"][2][1] == "W"


def test_diagonal_move_to_empty_square_is_legal():
    env = _fresh()
    done, _ = env.step("a2b3")
    assert not done
    assert env.state.game_state["board"][2][1] == "W"


def test_illegal_destination_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("a1b2")  # occupied by another White piece
    assert not done
    assert env.state.game_state == before
    assert env.state.current_player_id == 0


def test_reaching_home_row_wins():
    env = _fresh(board_size=5)
    board = env.state.game_state["board"]
    board[3][0] = "W"   # one step from Black's home row (row 4)
    board[4][0] = ""    # clear the destination
    done, _ = env.step("a4a5")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_valid_moves_stay_synchronised_after_rotation():
    env = _fresh()
    env.step("a2b3")
    assert env.state.game_state["valid_moves"] == env._get_valid_moves(1)
    assert all(move[0] in "abcdefgh" for move in env.state.game_state["valid_moves"])


def test_snapshot_restore_recovers_board_and_turn():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("a2a3")
    env.restore(snapshot)
    assert env.state.current_player_id == 0
    assert env.state.game_state["board"][1][0] == "W"
    assert env.state.game_state["board"][2][0] == ""


@pytest.mark.parametrize("size", [3, 27])
def test_invalid_board_size_rejected(size):
    with pytest.raises(ValueError):
        BreakthroughEnv(board_size=size)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"board_size": 4.5},
        {"board_size": True},
        {"is_open": 1},
    ],
)
def test_invalid_configuration_types_rejected(kwargs):
    with pytest.raises(ValueError):
        BreakthroughEnv(**kwargs)


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("move a pawn please")
    assert not done
    assert env.state.error_count == 1


def test_leading_zero_coordinate_is_rejected_without_mutation():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("a02a03")
    assert not done
    assert env.state.game_state == before


def test_illegal_move_increments_error_count():
    env = _fresh()
    done, _ = env.step("a2a4")  # cannot advance two squares
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
