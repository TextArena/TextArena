"""Offline deterministic tests for the UltimateTicTacToe environment.

Ported and expanded from the original scripted 66-move replay
(textarena/tests/test_UltimateTicTacToe_v0.py). Two-player game; moves are
'macro micro' (each 0-8). A move sends the opponent to the micro-board equal
to the micro square just used, unless that board is closed (then free move).
"""
import copy

import pytest

import textarena as ta
from textarena.envs.UltimateTicTacToe.env import UltimateTicTacToeEnv


# The original scripted game: a full 66-move replay that ends in a draw.
PREDEFINED_ACTIONS = [
    '8 2', '2 8', '8 1', '1 4', '4 4', '4 7', '7 2', '2 2',
    '2 4', '4 1', '1 5', '5 3', '3 7', '7 1', '1 0', '0 7',
    '7 7', '7 4', '4 6', '6 2', '2 5', '5 2', '2 6', '6 7',
    '7 5', '5 8', '8 6', '6 3', '3 3', '3 1', '1 6', '6 0',
    '0 3', '3 4', '4 5', '5 7', '7 8', '8 7', '8 4', '4 3',
    '3 8', '3 6', '6 8', '6 1', '1 1', '1 3', '3 2', '2 3',
    '3 5', '5 0', '0 0', '0 4', '4 0', '0 6', '0 8', '0 5',
    '5 1', '1 7', '1 8', '1 2', '2 7', '2 1', '2 0', '0 1',
    '4 8', '5 4',
]


def _fresh():
    env = UltimateTicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert env.state.game_state["next_micro_board"] is None
    assert env.state.game_state["macro_board"] == [[' '] * 3 for _ in range(3)]
    assert len(env.state.game_state["board"]) == 9


def test_scripted_replay_terminates_in_draw():
    env = _fresh()
    for i, action in enumerate(PREDEFINED_ACTIONS):
        done, _ = env.step(action)
        if i < len(PREDEFINED_ACTIONS) - 1:
            assert not done, f"Game ended early at move {i}"
    # This particular 66-move replay fills every micro board without a macro
    # win, so the game ends in a draw.
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_invalid_format_rejected():
    env = _fresh()
    done, _ = env.step("no move here")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("no move here")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert "for example '7 8'" in env.action_format
    fresh = _fresh()
    fresh.step("7 8")
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_must_play_in_forced_micro_board():
    env = _fresh()
    env.step("0 0")            # p0 plays macro 0, micro 0 -> forces board 0
    assert env.state.game_state["next_micro_board"] == 0
    done, _ = env.step("1 0")  # p1 tries a different macro board
    assert not done
    assert env.state.error_count == 1


def test_occupied_cell_rejected():
    env = _fresh()
    env.step("0 0")            # p0 occupies macro 0 / micro 0
    done, _ = env.step("0 0")  # p1 forced into board 0, but cell is occupied
    assert not done
    assert env.state.error_count == 1


def test_first_move_sets_next_board():
    env = _fresh()
    done, _ = env.step("4 4")  # center board, center square -> forces board 4
    assert not done
    assert env.state.game_state["next_micro_board"] == 4
    assert env.state.current_player_id == 1
    assert env.state.game_state["board"][4][1][1] == "X"


def test_won_micro_board_preserves_played_cells():
    env = _fresh()
    board = env.state.game_state["board"][0]
    board[0] = ["X", "X", " "]
    board[1][0] = "O"
    done, _ = env.step("0 2")
    assert not done
    assert env.state.game_state["macro_board"][0][0] == "X"
    assert board[1][0] == "O"  # closing a board must not overwrite its history
    assert board[2][2] == " "


def test_drawn_micro_board_is_closed_and_releases_forced_board():
    env = _fresh()
    board = env.state.game_state["board"][0]
    board[:] = [
        [" ", "O", "X"],
        ["O", "X", "X"],
        ["O", "X", "O"],
    ]
    env.state.game_state["next_micro_board"] = 0
    done, _ = env.step("0 0")
    assert not done
    assert env.state.game_state["macro_board"][0][0] == "D"
    assert env.state.game_state["next_micro_board"] is None
    assert all(not move.startswith("0 ") for move in env.state.game_state["valid_moves"])


def test_closed_micro_board_rejection_is_atomic():
    env = _fresh()
    env.state.game_state["macro_board"][0][0] = "D"
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("0 0")
    assert not done
    assert env.state.game_state == before


def test_three_drawn_macro_cells_are_not_a_win():
    env = _fresh()
    macro = env.state.game_state["macro_board"]
    macro[0] = ["D", "D", "D"]
    assert not env._check_winner(macro)


def test_macro_win_completes_short_staged_game():
    env = _fresh()
    gs = env.state.game_state
    gs["macro_board"][0] = ["X", "X", " "]
    gs["board"][2][0] = ["X", "X", " "]
    done, _ = env.step("2 2")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_concatenated_indices_are_rejected():
    env = _fresh()
    done, _ = env.step("00")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["board"][0][0][0] == " "


def test_render_hides_unused_squares_of_closed_mini_boards():
    env = _fresh()
    board = env.state.game_state["board"][0]
    board[0] = ["X", "X", " "]
    board[1][0] = "O"
    env.step("0 2")

    view = env.render(1)

    assert "'0," not in view
    assert " X | 1 | 2 " in view


def test_render_names_the_forced_mini_board_and_its_valid_moves():
    env = _fresh()
    env.step("4 4")

    view = env.render(1)

    assert "You must play in mini-board 4." in view
    assert "Valid moves: '4 0', '4 1', '4 2', '4 3', '4 5', '4 6', '4 7', '4 8'" in view


def test_render_offers_a_free_move_when_sent_to_a_closed_board():
    env = _fresh()
    env.state.game_state["macro_board"][1][1] = "D"
    env.step("0 4")

    view = env.render(1)

    assert "You may play in any open mini-board." in view
    assert "'4 0'" not in view.split("Valid moves: ", 1)[1]


def test_game_ending_move_does_not_announce_a_next_board():
    env = _fresh()
    gs = env.state.game_state
    gs["macro_board"][0] = ["X", "X", " "]
    gs["board"][2][0] = ["X", "X", " "]
    start = len(env.state.events)

    done, _ = env.step("2 2")

    assert done
    descriptions = [
        message
        for _, message, event_type, _ in env.state.events[start:]
        if event_type == ta.ObservationType.GAME_ACTION_DESCRIPTION
    ]
    assert descriptions == ["Player 0 played in mini-board 2, square 2 (row 0, col 2)."]
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert "Valid moves" not in final_board


def test_snapshot_restore_recovers_forced_board_and_marks():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("4 4")
    env.restore(snapshot)
    assert env.state.current_player_id == 0
    assert env.state.game_state["next_micro_board"] is None
    assert env.state.game_state["board"][4][1][1] == " "
    assert len(env.state.game_state["valid_moves"]) == 81
