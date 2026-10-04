"""Deterministic game-logic tests for Breakthrough-v1."""
import copy
import re

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


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("move a pawn please")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("board_size", [8, 5, 10])
def test_format_error_describes_expected_action(board_size):
    env = _fresh(board_size=board_size)
    env.step("move a pawn please")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice
    assert f"rows 1 to {board_size})" in env.action_format

    white_example, black_example = re.search(
        r"for example '([^']+)' as White or '([^']+)' as Black", env.action_format
    ).groups()
    assert black_example in env._get_valid_moves(1)
    fresh = _fresh(board_size=board_size)
    fresh.step(white_example)
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


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


@pytest.mark.parametrize("board_size", [5, 8, 10])
@pytest.mark.parametrize("player_id", [0, 1])
def test_prompt_describes_setup_and_its_example_is_legal(board_size, player_id):
    env = _fresh(board_size=board_size)

    prompt = env.prompt(player_id)

    assert f"White (W) on rows 1 and 2, Black (B) on rows {board_size - 1} and {board_size}" in prompt
    assert "White moves first" in prompt
    assert "Blacks's" not in prompt
    example = re.search(r"e\.g\. '([a-z]\d+[a-z]\d+)'", prompt).group(1)
    assert example in env._get_valid_moves(player_id)


def test_blind_prompt_explains_that_no_board_is_shown():
    env = BreakthroughEnv(board_size=8, is_open=False)
    env.reset(num_players=2, seed=0)

    assert "board is not shown" in env.prompt(0)
    assert env.render(0) is None
    assert "board is not shown" not in _fresh().prompt(0)


def test_rearmost_piece_always_has_a_diagonal_move():
    # A blocked-in position cannot exist: the rearmost piece's diagonal squares hold no friendly piece.
    env = _fresh(board_size=5)
    board = env.state.game_state["board"]
    for row in board:
        row[:] = [""] * 5
    board[2][0], board[1][0], board[1][1] = "B", "W", "W"  # a3 is blocked head-on and b2 holds a White piece
    board[0][4] = "W"

    assert env._get_valid_moves(1) == ["a3b2"]


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
