"""Deterministic offline tests for the Othello environment.

Player 0 is Black (moves first), Player 1 is White.
"""
import re

import pytest

from textarena.envs.Othello.env import OthelloEnv


def _fresh(board_size=8):
    env = OthelloEnv(board_size=board_size)
    env.reset(num_players=2, seed=42)
    return env


def test_initial_valid_moves_4x4():
    env = _fresh(board_size=4)
    assert env.state.game_state["valid_moves"] == [[0, 1], [1, 0], [2, 3], [3, 2]]


def test_valid_move_flips_pieces():
    env = _fresh(board_size=8)
    done = env.step("2, 3")  # Black flanks the white piece at (3,3)
    assert not done
    assert env.state.game_state["black_count"] == 4
    assert env.state.game_state["white_count"] == 1
    assert env.state.current_player_id == 1


def test_forced_pass_keeps_actor_and_synchronizes_valid_moves():
    env = _fresh(board_size=4)
    board = env.state.game_state["board"]
    for row in board:
        row[:] = [""] * 4
    board[0][0], board[0][1] = "B", "W"
    board[1][0], board[1][1] = "B", "W"

    done = env.step("0, 2")

    assert not done
    assert env.state.current_player_id == 0
    assert [1, 2] in env.state.game_state["valid_moves"]
    assert env.state.game_state["valid_moves"] == env._valid_moves(board, "B")
    assert env.state.game_state["black_count"] == 4
    assert env.state.game_state["white_count"] == 1


def test_full_game_white_wins_on_4x4():
    env = _fresh(board_size=4)
    # Greedy first-valid-move line for both sides on the 4x4 board.
    seq = [
        "0, 1", "0, 0", "1, 0", "0, 2", "0, 3", "2, 0",
        "3, 0", "1, 3", "2, 3", "3, 1", "3, 2", "3, 3",
    ]
    done = False
    for a in seq:
        done = env.step(a)
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.game_state["white_count"] == 10
    assert env.state.game_state["black_count"] == 6


def test_invalid_format_increments_error():
    env = _fresh()
    done = env.step("row two col three")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("board_size", [8, 4, 6, 10, 14])
def test_format_error_describes_expected_action(board_size):
    env = _fresh(board_size=board_size)
    env.step("row two col three")
    assert f"Expected {env.action_format}." in _invalid_feedback(env)[0]
    assert f"each from 0 to {board_size - 1}," in env.action_format

    example = re.search(r"for example '([^']+)'", env.action_format).group(1)
    fresh = _fresh(board_size=board_size)
    fresh.step(example)
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_compact_ambiguous_coordinates_are_rejected():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]

    done = env.step("23")

    assert not done
    assert env.state.game_state["board"] == before
    assert env.state.error_count == 1


@pytest.mark.parametrize("action, accepted", [
    ("(2, 3)", True), ("( 2 3 )", True), ("(2,3)", True), ("(2, 3", False), ("2, 3)", False), ("((2, 3))", False),
])
def test_parenthesized_moves_like_the_announcements_are_accepted(action, accepted):
    env = _fresh()
    env.step(action)
    assert (env.state.game_state["board"][2][3] == "B") == accepted
    assert env.state.error_count == (0 if accepted else 1)


def test_prompt_explains_flanking_in_plain_words():
    prompt = _fresh().prompt(0)
    assert "pieces-in" not in prompt and ")-between" not in prompt
    assert "at least one unbroken straight line (horizontal, vertical, or diagonal) of your opponent's pieces" in prompt


def test_huge_coordinate_is_rejected_atomically():
    env = _fresh()
    before = env.snapshot()

    done = env.step(f"{'9' * 5000}, 0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before["state"].game_state


def test_illegal_move_rejected():
    env = _fresh(board_size=8)
    done = env.step("0, 0")  # not a legal opening move
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("board_size", [4, 6, 10, 14])
def test_terminal_renderer_supports_registered_sizes(board_size):
    env = _fresh(board_size=board_size)
    rendered = env.get_board_str()
    label_width = len(str(board_size - 1))
    expected_header = " " * (label_width + 2) + "".join(f"{i:^4}" for i in range(board_size))
    assert expected_header in rendered
    assert rendered.count(" │ ") == board_size * board_size
    assert env.state.game_state["rendered_board"] == rendered
    assert rendered in env.render(0)
    lines = rendered.splitlines()
    assert len(lines[0]) == len(lines[1]) == len(lines[2])


def test_renderer_draws_black_hollow_and_white_filled():
    rendered = _fresh(board_size=4).get_board_str().splitlines()
    # Initial position: White on (1,1) and (2,2), Black on (1,2) and (2,1).
    assert rendered[4] == "1 │   │ ● │ ○ │   │"
    assert rendered[6] == "2 │   │ ○ │ ● │   │"


def test_prompt_and_board_legend_match_rendered_symbols():
    env = _fresh(board_size=4)

    for player_id, own in [(0, "○"), (1, "●")]:
        prompt = env.prompt(player_id)
        assert "Black discs are shown as '○' and White discs as '●'" in prompt
        assert f"your discs are '{own}'" in prompt
        assert "(B)" not in prompt and "(W)" not in prompt
    assert "Scores - Black ○: 2, White ●: 2" in env.render(0)


def test_move_and_skip_announcements_use_rendered_symbols():
    env = _fresh(board_size=4)
    board = env.state.game_state["board"]
    for row in board:
        row[:] = [""] * 4
    board[0][0], board[0][1] = "B", "W"
    board[1][0], board[1][1] = "B", "W"

    env.step("0, 2")

    messages = [message for _, message in env.state.logs]
    assert "Player 0 (Black ○) played (0, 2) flipping 1 piece(s)" in messages
    assert "Player 1 (White ●) has no valid moves and must skip." in messages


def _invalid_feedback(env):
    return [message for _, message in env.state.logs if "attempted an invalid move" in message]


def test_hidden_valid_moves_are_not_leaked_by_invalid_feedback():
    env = OthelloEnv(board_size=8, show_valid=False)
    env.reset(num_players=2, seed=0)

    env.step("0, 0")

    feedback = _invalid_feedback(env)
    assert len(feedback) == 1
    assert "Valid moves" not in feedback[0] and "2, 3" not in feedback[0]
    assert "flip at least one" in feedback[0]
    assert "Valid moves" not in env.render(0)


def test_visible_valid_moves_are_repeated_in_invalid_feedback():
    env = _fresh(board_size=8)

    env.step("0, 0")

    assert "Valid moves: '2, 3', '3, 2', '4, 5', '5, 4'" in _invalid_feedback(env)[0]


def test_prompt_explains_passing_and_game_end():
    prompt = _fresh(board_size=4).prompt(1)

    assert "turn is skipped automatically" in prompt
    assert "equal counts are a draw" in prompt
    assert "numbered from 0" in prompt


def test_odd_board_size_rejected():
    with pytest.raises(ValueError, match="board_size must be an even integer of at least 4"):
        OthelloEnv(board_size=5)
