"""Deterministic offline tests for the QuantumTicTacToe environment.

Moves place a spooky mark in two empty cells ('a,b'). When the entanglement
graph forms a cycle, marks collapse into classical symbols. The sequences below
force a triangular cycle among cells 0,1,2 so a full row solidifies for one player.
Player 0 is 'O' (even), Player 1 is 'X' (odd); Player 0 moves first.
"""
from textarena.envs.QuantumTicTacToe.env import QuantumTicTacToeEnv


def _fresh():
    env = QuantumTicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_player0_wins_with_solidified_row():
    env = _fresh()
    # P0 entangles cells {0,1},{1,2},{0,2} -> cycle collapses to O,O,O across row 0.
    seq = ["0,1", "3,4", "1,2", "4,5", "0,2"]
    done = False
    for a in seq:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["board"][0] == ["O", "O", "O"]


def test_player1_wins_with_solidified_row():
    env = _fresh()
    # Symmetric: P1 builds the collapsing triangle among cells 0,1,2.
    seq = ["3,4", "0,1", "4,5", "1,2", "6,7", "0,2"]
    done = False
    for a in seq:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {1: 1, 0: -1}
    assert env.state.game_state["board"][0] == ["X", "X", "X"]


def test_cycle_collapse_propagates_to_dependent_marks():
    env = _fresh()
    gs = env.state.game_state
    gs["superpositions"] = {
        0: (0, (0, 0), (0, 1)),
        1: (1, (0, 1), (0, 2)),
        2: (0, (0, 2), (0, 0)),
        3: (1, (0, 1), (1, 1)),
    }
    gs["move_count"] = 4

    outcome = env._collapse_superpositions([0, 1, 2], seed_move_id=2)

    assert outcome is None
    assert gs["superpositions"] == {}
    assert gs["board"][0] == ["O", "X", "O"]
    assert gs["board"][1][1] == "X"
    assert gs["classical_moves"][0] == [1, 2, 3]
    assert gs["classical_moves"][1][1] == 4
    rendered = env.get_board_str()
    assert "O1" in rendered and "X2" in rendered and "O3" in rendered


def test_snapshot_restore_replays_cycle_collapse():
    env = _fresh()
    for action in ["0,1", "3,4", "1,2", "4,5"]:
        done, _ = env.step(action)
        assert not done
    snapshot = env.snapshot()

    done, _ = env.step("0,2")
    first = (
        done,
        [row[:] for row in env.state.game_state["board"]],
        dict(env.state.game_state["superpositions"]),
        dict(env.state.rewards),
    )

    env.restore(snapshot)
    done, _ = env.step("0,2")
    second = (
        done,
        [row[:] for row in env.state.game_state["board"]],
        dict(env.state.game_state["superpositions"]),
        dict(env.state.rewards),
    )

    assert second == first


def test_entangled_pair_order_does_not_change_automatic_collapse():
    forward = _fresh()
    reverse = _fresh()

    forward.step("0,1")
    forward.step("0,1")
    reverse.step("0,1")
    reverse.step("1,0")

    assert reverse.state.game_state == forward.state.game_state
    assert forward.state.game_state["board"][0][:2] == ["X", "O"]


def test_full_board_win_is_not_overridden_by_draw():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [
        ["O", "O", "O"],
        ["X", "X", "O"],
        ["X", "O", "X"],
    ]
    gs["classical_moves"] = [
        [1, 3, 5],
        [2, 4, 7],
        [6, 8, 9],
    ]

    outcome = env._collapse_superpositions([])

    assert outcome.rewards == {0: 1, 1: -1}


def test_existing_line_ends_game_before_last_empty_cell_claim():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [
        ["O", "O", "O"],
        ["X", "X", "O"],
        ["X", "O", ""],
    ]
    gs["classical_moves"] = [
        [1, 3, 5],
        [2, 4, 7],
        [6, 8, None],
    ]

    outcome = env._collapse_superpositions([])

    assert outcome.rewards == {0: 1, 1: -1}
    assert gs["board"][2][2] == ""


def test_simultaneous_lines_use_earlier_maximum_move():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [
        ["O", "O", "O"],
        ["X", "X", "X"],
        ["O", "X", "O"],
    ]
    gs["classical_moves"] = [
        [1, 3, 5],
        [2, 4, 6],
        [7, 8, 9],
    ]

    outcome = env._collapse_superpositions([])

    assert outcome.rewards == {0: 1, 1: -1}


def test_full_board_without_line_is_draw():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [
        ["O", "X", "O"],
        ["O", "X", "X"],
        ["X", "O", "O"],
    ]
    gs["classical_moves"] = [
        [1, 2, 3],
        [5, 4, 6],
        [8, 7, 9],
    ]

    outcome = env._collapse_superpositions([])

    assert outcome.rewards == {0: 0, 1: 0}


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("place somewhere")
    assert not done
    assert env.state.error_count == 1


def test_duplicate_cell_indices_rejected():
    env = _fresh()
    done, _ = env.step("2,2")
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_cell_rejected():
    env = _fresh()
    done, _ = env.step("9,0")
    assert not done
    assert env.state.error_count == 1


def test_huge_cell_index_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done, _ = env.step(f"{'9' * 5000},0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state
