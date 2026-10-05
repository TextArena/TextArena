"""Deterministic game-logic tests for Checkers-v1."""
import copy
import re

import pytest

from textarena.envs.Checkers.env import CheckersEnv


def _fresh(max_turns=50):
    env = CheckersEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def _clear(board):
    for r in range(8):
        for c in range(8):
            board[r][c] = "."


def test_reset_board_layout():
    env = _fresh()
    board = env.state.game_state["board"]
    assert sum(cell.lower() == "b" for row in board for cell in row) == 12
    assert sum(cell.lower() == "r" for row in board for cell in row) == 12
    assert env.state.current_player_id == 0


def test_simple_move_and_rotation():
    env = _fresh()
    done = env.step("5 0 4 1")  # Red advances diagonally forward
    assert not done
    board = env.state.game_state["board"]
    assert board[4][1] == "r" and board[5][0] == "."
    assert env.state.current_player_id == 1


def test_capture_removes_jumped_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    board[4][3] = "b"  # place an enemy piece to jump
    done = env.step("5 2 3 4")
    assert not done
    assert board[3][4] == "r"      # red landed here
    assert board[4][3] == "."      # jumped black removed


def test_capture_is_mandatory_and_invalid_move_is_atomic():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[5][2] = "r"
    board[4][3] = "b"
    before = copy.deepcopy(board)
    done = env.step("5 0 4 1")
    assert not done
    assert board == before
    assert env.state.current_player_id == 0


def test_multi_jump_keeps_turn_and_forces_same_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    done = env.step("5 0 3 2")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.game_state["forced_piece"] == (3, 2)
    assert env.state.game_state["valid_moves"] == ["3 2 1 4"]
    done = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_turn_limit_waits_for_forced_capture_chain_to_finish():
    env = _fresh(max_turns=1)
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    board[0][1] = "b"  # keeps Black alive and mobile after the chain

    done = env.step("5 0 3 2")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.game_state["forced_piece"] == (3, 2)

    done = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_man_cannot_capture_backward_but_king_can():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "r"
    board[4][3] = "b"
    before = copy.deepcopy(board)
    env.step("3 2 5 4")
    assert board == before

    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "R"
    board[4][3] = "b"
    done = env.step("3 2 5 4")
    assert done  # the only Black piece was captured
    assert board[5][4] == "R"


def test_promotion_ends_capture_turn():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][1] = "r"
    board[1][2] = "b"
    board[1][4] = "b"  # newly crowned king could jump this only on a later turn
    done = env.step("2 1 0 3")
    assert not done
    assert board[0][3] == "R"
    assert env.state.game_state["forced_piece"] is None
    assert env.state.current_player_id == 1


def test_valid_move_generation_and_turn_limit_draw():
    env = _fresh(max_turns=1)
    assert "5 0 4 1" in env.state.game_state["valid_moves"]
    done = env.step("5 0 4 1")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_capturing_last_piece_wins():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "r"
    board[2][3] = "b"  # black's only remaining piece
    done = env.step("3 2 1 4")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done = env.step("move up")
    assert not done
    assert env.state.error_count == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("move up")
    assert f"Expected {env.action_format}." in _invalid_feedback(env)[0]

    assert "'5 0 4 1' as Red or '2 1 3 2' as Black" in env.action_format
    fresh = _fresh()
    fresh.step("5 0 4 1")
    fresh.step("2 1 3 2")
    assert fresh.state.turn == 2 and fresh.state.error_count == 0


def test_illegal_move_increments_error_count():
    env = _fresh()
    done = env.step("5 0 3 0")  # straight two-square move is illegal
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done = env.step("garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def _invalid_feedback(env):
    return [message for _, message in env.state.logs if "attempted an invalid move" in message]


def _double_jump_position(env):
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"
    board[0][7] = "b"  # keeps Black alive after the double jump
    board[6][7] = "r"
    env.state.game_state["valid_moves"] = env._legal_moves(0)
    return board


def test_multi_jump_continuation_is_announced_and_rendered():
    env = _fresh()
    _double_jump_position(env)

    env.step("5 0 3 2")

    assert env.state.current_player_id == 0
    assert "Player 0 must continue jumping with the piece on (3,2)." in [message for _, message in env.state.logs]
    rendered = env.render(0)
    assert "jump again with your piece on (3,2)" in rendered and "Legal jumps: 3 2 1 4" in rendered

    env.step("3 2 1 4")
    assert "jump again" not in env.render(env.state.current_player_id)


def test_moving_another_piece_mid_chain_names_the_jumping_piece():
    env = _fresh()
    _double_jump_position(env)
    env.step("5 0 3 2")

    env.step("6 7 5 6")

    feedback = _invalid_feedback(env)
    assert len(feedback) == 1 and "continue jumping with your piece on (3,2)" in feedback[0]


def test_ignoring_a_mandatory_capture_explains_the_rule():
    env = _fresh()
    _double_jump_position(env)

    env.step("6 7 5 6")

    feedback = _invalid_feedback(env)
    assert len(feedback) == 1
    assert "captures are mandatory" in feedback[0] and "Legal moves: 5 0 3 2" in feedback[0]


def test_backward_man_move_explains_direction():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[3][2] = "r"
    board[0][7] = "b"

    env.step("3 2 4 3")

    assert "only kings may move backward" in _invalid_feedback(env)[0]


def test_capture_that_ends_the_game_does_not_leave_a_continuation():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[5][0] = "r"
    board[4][1] = "b"
    board[2][3] = "b"  # Black's last pieces: the double jump captures both

    env.step("5 0 3 2")
    done = env.step("3 2 1 4")

    assert done and env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["forced_piece"] is None
    assert "jump again" not in env.render(0)


@pytest.mark.parametrize("player_id", [0, 1])
def test_prompt_example_is_legal_and_rules_are_complete(player_id):
    env = _fresh(max_turns=80)
    prompt = env.prompt(player_id)

    example = re.search(r"e\.g\. '(\d \d \d \d)'", prompt).group(1)
    assert example in env._legal_moves(player_id)
    assert "draw after 80 turns" in prompt
    assert "a king moves one square diagonally in any direction" in prompt
    assert "landing square" in prompt
