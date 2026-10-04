"""Deterministic game-logic tests for FifteenPuzzle (single player).

The board is randomly shuffled, so tests that need a specific layout overwrite
``env.board`` directly.
"""
import copy
import re

import pytest

import textarena as ta
from textarena.envs.FifteenPuzzle.env import FifteenPuzzleEnv


def _fresh():
    env = FifteenPuzzleEnv()
    env.reset(num_players=1, seed=42)
    return env


def _set_board(env, board):
    env.board = board
    env.state.game_state["board"] = board


def test_valid_move_slides_tile():
    env = _fresh()
    # Empty in the middle; sliding 'up' pulls the tile below into it.
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
    done, _ = env.step("up")
    assert not done
    # The 11 tile below the blank should have moved up into (2, 2).
    assert env.board[2][2] == 11 and env.board[3][2] is None
    assert env.state.game_state["rendered_board"] == env._render_board(env.board)


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("go up please")  # not a bare direction word
    assert not done and env.state.error_count == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("go up please")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    directions = re.findall(r"'([a-z]+)'", env.action_format)
    assert directions == ["up", "down", "left", "right"]
    for direction in directions:  # with the blank in the middle every direction is legal
        fresh = _fresh()
        _set_board(fresh, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
        fresh.step(direction)
        assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_illegal_direction_rejected():
    env = _fresh()
    # Blank on the bottom row (and board NOT solved) -> 'up' has no tile below it.
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [None, 13, 14, 15]])
    done, _ = env.step("up")
    assert not done and env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("still garbage")
    assert done and env.state.game_info[0]["invalid_move"] is True


def test_solving_puzzle_wins():
    env = _fresh()
    # One legal move away from solved: blank at (3,2), 15 to its right.
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, None, 15]])
    done, _ = env.step("left")  # slide the 15 into place
    assert done and env.state.rewards == {0: 1}
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def _is_solvable(board):
    flat = [tile for row in board for tile in row]
    numbered = [tile for tile in flat if tile is not None]
    inversions = sum(
        left > right
        for idx, left in enumerate(numbered)
        for right in numbered[idx + 1 :]
    )
    blank_row_from_bottom = 4 - flat.index(None) // 4
    return (inversions + blank_row_from_bottom) % 2 == 1


def test_many_seeded_boards_are_solvable_nonterminal_and_reproducible():
    for seed in range(100):
        first = FifteenPuzzleEnv(max_turns=50)
        second = FifteenPuzzleEnv(max_turns=50)
        first.reset(num_players=1, seed=seed)
        second.reset(num_players=1, seed=seed)
        assert first.board == second.board
        assert _is_solvable(first.board)
        assert not first._is_solved()


@pytest.mark.parametrize("action", ["[up", "up]", "go up", "up down", "north"])
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_directions_are_case_insensitive():
    env = _fresh()
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
    done, _ = env.step("UP")
    assert not done
    assert env.board[2][2] == 11


def test_illegal_move_is_atomic():
    env = _fresh()
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [None, 13, 14, 15]])
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("up")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_dynamic_render_cannot_go_stale():
    env = _fresh()
    board = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, None, 15]]
    env.board = board
    env.state.game_state["rendered_board"] = "stale"
    rendered = env.render(0)
    assert "13 14 __ 15" in rendered
    assert env.state.game_state["rendered_board"] == env._render_board(board)


@pytest.mark.parametrize("max_turns,seed", [(12, 915), (12, 3633), (14, 12305), (16, 2784)])
def test_generator_never_starts_on_the_solved_board(max_turns, seed):
    env = FifteenPuzzleEnv(max_turns=max_turns)
    env.reset(num_players=1, seed=seed)
    assert not env._is_solved()
    assert _is_solvable(env.board)


def test_each_move_delivers_exactly_one_board():
    env = _fresh()
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
    env.get_observation()
    env.step("up")
    _, observation = env.get_observation()
    boards = [message for _, message, kind in observation if kind == ta.ObservationType.GAME_BOARD]
    assert len(boards) == 1 and "Available Moves" in boards[0]


def test_partial_reward_stays_below_a_win_when_solved_tiles_are_displaced():
    env = FifteenPuzzleEnv(max_turns=1)
    env.reset(num_players=1, seed=42)
    env.state.game_state["initial_board"] = [[2, 3, 1, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, None]]
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
    done, _ = env.step("up")  # every scrambled tile is fixed, but 15 and the gap are swapped
    assert done and not env._is_solved()
    assert env.state.rewards == {0: pytest.approx(1 / 3)}


def test_unknown_direction_is_reported_as_such():
    env = _fresh()
    env.get_observation()
    env.step("north")
    _, observation = env.get_observation()
    assert any("Unknown direction 'north'" in message for _, message, _ in observation)


def test_turn_limit_counts_final_move_and_returns_partial_reward():
    env = FifteenPuzzleEnv(max_turns=1)
    env.reset(num_players=1, seed=42)
    _set_board(env, [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, None, 12], [13, 14, 11, 15]])
    env.state.game_state["initial_board"] = copy.deepcopy(env.board)
    done, _ = env.step("right")
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert 0.0 <= env.state.rewards[0] < 1.0
