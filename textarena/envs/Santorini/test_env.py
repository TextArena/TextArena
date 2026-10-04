"""Offline deterministic tests for the Santorini (fixed-worker) environment.

Consolidated from the former test_santorini.py, extended with public-API
scripted-play and invalid-move tests.
"""
import random
import copy

import pytest

from textarena.envs.Santorini.env import SantoriniBaseFixedWorkerEnv


def _fresh(num_players=2, **kwargs):
    env = SantoriniBaseFixedWorkerEnv(**kwargs)
    env.reset(num_players=num_players, seed=42)
    return env


def test_init():
    env = SantoriniBaseFixedWorkerEnv()
    assert env.rows == 5 and env.cols == 5
    assert env.is_open is True and env.show_valid is True

    env = SantoriniBaseFixedWorkerEnv(is_open=False, show_valid=False)
    assert env.is_open is False and env.show_valid is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"is_open": 1},
        {"show_valid": "yes"},
        {"error_allowance": -1},
        {"error_allowance": 1.5},
        {"error_allowance": True},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SantoriniBaseFixedWorkerEnv(**kwargs)


def test_reset_player_counts():
    env = SantoriniBaseFixedWorkerEnv()
    with pytest.raises(ValueError):
        env.reset(num_players=1)
    with pytest.raises(ValueError):
        env.reset(num_players=4)
    with pytest.raises(ValueError):
        env.reset(num_players=2.0)

    env.reset(num_players=2, seed=42)
    assert env.state.num_players == 2
    assert env.board[2][1][1] == (0, 1)  # Navy worker 1 at C2
    assert env.board[1][2][1] == (0, 2)  # Navy worker 2 at B3
    assert env.board[3][2][1] == (1, 1)  # White worker 1 at D3
    assert env.board[2][3][1] == (1, 2)  # White worker 2 at C4

    env.reset(num_players=3, seed=42)
    assert env.state.num_players == 3
    assert env.board[2][2][1] == (0, 1)
    assert env.board[3][1][1] == (2, 1)


def test_valid_moves_format():
    env = _fresh(2)
    valid_moves = env._get_valid_moves(0)
    assert isinstance(valid_moves, str) and valid_moves
    for move in valid_moves.split(", "):
        assert env.move_pattern.search(move) is not None


def test_is_valid_move_rules():
    env = _fresh(2)
    env.board = [[(0, None) for _ in range(env.cols)] for _ in range(env.rows)]
    env.board[2][2] = (0, (0, 1))
    # Adjacent empty cells are reachable.
    assert env._is_valid_move(2, 2, 2, 3)
    # Non-adjacent is not.
    assert not env._is_valid_move(2, 2, 2, 4)
    # Cannot climb more than one level.
    env.board[2][3] = (2, None)
    assert not env._is_valid_move(2, 2, 2, 3)
    # Cannot enter a dome.
    env.board[2][3] = (4, None)
    assert not env._is_valid_move(2, 2, 2, 3)
    # Cannot enter an occupied cell.
    env.board[2][3] = (0, (1, 1))
    assert not env._is_valid_move(2, 2, 2, 3)


def test_is_valid_build_rules():
    env = _fresh(2)
    env.board = [[(0, None) for _ in range(env.cols)] for _ in range(env.rows)]
    env.board[2][2] = (0, (0, 1))
    assert env._is_valid_build(env.board, 2, 2, 2, 3)   # adjacent empty
    assert not env._is_valid_build(env.board, 2, 2, 2, 4)  # non-adjacent
    assert not env._is_valid_build(env.board, 2, 2, 2, 2)  # where worker stands
    env.board[2][3] = (4, None)
    assert not env._is_valid_build(env.board, 2, 2, 2, 3)  # on a dome


def test_valid_move_execution_and_rotation():
    env = _fresh(2)
    assert env.state.current_player_id == 0
    done, _ = env.step("N1C2C3B2")  # Navy 1: C2 -> C3, build B2
    assert not done
    assert env.board[2][1][1] is None       # source cleared
    assert env.board[2][2][1] == (0, 1)     # worker at C3
    assert env.board[1][1][0] == 1          # B2 built to height 1
    assert env.state.current_player_id == 1  # rotated to White


def test_scripted_win_by_reaching_level_three():
    env = _fresh(2)
    # Stage a level-2 worker beside a level-3 cell; moving up wins.
    env.board[2][1] = (2, (0, 1))  # Navy 1 at C2, height 2
    env.board[2][2] = (3, None)    # C3 at height 3 (empty)
    done, _ = env.step("N1C2C3B2")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.board[1][1][0] == 0  # winning ends before the submitted build


def test_winning_move_does_not_require_build_coordinate():
    env = _fresh(2)
    env.board[2][1] = (2, (0, 1))
    env.board[2][2] = (3, None)
    assert "N1C2C3" in env._get_valid_moves(0).split(", ")
    done, _ = env.step("N1C2C3")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_moving_from_level_three_does_not_win():
    env = _fresh(2)
    env.board[2][1] = (3, (0, 1))
    env.board[2][2] = (2, None)
    done, _ = env.step("N1C2C3B2")
    assert not done
    assert env.state.current_player_id == 1


def test_invalid_build_is_atomic():
    env = _fresh(2)
    before = copy.deepcopy(env.board)
    done, _ = env.step("N1C2C3E5")
    assert not done
    assert env.board == before
    assert env.state.current_player_id == 0


