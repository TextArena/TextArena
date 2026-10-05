"""Deterministic game-logic tests for Battleship-v1."""
import pytest

import textarena as ta
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


def test_hit_marks_boards():
    env = _fresh()
    opp_board = env.state.game_state["board"][1]
    # find a ship cell on the opponent's board
    target = next((r, c) for r in range(10) for c in range(10) if opp_board[r][c] in SHIP_INITIALS)
    r, c = target
    done = env.step(f"{chr(ord('A') + r)}{c}")
    assert not done
    assert env.state.game_state["board"][1][r][c] == "X"
    assert env.state.game_state["tracking_board"][0][r][c] == "X"


def test_sinking_last_ship_wins():
    env = _fresh()
    board = env.state.game_state["board"]
    # Wipe player 1's board and leave a single one-cell target for player 0.
    for r in range(10):
        for c in range(10):
            board[1][r][c] = "~"
    board[1][0][0] = "P"
    done = env.step("A0")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done = env.step("fire somewhere")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("grid_size, last_row", [(5, "E"), (10, "J"), (14, "N"), (20, "T")])
def test_format_error_describes_expected_action(grid_size, last_row):
    env = _fresh(grid_size=grid_size)
    env.step("fire somewhere")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]
    assert f"from A to {last_row} followed by a column number from 0 to {grid_size - 1}," in env.action_format

    assert env.action_format.endswith("for example 'C4'")
    fresh = _fresh(grid_size=grid_size)
    fresh.step("C4")
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_out_of_bounds_increments_error_count():
    env = _fresh()
    done = env.step("Z9")  # row 'Z' is far outside a 10x10 board
    assert not done
    assert env.state.error_count == 1


def test_huge_column_is_rejected_without_mutation():
    env = _fresh()
    before = env.snapshot()

    done = env.step(f"A{'9' * 5000}")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done = env.step("still garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def _ship_cells(env, player_id, ship_name):
    (r1, c1), (r2, c2) = env.state.game_state["ship_placements"][player_id][ship_name]
    return [
        (r, c)
        for r in range(min(r1, r2), max(r1, r2) + 1)
        for c in range(min(c1, c2), max(c1, c2) + 1)
    ]


def _water_cells(env, player_id):
    board = env.state.game_state["board"][player_id]
    return [(r, c) for r in range(env.grid_size) for c in range(env.grid_size) if board[r][c] == "~"]


def _coord(cell):
    return f"{chr(ord('A') + cell[0])}{cell[1]}"


def test_mdp_observation_keeps_only_the_latest_board():
    env = ta.make("Battleship-v1-standard-mdp")
    env.reset(num_players=2, seed=3)
    raw = env.env
    shots = {pid: _water_cells(raw, 1 - pid) for pid in range(2)}
    for _ in range(20):
        pid, _ = env.get_observation()
        env.step(_coord(shots[pid].pop()))

    _, observation = env.get_observation()

    assert observation.count("Your Ships") == 1
    assert len(observation) < 6000


def test_invalid_move_rerenders_the_actors_board():
    env = _fresh(grid_size=5)
    start = len(env.state.events)

    env.step("not a coordinate")

    boards = [
        (to_id, message)
        for _, message, event_type, to_id in env.state.events[start:]
        if event_type == ta.ObservationType.GAME_BOARD
    ]
    assert boards == [(0, env.get_board_str(player_id=0))]


def test_sinking_announces_the_ship_type_to_both_players():
    env = _fresh()
    patrol_boat = _ship_cells(env, 1, "Patrol Boat")
    misses = _water_cells(env, 0)

    env.step(_coord(patrol_boat[0]))
    env.step(_coord(misses.pop()))
    start = len(env.state.events)
    env.step(_coord(patrol_boat[1]))

    messages = {
        to_id: message
        for _, message, event_type, to_id in env.state.events[start:]
        if event_type == ta.ObservationType.GAME_ACTION_DESCRIPTION
    }
    assert "sank the opponent's Patrol Boat" in messages[0]
    assert "sank your Patrol Boat" in messages[1]


def test_prompt_states_the_coordinate_ranges_and_fleet():
    env = _fresh(grid_size=5)
    prompt = env.prompt(0)
    assert "A-E" in prompt and "0-4" in prompt
    assert "Patrol Boat (P, 2 cells)" in prompt
    assert "Here is the initial board" not in prompt
