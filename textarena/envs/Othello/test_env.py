"""Deterministic offline tests for the Othello environment.

Player 0 is Black (moves first), Player 1 is White.
"""
import pytest

from textarena.envs.Othello.env import OthelloEnv


def _fresh(board_size=8):
    env = OthelloEnv(board_size=board_size)
    env.reset(num_players=2, seed=42)
    return env


def test_initial_valid_moves_4x4():
    env = _fresh(board_size=4)
    assert env.state.game_state["valid_moves"] == [[0, 1], [1, 0], [2, 3], [3, 2]]


def test_valid_move_flips_pieces():
    env = _fresh(board_size=8)
    done, _ = env.step("2, 3")  # Black flanks the white piece at (3,3)
    assert not done
    assert env.state.game_state["black_count"] == 4
    assert env.state.game_state["white_count"] == 1
    assert env.state.current_player_id == 1


def test_forced_pass_keeps_actor_and_synchronizes_valid_moves():
    env = _fresh(board_size=4)
    board = env.state.game_state["board"]
    for row in board:
        row[:] = [""] * 4
    board[0][0], board[0][1] = "B", "W"
    board[1][0], board[1][1] = "B", "W"

    done, _ = env.step("0, 2")

    assert not done
    assert env.state.current_player_id == 0
    assert [1, 2] in env.state.game_state["valid_moves"]
    assert env.state.game_state["valid_moves"] == env._valid_moves(board, "B")
    assert env.state.game_state["black_count"] == 4
    assert env.state.game_state["white_count"] == 1


def test_full_game_white_wins_on_4x4():
    env = _fresh(board_size=4)
    # Greedy first-valid-move line for both sides on the 4x4 board.
    seq = [
        "0, 1", "0, 0", "1, 0", "0, 2", "0, 3", "2, 0",
        "3, 0", "1, 3", "2, 3", "3, 1", "3, 2", "3, 3",
    ]
    done = False
    for a in seq:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.game_state["white_count"] == 10
    assert env.state.game_state["black_count"] == 6


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("row two col three")
    assert not done
    assert env.state.error_count == 1


def test_compact_ambiguous_coordinates_are_rejected():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]

    done, _ = env.step("23")

    assert not done
    assert env.state.game_state["board"] == before
    assert env.state.error_count == 1


def test_huge_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"{'9' * 5000}, 0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state


def test_illegal_move_rejected():
    env = _fresh(board_size=8)
    done, _ = env.step("0, 0")  # not a legal opening move
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("board_size", [4, 6, 10, 14])
def test_terminal_renderer_supports_registered_sizes(board_size):
    env = _fresh(board_size=board_size)
    rendered = env.get_board_str()
    label_width = len(str(board_size - 1))
    expected_header = " " * (label_width + 2) + "".join(f"{i:^4}" for i in range(board_size))
    assert expected_header in rendered
    assert rendered.count(" │ ") == board_size * board_size
    assert env.state.game_state["rendered_board"] == rendered
    assert rendered in env.render(0)
    lines = rendered.splitlines()
    assert len(lines[0]) == len(lines[1]) == len(lines[2])


@pytest.mark.parametrize("kwargs", [{"board_size": 5}, {"board_size": 8.0}, {"show_valid": 1}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        OthelloEnv(**kwargs)