def test_helpers_reject_out_of_bounds_coordinates():
    env = _fresh(2)
    assert not env._is_valid_move(-1, 0, 0, 0)
    assert not env._is_valid_move(0, 0, 5, 0)
    assert not env._is_valid_build(env.board, 0, 0, -1, 0)
    assert not env._is_valid_build(env.board, 0, 0, 0, 5)


def test_three_player_blocked_player_is_eliminated_and_skipped():
    env = _fresh(3)
    env.board = [[(0, None) for _ in range(5)] for _ in range(5)]
    env.board[0][0] = (0, (0, 1))
    env.board[0][1] = (0, (0, 2))
    env.board[4][4] = (0, (1, 1))
    env.board[4][3] = (0, (1, 2))
    env.board[2][2] = (0, (2, 1))
    env.board[2][3] = (0, (2, 2))
    for row in range(3, 5):
        for col in range(2, 5):
            if env.board[row][col][1] is None:
                env.board[row][col] = (4, None)

    done, _ = env.step("N1A1B1A1")
    assert not done
    assert 1 in env.state.eliminated
    assert env.state.current_player_id == 2
    assert not any(
        worker is not None and worker[0] == 1
        for row in env.board
        for _, worker in row
    )


def test_each_player_sees_their_own_valid_moves_every_turn():
    env = _fresh(2)
    assert all("Valid moves" not in env.prompt(player_id) for player_id in (0, 1))

    env.step("N1C2C3B2")
    white_view = env.render(1)
    assert f"Valid moves: {env._get_valid_moves(1)}" in white_view
    assert "N1" not in white_view.split("Valid moves:")[1]

    env.step(env._get_valid_moves(1).split(", ")[0])
    assert f"Valid moves: {env._get_valid_moves(0)}" in env.render(0)


def test_hidden_valid_moves_and_hidden_board_render_nothing():
    env = _fresh(2, is_open=False, show_valid=False)
    assert env.render(0) is None
    assert "board is not shown" in env.prompt(0)


@pytest.mark.parametrize("num_players", [2, 3])
def test_prompt_example_is_legal_for_each_player(num_players):
    env = _fresh(num_players)
    for player_id in range(num_players):
        prompt = env.prompt(player_id)
        example = prompt.split("Example: ")[1].split()[0]
        assert example in env._get_valid_moves(player_id).split(", ")
    assert ("last player remaining wins" in env.prompt(0)) == (num_players == 3)


def _eliminate_by_invalid_moves(env, player_id):
    assert env.state.current_player_id == player_id
    for _ in range(env.error_allowance + 1):
        env.step("garbage")


def test_three_player_invalid_elimination_removes_workers_and_passes_turn():
    env = _fresh(3)
    env.step(env._get_valid_moves(0).split(", ")[0])

    _eliminate_by_invalid_moves(env, 1)

    assert env.state.eliminated == [1] and not env.state.done
    assert not any(worker is not None and worker[0] == 1 for row in env.board for _, worker in row)
    assert env.state.current_player_id == 2
    assert env.game_state["valid_moves"] == env._get_valid_moves(2)


def test_three_player_invalid_elimination_also_eliminates_a_blocked_next_player():
    env = _fresh(3)
    env.board = [[(0, None) for _ in range(5)] for _ in range(5)]
    env.board[0][0] = (0, (0, 1))
    env.board[0][2] = (0, (0, 2))
    env.board[2][2] = (0, (1, 1))
    env.board[2][3] = (0, (1, 2))
    env.board[4][4] = (0, (2, 1))
    env.board[4][3] = (0, (2, 2))
    for row, col in [(3, 2), (3, 3), (3, 4), (4, 2)]:
        env.board[row][col] = (4, None)  # Grey's workers are walled in by domes
    env.step("N1A1B1A1")
    assert env.state.current_player_id == 1

    done = False
    for _ in range(env.error_allowance + 1):
        done, _ = env.step("garbage")

    assert done
    assert env.state.rewards == {0: 1, 1: -1, 2: -1}


def test_snapshot_restore_recovers_board_valid_moves_and_turn():
    env = _fresh(2)
    snapshot = env.snapshot()
    env.step("N1C2C3B2")
    env.restore(snapshot)
    assert env.state.current_player_id == 0
    assert env.board[2][1][1] == (0, 1)
    assert env.board[1][1][0] == 0
    assert env.game_state["valid_moves"] == env._get_valid_moves(0)


def test_invalid_format_increments_error():
    env = _fresh(2)
    done, _ = env.step("I have no idea how to move")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # no rotation on invalid move


def test_moving_opponents_worker_is_invalid():
    env = _fresh(2)
    # Navy (P0) attempts to move a White worker.
    done, _ = env.step("W1D3D2E2")
    assert not done
    assert env.state.error_count == 1


def test_illegal_wellformed_move_is_rejected():
    env = _fresh(2)
    # Correct format but there is no Navy worker at A1.
    done, _ = env.step("N1A1A2A3")
    assert not done
    assert env.state.error_count == 1


def test_random_play_reaches_a_winner():
    random.seed(112)
    env = _fresh(2)
    done = False
    turn_count = 0
    while not done and turn_count < 1000:
        current = env.state.current_player_id
        valid_moves = env._get_valid_moves(current).split(", ")
        assert valid_moves, "current player should always have a move before game end"
        done, _ = env.step(random.choice(valid_moves))
        turn_count += 1
    assert done
    assert 1 in env.state.rewards.values()
    assert -1 in env.state.rewards.values()
