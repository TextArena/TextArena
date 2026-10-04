"""Offline, deterministic tests for the Tak environment.

Tak is a two-player abstract game where you win by connecting two opposite edges
with a road of flat stones/capstones. On a 3x3 board, Player 0 can build a
vertical road in column 0 (rows 0,1,2) while Player 1 harmlessly builds in
column 2. Actions use the ``place () {(r,c): [F0]}`` format.
"""

import pytest

from textarena.envs.Tak.env import TakEnv


def _fresh(board_size=3, stones=10, capstones=1):
    env = TakEnv(board_size=board_size, stones=stones, capstones=capstones)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_structure():
    env = _fresh()
    assert len(env.board) == 3 and all(len(r) == 3 for r in env.board)
    assert all(cell == [] for row in env.board for cell in row)
    assert env.players[0]["stones"] == 10 and env.players[0]["capstones"] == 1
    assert env.game_state["move_count"] == 0
    assert env.state.current_player_id == 0


def test_opening_placement_uses_opponents_flat_and_reserve():
    env = _fresh()
    done, _ = env.step("place () {(0,0): [F1]}")
    assert not done
    assert env.board[0][0] == ["F1"]
    assert env.players[1]["stones"] == 9
    assert env.players[0]["stones"] == 10
    assert env.game_state["move_count"] == 1
    assert env.state.current_player_id == 1
    assert env.get_board_str() == env._render_board()


@pytest.mark.parametrize(
    "action",
    [
        "place () {(0,0): [F0]}",
        "place () {(0,0): [W1]}",
        "place () {(0,0): [C1]}",
        "move (0,0) {(0,1): [F0]}",
    ],
)
def test_opening_rejects_self_pieces_nonflats_and_movement(action):
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(action)

    assert not done
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]
    assert env.game_state["move_count"] == 0


def test_malformed_placement_is_invalid_without_mutation():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step("place () {(0,0): []}")

    assert not done
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"board_size": 2, "stones": 10, "capstones": 1},
        {"board_size": 9, "stones": 10, "capstones": 1},
        {"board_size": 3, "stones": 0, "capstones": 1},
    ],
)
def test_unplayable_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        TakEnv(**kwargs)


def test_huge_source_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"move ({'9' * 5000},0) {{(0,0): [F0]}}")

    assert not done
    assert env.state.error_count == 1
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


def test_huge_allocation_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"place () {{({'9' * 5000},0): [F0]}}")

    assert not done
    assert env.state.error_count == 1
    assert env.board == before["state"].game_state["board"]
    assert env.players == before["state"].game_state["players"]


def test_duplicate_allocation_target_is_rejected():
    env = _fresh()

    done, _ = env.step("place () {(0,0): [F0], (0,0): [F0]}")

    assert not done
    assert env.board[0][0] == []
    assert env.players[0]["stones"] == 10


def test_bad_format_is_invalid():
    env = _fresh()
    done, _ = env.step("place a stone somewhere")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_placement_on_occupied_square_rejected():
    env = _fresh()
    env.step("place () {(0,0): [F1]}")  # P0 places P1's opening flat.
    # P1 tries to place onto the same occupied square.
    done, _ = env.step("place () {(0,0): [F0]}")
    assert not done
    assert env.state.error_count == 1


def test_connecting_road_wins():
    env = _fresh()
    sequence = [
        "place () {(1,1): [F1]}",  # P0 places P1's opening flat
        "place () {(0,1): [F0]}",  # P1 places P0's opening flat
        "place () {(0,0): [F0]}",  # P0
        "place () {(0,2): [F1]}",  # P1
        "place () {(1,0): [F0]}",  # P0
        "place () {(2,2): [F1]}",  # P1
        "place () {(2,0): [F0]}",  # P0 completes column-0 road
    ]
    done = False
    for action in sequence:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_stack_spread_must_be_straight_and_within_carry_limit():
    env = _fresh(board_size=3)
    env.game_state["move_count"] = 2
    env.board[1][1] = ["F0", "F0", "F0", "F0"]
    before = [[stack[:] for stack in row] for row in env.board]

    done, _ = env.step("move (1,1) {(1,2): [F0], (2,2): [F0]}")
    assert not done
    assert env.board == before

    done, _ = env.step("move (1,1) {(1,2): [F0, F0, F0, F0]}")
    assert done  # second consecutive invalid move
    assert env.board == before


def test_capstone_can_flatten_wall_only_as_final_single_drop():
    env = _fresh(board_size=4)
    env.game_state["move_count"] = 2
    env.board[1][0] = ["F1", "C0"]
    env.board[1][2] = ["W1"]

    done, _ = env.step("move (1,0) {(1,1): [F1], (1,2): [C0]}")

    assert not done
    assert env.board[1][0] == []
    assert env.board[1][1] == ["F1"]
    assert env.board[1][2] == ["F1", "C0"]


def test_movement_that_uncovers_opponent_road_awards_opponent():
    env = _fresh()
    env.game_state["move_count"] = 2
    env.board[0][0] = ["F1"]
    env.board[0][1] = ["F1", "F0"]
    env.board[0][2] = ["F1"]

    done, _ = env.step("move (0,1) {(1,1): [F0]}")

    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_exhausting_reserve_uses_visible_flat_count():
    env = _fresh(board_size=3, stones=2, capstones=0)

    env.step("place () {(0,0): [F1]}")
    env.step("place () {(2,2): [F0]}")
    done, _ = env.step("place () {(1,2): [F0]}")

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_exhausting_reserve_draws_on_tied_visible_flat_count():
    env = _fresh(board_size=3, stones=3, capstones=0)

    env.step("place () {(0,0): [F1]}")
    env.step("place () {(2,2): [F0]}")
    env.step("place () {(1,2): [F0]}")
    env.step("place () {(2,0): [F1]}")
    done, _ = env.step("place () {(1,1): [W0]}")

    assert done
    assert env.state.rewards == {0: 0, 1: 0}
