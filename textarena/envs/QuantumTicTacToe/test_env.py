"""Deterministic offline tests for the QuantumTicTacToe environment.

Moves place a spooky mark in two open cells ('a,b'). When a move closes a
cycle in the entanglement graph, the opponent chooses the collapse with
'collapse c' (c is a cell of the mark that closed the cycle) and then makes
their own move. Player 0 is 'O' (odd move numbers), Player 1 is 'X' (even);
Player 0 moves first.
"""
import copy

import textarena as ta
from textarena.envs.QuantumTicTacToe.env import QuantumTicTacToeEnv


def _fresh():
    env = QuantumTicTacToeEnv()
    env.reset(num_players=2, seed=42)
    return env


def _play(env, *actions):
    done = False
    for action in actions:
        assert not done, f"game ended before {action!r}"
        done = env.step(action)
        assert env.state.error_count == 0, f"{action!r} was rejected"
    return done


def _last_warning(env):
    return next(m for _, m, t, _ in reversed(env.state.events) if t == ta.ObservationType.GAME_ADMIN)


def test_player0_wins_with_solidified_row():
    env = _fresh()
    # P0 entangles cells {0,1},{1,2},{0,2}; whichever collapse P1 picks, row 0 becomes O,O,O.
    assert not _play(env, "0,1", "3,4", "1,2", "4,5", "0,2")
    assert env.state.current_player_id == 1
    assert _play(env, "collapse 0")
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["board"][0] == ["O", "O", "O"]


def test_player1_wins_with_solidified_row():
    env = _fresh()
    # Symmetric: P1 builds the collapsing triangle among cells 0,1,2 and P0 must choose its collapse.
    assert not _play(env, "3,4", "0,1", "4,5", "1,2", "6,7", "0,2")
    assert env.state.current_player_id == 0
    assert _play(env, "collapse 2")
    assert env.state.rewards == {1: 1, 0: -1}
    assert env.state.game_state["board"][0] == ["X", "X", "X"]


def test_closing_a_cycle_waits_for_the_opponent_to_choose():
    env = _fresh()
    _play(env, "0,4", "0,4")
    gs = env.game_state
    assert gs["pending_collapse"] == 1
    assert gs["board"] == [["", "", ""], ["", "", ""], ["", "", ""]]
    assert env.state.current_player_id == 0
    options = (
        "Collapse options for X2 (cells 0 and 4): 'collapse 0' puts X2 in cell 0, O1 in cell 4; "
        "'collapse 4' puts X2 in cell 4, O1 in cell 0."
    )
    messages = [message for _, message, _, to_id in env.state.events if to_id == -1]
    assert f"Mark X2 closed a cycle. Player 0 chooses how it collapses. {options}" in messages
    assert options in env.render(0) and "Submit 'collapse <cell>' to choose." in env.render(0)


def test_the_chooser_picks_either_collapse_and_then_moves():
    for choice, expected in (("collapse 0", ["X", "", ""]), ("collapse 4", ["O", "", ""])):
        env = _fresh()
        assert not _play(env, "0,4", "0,4", choice)
        gs = env.game_state
        assert gs["board"][0] == expected
        assert gs["board"][1][1] == ("O" if expected[0] == "X" else "X")
        assert gs["pending_collapse"] is None and gs["superpositions"] == {}
        assert env.state.current_player_id == 0  # the chooser now places their own mark
        assert not _play(env, "1,2")
        assert gs["superpositions"] == {2: (0, (0, 1), (0, 2))}
        assert env.state.current_player_id == 1


def test_prompt_example_matches_the_game():
    env = _fresh()
    _play(env, "0,4", "0,4", "collapse 0")
    gs = env.game_state
    assert (gs["board"][0][0], gs["classical_moves"][0][0]) == ("X", 2)
    assert (gs["board"][1][1], gs["classical_moves"][1][1]) == ("O", 1)


def test_cycle_collapse_propagates_to_dependent_marks():
    env = _fresh()
    gs = env.state.game_state
    gs["superpositions"] = {
        0: (0, (0, 0), (0, 1)),
        1: (1, (0, 1), (0, 2)),
        2: (0, (0, 0), (0, 2)),
        3: (1, (0, 1), (1, 1)),
    }
    gs["move_count"] = 4
    gs["pending_collapse"] = 2

    done = env.step("collapse 2")

    assert not done and env.state.error_count == 0
    assert gs["superpositions"] == {}
    assert gs["board"][0] == ["O", "X", "O"]
    assert gs["board"][1][1] == "X"
    assert gs["classical_moves"][0] == [1, 2, 3]
    assert gs["classical_moves"][1][1] == 4
    rendered = env.get_board_str()
    assert "O1" in rendered and "X2" in rendered and "O3" in rendered


def test_entangled_pair_order_does_not_change_the_game():
    forward = _fresh()
    reverse = _fresh()

    _play(forward, "0,1", "0,1", "collapse 0")
    _play(reverse, "0,1", "1,0", "collapse 0")

    assert reverse.state.game_state == forward.state.game_state
    assert forward.state.game_state["board"][0][:2] == ["X", "O"]


def test_placing_a_mark_while_a_collapse_is_pending_is_rejected_atomically():
    env = _fresh()
    _play(env, "0,4", "0,4")
    before = copy.deepcopy(env.game_state)
    done = env.step("1,2")
    assert not done and env.state.error_count == 1
    assert env.game_state == before
    assert env.state.current_player_id == 0
    assert "A cycle is waiting to collapse." in _last_warning(env)


