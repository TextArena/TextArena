"""Deterministic game-logic tests for ConnectFour."""
import pytest

from textarena.envs.ConnectFour.env import ConnectFourEnv


def _fresh(**kwargs):
    env = ConnectFourEnv(**kwargs)
    env.reset(num_players=2, seed=42)
    return env


def test_player0_wins_vertical():
    env = _fresh()
    # Player 0 stacks four X's in column 0; player 1 answers in column 1.
    for action in ["0", "1", "0", "1", "0", "1", "0"]:
        done, _ = env.step(action)
    assert done and env.state.rewards == {0: 1, 1: -1}


def test_player0_wins_diagonal():
    env = _fresh()
    sequence = ["0", "1", "1", "2", "4", "2", "2", "3", "4", "3", "5", "3", "3"]
    for action in sequence:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_small_full_board_draw_completion():
    env = _fresh(num_rows=2, num_cols=3)
    for action in ["0", "1", "2", "0", "1", "2"]:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_turn_rotation_after_valid_move():
    env = _fresh()
    assert env.state.current_player_id == 0
    done, _ = env.step("3")
    assert not done and env.state.current_player_id == 1


def test_disc_lands_on_bottom_row():
    env = _fresh()
    env.step("2")
    board = env.state.game_state["board"]
    # Bottom-most row should now hold the X in column 2.
    assert board[env.num_rows - 1][2] == "X"


def test_col_prefix_is_accepted():
    env = _fresh()
    done, _ = env.step("col 2")
    assert not done and env.state.error_count == 0
    board = env.state.game_state["board"]
    assert board[env.num_rows - 1][2] == "X"


def test_blind_terminal_view_exposes_only_public_move_history():
    env = _fresh(is_open=False)
    env.step("3")

    board_str = env.get_board_str()

    assert board_str == "Hidden Connect Four board.\nPublic move history: P0:col 3"
    assert env.render(1) is None


def test_large_registered_board_uses_synchronized_renderer():
    env = _fresh(num_rows=12, num_cols=15)
    env.step("14")

    rendered = env.get_board_str()

    assert rendered == env._render_board()
    assert rendered in env.render(1)
    assert "14" in rendered
    assert rendered.count("│") == env.num_rows * (env.num_cols + 1)
    lines = rendered.splitlines()
    assert len(lines[0]) == len(lines[1]) == len(lines[2])


@pytest.mark.parametrize(
    "kwargs",
    [{"num_rows": 0}, {"num_cols": 0}, {"num_rows": 2.5}, {"is_open": 1}],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        ConnectFourEnv(**kwargs)


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no move here")
    assert not done and env.state.error_count == 1


def test_illegal_out_of_bounds_column_rejected():
    env = _fresh()
    # Well-formatted but out of range for the default 7-column board.
    done, _ = env.step("9")
    assert not done and env.state.error_count == 1


def test_huge_column_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step("9" * 5000)

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state


def test_illegal_full_column_rejected():
    env = _fresh(num_rows=2, num_cols=3)
    # Fill column 0 (two rows) with alternating players, then try to overfill.
    env.step("0")  # p0 -> col0 bottom
    env.step("0")  # p1 -> col0 top (now full)
    done, _ = env.step("0")  # p0 attempts a full column
    assert not done and env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("still garbage")
    assert done and env.state.rewards == {0: -1, 1: 1}
