"""Deterministic game-logic tests for TicTacToe-v0.

Player 0 plays 'O' and moves first; Player 1 plays 'X'. Moves are the
bare cell index 0-8, e.g. '4'.
"""
import copy

import textarena as ta
from textarena.envs.TicTacToe.env import TicTacToeEnv


def _fresh():
    env = TicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_player0_wins_top_row():
    env = _fresh()
    # O: 0,1,2 (top row) | X: 3,4 (blocked too late)
    for action in ["0", "3", "1", "4", "2"]:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_full_board_is_a_draw():
    env = _fresh()
    # Final board (O=0,1,5,6,8 / X=2,3,4,7) contains no three-in-a-row.
    moves = ["0", "2", "1", "3", "5", "4", "6", "7", "8"]
    done = False
    for action in moves:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_occupied_cell_is_invalid_then_allows_resubmit():
    env = _fresh()
    env.step("0")   # P0 -> O at 0
    env.step("4")   # P1 -> X at 4
    # P0 tries to play the occupied center cell.
    done, _ = env.step("4")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # still P0's turn after invalid


def test_two_consecutive_invalid_moves_end_the_game():
    env = _fresh()
    env.step("not a move")          # first invalid -> warning, error_count=1
    done, _ = env.step("still bad") # exceeds error_allowance -> P0 loses
    assert done
    assert env.state.rewards[0] == -1
    assert env.state.rewards[1] == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("the middle square")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert "for example '4'" in env.action_format
    fresh = _fresh()
    fresh.step("4")
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_out_of_range_cell_is_invalid():
    env = _fresh()
    done, _ = env.step("99")
    assert not done
    assert env.state.error_count == 1


def test_unbounded_numeric_input_is_rejected_without_integer_conversion():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("9" * 10_000)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before
    assert env.state.current_player_id == 0
