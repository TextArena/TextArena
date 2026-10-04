"""Deterministic tests for JoJoJoin.

Player 0 plays '■' and moves first; Player 1 plays '▲'. A move is the bare
number (0-24) of any empty cell on the 5x5 board; four marks in a row
horizontally, vertically or diagonally win.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.JoJoJoin.env import SYMBOLS, JoJoJoinEnv, create_board_str


def _fresh():
    env = JoJoJoinEnv()
    env.reset(num_players=2, seed=42)
    return env


def _play(env, *actions):
    """Play valid actions in order and return whether the game is done."""
    done = False
    for action in actions:
        assert not done, f"game ended before {action!r}"
        done, _ = env.step(action)
        assert env.state.error_count == 0, f"{action!r} was rejected"
    return done


def _marks(env):
    return [mark for row in env.game_state["board"] for mark in row]


@pytest.mark.parametrize(
    "moves",
    [
        ["1", "20", "2", "21", "3", "22", "4"],     # row 0, cells 1-4
        ["2", "0", "7", "1", "12", "3", "17"],      # column 2, rows 0-3
        ["0", "1", "6", "2", "12", "3", "18"],      # main diagonal
        ["5", "0", "11", "1", "17", "2", "23"],     # short diagonal starting at row 1
        ["4", "0", "8", "1", "12", "2", "16"],      # anti-diagonal
        ["3", "0", "8", "1", "13", "2", "18"],      # column 3 completed in the middle of the board
    ],
)
def test_player0_wins_with_four_in_a_row(moves):
    env = _fresh()
    assert _play(env, *moves)
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_info[0]["reason"] == "Player 0 has won!"


def test_completing_a_line_in_the_middle_wins():
    env = _fresh()
    assert _play(env, "10", "0", "11", "1", "13", "2", "12")  # row 2: 10, 11, _, 13 then 12 fills the gap
    assert env.state.rewards == {0: 1, 1: -1}


def test_player1_wins_with_four_in_a_row():
    env = _fresh()
    assert _play(env, "0", "4", "6", "9", "13", "14", "20", "19")
    assert env.state.rewards == {0: -1, 1: 1}


@pytest.mark.parametrize(
    "moves",
    [
        ["0", "20", "1", "21", "2"],                  # three in a row
        ["0", "20", "1", "21", "3", "22", "4"],       # four marks in a row with a gap
        ["0", "5", "6", "10", "18", "15", "24"],      # four on the main diagonal but not consecutive
    ],
)
def test_non_lines_do_not_win(moves):
    env = _fresh()
    assert not _play(env, *moves)


def test_full_board_without_four_in_a_row_is_a_draw():
    # Rows alternate AABBA / BBAAB, which has no four in a row in any direction.
    player0 = [0, 1, 4, 7, 8, 10, 11, 14, 17, 18, 20, 21, 24]
    player1 = [2, 3, 5, 6, 9, 12, 13, 15, 16, 19, 22, 23]
    moves = [str(cell) for pair in zip(player0, player1) for cell in pair] + [str(player0[-1])]
    env = _fresh()
    assert not _play(env, *moves[:-1])
    assert _play(env, moves[-1])
    assert env.state.rewards == {0: 0, 1: 0}
    assert env.state.game_info[1]["reason"] == "The game is a draw!"
    assert all(_marks(env))


def test_turn_rotation_and_marks():
    env = _fresh()
    _play(env, "12")
    assert env.state.current_player_id == 1
    _play(env, "13")
    assert env.game_state["board"][2][2] == SYMBOLS[0] == "\u25a0"
    assert env.game_state["board"][2][3] == SYMBOLS[1] == "\u25b2"


def test_occupied_cell_is_invalid_and_allows_resubmit():
    env = _fresh()
    _play(env, "12")
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("12")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1
    assert env.game_state == before
    assert not _play(env, "13")


@pytest.mark.parametrize("action, shown", [("25", "25"), ("99", "99"), ("100", "100"), ("9" * 10_000, "999999...")])
def test_out_of_range_cells_are_invalid_and_atomic(action, shown):
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.game_state == before
    _, message, _, _ = env.state.events[-2]  # the invalid-move notice precedes the re-sent board
    assert f"Reason: {shown} is not a valid cell. Must be between 0 and 24." in message


@pytest.mark.parametrize("action", ["12 please", "cell 12", "-1", "1.5", "", "<action>12</action>", "twelve", "\u0661\u0662", "1 2"])
def test_malformed_moves_are_rejected(action):
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.game_state == before


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("cell 12")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert env.action_format == "a cell number from 0 to 24, for example '12'"
    fresh = _fresh()
    _play(fresh, "12")
    assert fresh.state.turn == 1


@pytest.mark.parametrize("action, cell", [(" 7 ", 7), ("007", 7), ("0", 0), ("24", 24)])
def test_lenient_but_unambiguous_formats_are_accepted(action, cell):
    env = _fresh()
    _play(env, action)
    assert _marks(env)[cell] == SYMBOLS[0]


def test_two_consecutive_invalid_moves_lose():
    env = _fresh()
    env.step("not a move")
    done, _ = env.step("still bad")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.game_info[0]["invalid_move"]


def test_render_lists_bare_available_moves():
    env = _fresh()
    initial = env.render(0)
    assert initial.endswith("Available Moves: " + ", ".join(f"'{i}'" for i in range(25)))
    _play(env, "0", "24")
    rendered = env.render(0)
    assert "'0'" not in rendered.split("Available Moves:")[1]
    assert "'24'" not in rendered.split("Available Moves:")[1]
    assert env.get_board_str() == create_board_str(env.game_state["board"])
    assert env.get_board_str() in rendered
    first_row = env.get_board_str().splitlines()[0].split("|")
    assert first_row[0].strip() == SYMBOLS[0] and first_row[1].strip() == "1"
    assert env.get_board_str().splitlines()[-1].split("|")[-1].strip() == SYMBOLS[1]


def test_prompt_teaches_bare_moves_and_symbols():
    env = _fresh()
    prompt0, prompt1 = env.prompt(0), env.prompt(1)
    assert "e.g. '12'" in prompt0
    assert "[" not in prompt0 and "]" not in prompt0
    assert f"you are '{SYMBOLS[0]}'; your opponent is '{SYMBOLS[1]}'" in prompt0
    assert f"you are '{SYMBOLS[1]}'; your opponent is '{SYMBOLS[0]}'" in prompt1


def test_initial_observation_contains_prompt_and_board():
    env = _fresh()
    pid, observation = env.get_observation()
    assert pid == 0
    assert [kind for _, _, kind in observation] == [ta.ObservationType.PROMPT, ta.ObservationType.GAME_BOARD]


def test_snapshot_restore_replays_identically():
    env = _fresh()
    _play(env, "12", "6")
    snapshot = env.snapshot()
    _play(env, "13", "7", "11", "8", "14")
    first = (copy.deepcopy(env.game_state), env.state.rewards)
    env.restore(snapshot)
    _play(env, "13", "7", "11", "8", "14")
    assert (env.game_state, env.state.rewards) == first
    assert env.state.rewards == {0: 1, 1: -1}


def test_registered_variants():
    for env_id in ("JoJoJoin-v0", "JoJoJoin-v0-mdp"):
        env = ta.make(env_id)
        env.reset(num_players=2, seed=1)
        done, _ = env.step("12")
        assert not done and env.state.error_count == 0
