"""Deterministic game-logic tests for Battleship-v0."""
import pytest

from textarena.envs.Battleship.env import BattleshipEnv

SHIP_INITIALS = {"A", "B", "S", "D", "P"}


def _fresh(grid_size=10):
    env = BattleshipEnv(grid_size=grid_size)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_places_all_ships():
    env = _fresh()
    # Each player's board should contain the full complement of ship cells (5+4+3+3+2).
    for pid in range(2):
        cells = sum(cell in SHIP_INITIALS for row in env.state.game_state["board"][pid] for cell in row)
        assert cells == 17
    assert env.state.current_player_id == 0


def test_small_board_generation_is_bounded_unique_and_deterministic():
    for seed in range(10):
        first = BattleshipEnv(grid_size=5)
        second = BattleshipEnv(grid_size=5)
        first.reset(num_players=2, seed=seed)
        second.reset(num_players=2, seed=seed)
        assert first.state.game_state["board"] == second.state.game_state["board"]
        for pid in range(2):
            assert sum(
                cell in SHIP_INITIALS
                for row in first.state.game_state["board"][pid]
                for cell in row
            ) == 17


def test_default_terminal_view_does_not_reveal_opponent_ships():
    env = _fresh(grid_size=5)
    opponent = env.state.game_state["board"][1]
    for row in opponent:
        row[:] = ["~"] * 5
    opponent[0][0] = "Z"

    private_view = env.get_board_str(player_id=0)
    admin_view = env.get_board_str(reveal_all=True)

    assert "Z" not in private_view
    assert "Z" in admin_view
    assert "0    1    2    3    4" in admin_view


def test_extreme_admin_renderer_keeps_titles_and_headers_aligned():
    env = _fresh(grid_size=20)

    lines = env.get_board_str(reveal_all=True).splitlines()

    assert len(lines[0]) == len(lines[1]) == len(lines[2])
    assert "19" in lines[1]


@pytest.mark.parametrize("grid_size", [5, 10, 20])
def test_admin_header_numbers_sit_above_their_cells(grid_size):
    env = _fresh(grid_size=grid_size)
    for board in env.state.game_state["board"].values():
        for row in board:
            row[:] = ["S"] * grid_size

    lines = env.get_board_str(reveal_all=True).splitlines()
    board_width = len(lines[2])
    header, first_row = lines[1][:board_width], lines[3][:board_width]

    for col in range(grid_size):
        number_start = header.index(str(col), 4 + 5 * col)
        assert number_start == 4 + 5 * col
        assert first_row[number_start] == "S"


@pytest.mark.parametrize("grid_size", [None, 4, 27, 5.5, True])
def test_invalid_grid_size_rejected(grid_size):
    with pytest.raises(ValueError):
        BattleshipEnv(grid_size=grid_size)


def test_hit_marks_boards():
    env = _fresh()
    opp_board = env.state.game_state["board"][1]
    # find a ship cell on the opponent's board
    target = next((r, c) for r in range(10) for c in range(10) if opp_board[r][c] in SHIP_INITIALS)
    r, c = target
    done, _ = env.step(f"{chr(ord('A') + r)}{c}")
    assert not done
    assert env.state.game_state["board"][1][r][c] == "X"
    assert env.state.game_state["tracking_board"][0][r][c] == "X"


def test_snapshot_restore_replays_shot_and_private_render():
    env = _fresh(grid_size=5)
    opponent = env.state.game_state["board"][1]
    r, c = next(
        (r, c)
        for r in range(env.grid_size)
        for c in range(env.grid_size)
        if opponent[r][c] in SHIP_INITIALS
    )
    action = f"{chr(ord('A') + r)}{c}"
    snapshot = env.snapshot()

    done, _ = env.step(action)
    first = (
        done,
        env.state.game_state,
        env.get_board_str(player_id=0),
        env.get_board_str(player_id=1),
    )

    env.restore(snapshot)
    done, _ = env.step(action)
    second = (
        done,
        env.state.game_state,
        env.get_board_str(player_id=0),
        env.get_board_str(player_id=1),
    )

    assert second == first


def test_sinking_last_ship_wins():
    env = _fresh()
    board = env.state.game_state["board"]
    # Wipe player 1's board and leave a single one-cell target for player 0.
    for r in range(10):
        for c in range(10):
            board[1][r][c] = "~"
    board[1][0][0] = "P"
    done, _ = env.step("A0")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("fire somewhere")
    assert not done
    assert env.state.error_count == 1


def test_out_of_bounds_increments_error_count():
    env = _fresh()
    done, _ = env.step("Z9")  # row 'Z' is far outside a 10x10 board
    assert not done
    assert env.state.error_count == 1


def test_huge_column_is_rejected_without_mutation():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"A{'9' * 5000}")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("still garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
