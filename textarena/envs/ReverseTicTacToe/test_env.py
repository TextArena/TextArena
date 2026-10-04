"""Deterministic offline tests for the ReverseTicTacToe environment.

Completing three-in-a-row LOSES. Player 0 is 'O', Player 1 is 'X'; P0 moves first.
Moves are the bare cell index 0-8, e.g. '4'.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.ReverseTicTacToe.env import ReverseTicTacToeEnv


def _fresh():
    env = ReverseTicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_completing_a_line_loses():
    env = _fresh()
    # P0 is forced to build the top row (0,1,2) and thus loses to P1.
    done = False
    for a in ["0", "3", "1", "4", "2"]:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_full_board_without_line_is_draw():
    env = _fresh()
    # Fills the board so neither symbol forms a line:
    #   O X O / X X O / O O X
    seq = ["0", "1", "2", "3", "5", "4", "6", "8", "7"]
    done = False
    for a in seq:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("place at four")
    assert not done
    assert env.state.error_count == 1


def test_occupied_cell_rejected():
    env = _fresh()
    env.step("0")               # P0 -> O at cell 0
    done, _ = env.step("0")     # P1 tries the same cell
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1


def test_out_of_range_cell_rejected():
    env = _fresh()
    done, _ = env.step("99")
    assert not done
    assert env.state.error_count == 1


def test_player_one_can_lose_by_completing_a_line():
    env = _fresh()

    for action in ("3", "0", "4", "1", "8", "2"):
        done, _ = env.step(action)

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_anti_diagonal_loss_branch():
    env = _fresh()

    for action in ("2", "0", "4", "1", "6"):
        done, _ = env.step(action)

    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_column_loss_branch():
    env = _fresh()

    for action in ("0", "1", "3", "2", "6"):
        done, _ = env.step(action)

    assert done
    assert env.state.rewards == {0: -1, 1: 1}


@pytest.mark.parametrize("action", ("[0", "0]"))
def test_unbalanced_brackets_are_atomic_invalid_moves(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


def test_huge_cell_is_rejected_without_integer_conversion(monkeypatch):
    import textarena.envs.ReverseTicTacToe.env as reverse_module

    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    real_int = int

    def guarded_int(text):
        if isinstance(text, str) and len(text) > 1:
            pytest.fail("attempted to convert an unbounded cell")
        return real_int(text)

    monkeypatch.setattr(reverse_module, "int", guarded_int, raising=False)

    done, _ = env.step("9" * 100_000)

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_balanced_brackets_are_accepted():
    env = _fresh()

    done, _ = env.step("[4]")

    assert not done
    assert env.state.game_state["board"][1][1] == "O"
    assert env.state.current_player_id == 1


def test_terminal_action_is_counted_and_final_board_is_rendered():
    env = _fresh()
    for action in ("0", "3", "1", "4", "2"):
        done, _ = env.step(action)

    assert done
    assert env.state.turn == 5
    assert env.state.game_info[0]["turn_count"] == 3
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert " O | O | O " in final_board
    assert "'2'" not in final_board


def test_snapshot_and_reset_restore_empty_board_and_actor():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("0")

    env.restore(snapshot)

    assert env.state.game_state["board"] == [['', '', ''], ['', '', ''], ['', '', '']]
    assert env.state.current_player_id == 0
    assert env.state.turn == 0
    env.reset(num_players=2, seed=99)
    assert env.state.game_state["board"] == [['', '', ''], ['', '', ''], ['', '', '']]
