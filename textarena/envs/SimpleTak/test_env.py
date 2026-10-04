"""Offline deterministic tests for the SimpleTak environment."""
import pytest

from textarena.envs.SimpleTak.env import SimpleTakEnv


def _fresh(board_size=3):
    env = SimpleTakEnv(board_size=board_size)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    assert env.state.num_players == 2
    assert env.state.current_player_id == 0
    assert not env.state.done
    board = env.state.game_state["board"]
    assert len(board) == 3 and len(board[0]) == 3
    assert all(cell == "" for row in board for cell in row)


def test_place_stone_mutates_board_and_rotates():
    env = _fresh()
    done, _ = env.step("0")
    assert not done
    assert env.state.game_state["board"][0][0] == "O"  # player 0 uses 'O'
    assert env.state.current_player_id == 1


def test_player0_connects_left_column_and_wins():
    env = _fresh()
    # P0 builds the left column (0,3,6) => top-to-bottom connection.
    for a in ["0", "1", "3", "4", "6"]:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_player0_connects_left_to_right_and_wins():
    env = _fresh()
    for action in ["0", "3", "1", "4", "2"]:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


@pytest.mark.parametrize("board_size", [0, -1, 2.5, True])
def test_invalid_board_size_rejected(board_size):
    with pytest.raises(ValueError):
        SimpleTakEnv(board_size=board_size)


def test_invalid_format_increments_error_not_done():
    env = _fresh()
    done, _ = env.step("not a move")
    assert not done
    assert env.state.error_count == 1
    # Turn should not have rotated after a single invalid move.
    assert env.state.current_player_id == 0


def test_occupied_cell_rejected():
    env = _fresh()
    env.step("0")          # P0 -> (0,0)
    done, _ = env.step("0")  # P1 tries the same occupied cell
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1  # still P1's turn


def test_out_of_range_cell_rejected():
    env = _fresh()
    done, _ = env.step("99")
    assert not done
    assert env.state.error_count == 1


def test_huge_cell_index_is_rejected_without_mutation():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]

    done, _ = env.step("9" * 5000)

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["board"] == before


def test_extreme_registered_size_render_and_snapshot_restore():
    env = _fresh(board_size=8)
    snapshot = env.snapshot()
    env.step("63")
    assert env.state.game_state["board"][7][7] == "O"
    assert "O" in env.get_board_str()

    env.restore(snapshot)

    assert env.state.game_state["board"][7][7] == ""
    assert env.state.current_player_id == 0


def test_two_consecutive_invalid_moves_lose():
    env = _fresh()
    env.step("garbage")        # first invalid: error_count -> 1
    done, _ = env.step("still garbage")  # second invalid ends the game
    assert done
    # Offender (P0) loses, opponent wins.
    assert env.state.rewards == {0: -1, 1: 1}