def test_collapse_choices_are_validated():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    assert not env.step("collapse 0")  # nothing to collapse yet
    assert env.state.error_count == 1 and env.game_state == before
    assert "No collapse is pending." in _last_warning(env)

    env = _fresh()
    _play(env, "0,4", "0,4")
    before = copy.deepcopy(env.game_state)
    assert not env.step("collapse 3")  # not a cell of X2
    assert env.state.error_count == 1 and env.game_state == before
    assert "Choose cell 0 or 4, e.g. 'collapse 0'." in _last_warning(env)


def test_format_errors_describe_the_expected_action():
    env = _fresh()
    env.step("place somewhere")
    assert "Expected two different open cells separated by a comma, for example '0,4'." in _last_warning(env)

    env = _fresh()
    _play(env, "0,4", "0,4")
    env.step("collapse")
    assert (
        "Expected 'collapse' followed by cell 0 or 4, the two cells of mark X2, for example 'collapse 0'."
        in _last_warning(env)
    )


def test_collapse_action_tolerates_case_spacing_and_brackets():
    env = _fresh()
    _play(env, "0,4", "0,4", "[ COLLAPSE   4 ]")
    assert env.game_state["board"][1][1] == "X"


def test_two_invalid_replies_while_choosing_lose():
    env = _fresh()
    _play(env, "0,4", "0,4")
    env.step("collapse 3")
    done = env.step("2,5")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_last_open_cell_goes_to_the_chooser():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [
        ["O", "X", "O"],
        ["O", "X", "X"],
        ["X", "O", ""],
    ]
    gs["classical_moves"] = [
        [1, 2, 3],
        [5, 4, 6],
        [8, 7, None],
    ]
    gs["move_count"] = 8

    outcome = env._finish_collapse(player_id=0)

    assert gs["board"][2][2] == "O" and gs["classical_moves"][2][2] == 9
    assert outcome.rewards == {0: 0, 1: 0}


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

    outcome = env._finish_collapse(player_id=1)

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

    outcome = env._finish_collapse(player_id=1)

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

    outcome = env._finish_collapse(player_id=1)

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

    outcome = env._finish_collapse(player_id=1)

    assert outcome.rewards == {0: 0, 1: 0}


def test_invalid_format_increments_error():
    env = _fresh()
    done = env.step("place somewhere")
    assert not done
    assert env.state.error_count == 1


def test_duplicate_cell_indices_rejected():
    env = _fresh()
    done = env.step("2,2")
    assert not done
    assert env.state.error_count == 1


def test_out_of_range_cell_rejected():
    env = _fresh()
    done = env.step("9,0")
    assert not done
    assert env.state.error_count == 1


def _game_messages(env):
    return [m for f, m, t, to in env.state.events if f == -1 and to == -1 and t != ta.ObservationType.GAME_BOARD]


def test_feedback_uses_the_same_cell_numbers_as_actions():
    env = _fresh()
    for action in ["2,8", "3,4", "8,2", "collapse 2"]:  # O3 and O1 share cells 2 and 8 -> Player 1 chooses
        env.step(action)

    messages = _game_messages(env)
    assert "Player 0 placed spooky mark O1 in cells 2 and 8." in messages
    assert "Player 0 placed spooky mark O3 in cells 2 and 8." in messages
    assert "Player 1 collapsed O3 into cell 2." in messages
    assert "Superposition O3 resolved at cell 2." in messages
    assert "Superposition O1 resolved at cell 8." in messages
    assert not any("(0, 2)" in m or "(2, 2)" in m for m in messages)


def test_render_lists_open_cells_and_every_spooky_mark():
    env = _fresh()
    for action in ["4,0", "4,1", "4,2", "4,3", "4,5"]:  # five marks share cell 4
        env.step(action)

    board = env.render(1)

    assert "Spooky marks: O1 in cells 0 and 4; X2 in cells 1 and 4; O3 in cells 2 and 4; X4 in cells 3 and 4; O5 in cells 4 and 5" in board
    assert "Open cells: 0, 1, 2, 3, 4, 5, 6, 7, 8" in board
    grid = [line for line in board.splitlines() if "|" in line or line.startswith("-")]
    assert len(grid) == 5 and len({len(line) for line in grid}) == 1

    env.step("0,4")  # X6 closes the cycle 0-4
    env.step("collapse 0")  # X6 -> cell 0, then everything in that component collapses
    board = env.render(0)
    assert "Spooky marks: none" in board
    assert "X6" in board and "Open cells: 6, 7, 8" in board


def test_prompt_explains_the_collapse_choice():
    prompt = _fresh().prompt(0)
    assert "the opponent of the player who closed it chooses how" in prompt
    assert "'collapse c'" in prompt
    assert "Player 0 replies 'collapse 0' (X2 becomes classical in cell 0 and O1 in cell 4)" in prompt
    assert "filled automatically with the chooser's classical mark" in prompt


def test_non_ascii_digits_are_rejected():
    env = _fresh()
    done = env.step("0,\u0664")  # ARABIC-INDIC DIGIT FOUR
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["superpositions"] == {}


def test_huge_cell_index_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done = env.step(f"{'9' * 5000},0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state
