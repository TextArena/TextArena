"""Offline deterministic tests for the WildTicTacToe environment.

WildTicTacToe is a 2-player game where each turn a player places EITHER an 'X'
or an 'O' in any empty cell. A player wins immediately by completing a line of
three identical marks (regardless of who placed them). Move format: 'X 4'.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.WildTicTacToe.env import WildTicTacToeEnv


def _fresh():
    env = WildTicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert env.state.rewards is None
    # Board starts empty (3x3 of empty strings).
    assert env.state.game_state["board"] == [['', '', ''], ['', '', ''], ['', '', '']]


def test_player0_wins_with_three_x():
    env = _fresh()
    # p0 places X in the top row while p1 places O elsewhere.
    for a in ["X 0", "O 3", "X 1", "O 4", "X 2"]:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_full_board_is_a_draw():
    env = _fresh()
    # A proper 2-coloring of the board with no monochromatic line.
    #   X X O
    #   O O X
    #   X O X
    moves = ["X 0", "X 1", "O 2", "O 3", "O 4",
             "X 5", "X 6", "O 7", "X 8"]
    done = False
    for a in moves[:-1]:
        done, _ = env.step(a)
        assert not done
    done, _ = env.step(moves[-1])
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_invalid_format_is_rejected_but_game_continues():
    env = _fresh()
    done, _ = env.step("Z 0")  # bad mark -> regex miss
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # no rotation on invalid
    # A valid resubmission is accepted and rotates the turn.
    done, _ = env.step("X 0")
    assert not done
    assert env.state.current_player_id == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("Z 0")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert "for example 'X 4'" in env.action_format
    fresh = _fresh()
    fresh.step("X 4")
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_occupied_cell_is_rejected():
    env = _fresh()
    env.step("X 0")           # p0 -> cell 0
    done, _ = env.step("O 0")  # p1 tries the occupied cell
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1


def test_out_of_range_cell_is_rejected():
    env = _fresh()
    done, _ = env.step("X 9")
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("Z 0")            # first invalid (error_allowance=1)
    done, _ = env.step("Z 1")  # second consecutive invalid -> loss
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_player_wins_by_completing_marks_started_by_opponent():
    env = _fresh()

    for action in ("X 0", "X 1", "O 3", "X 2"):
        done, _ = env.step(action)

    assert done
    assert env.state.turn == 4
    assert env.state.rewards == {0: -1, 1: 1}


def test_anti_diagonal_win_branch():
    env = _fresh()

    for action in ("X 2", "O 0", "X 4", "O 1", "X 6"):
        done, _ = env.step(action)

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_column_win_branch():
    env = _fresh()

    for action in ("X 0", "O 1", "X 3", "O 2", "X 6"):
        done, _ = env.step(action)

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


@pytest.mark.parametrize("action", ("[X 0", "X 0]"))
def test_unbalanced_brackets_are_atomic_invalid_moves(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


def test_huge_cell_is_rejected_without_integer_conversion(monkeypatch):
    import textarena.envs.WildTicTacToe.env as wild_module

    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    real_int = int

    def guarded_int(text):
        if isinstance(text, str) and len(text) > 1:
            pytest.fail("attempted to convert an unbounded cell")
        return real_int(text)

    monkeypatch.setattr(wild_module, "int", guarded_int, raising=False)

    done, _ = env.step(f"X {'9' * 100_000}")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before
    admin_messages = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_ADMIN
    ]
    assert len(admin_messages[-1]) < 500


def test_lowercase_balanced_action_is_accepted():
    env = _fresh()

    done, _ = env.step("[x 4]")

    assert not done
    assert env.state.game_state["board"][1][1] == "X"
    assert env.state.current_player_id == 1


def test_terminal_action_is_counted_and_final_board_is_rendered():
    env = _fresh()
    for action in ("X 0", "O 3", "X 1", "O 4", "X 2"):
        done, _ = env.step(action)

    assert done
    assert env.state.turn == 5
    assert env.state.game_info[0]["turn_count"] == 3
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert " X | X | X " in final_board
    assert "'2'" not in final_board


def test_snapshot_and_reset_restore_empty_board_and_actor():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("X 0")

    env.restore(snapshot)

    assert env.state.game_state["board"] == [['', '', ''], ['', '', ''], ['', '', '']]
    assert env.state.current_player_id == 0
    assert env.state.turn == 0
    env.reset(num_players=2, seed=99)
    assert env.state.game_state["board"] == [['', '', ''], ['', '', ''], ['', '', '']]
