"""Deterministic game-logic tests for Alquerque-v1."""
import re

from textarena.envs.Alquerque.env import AlquerqueEnv


def _fresh():
    env = AlquerqueEnv()
    env.reset(num_players=2, seed=42)
    return env


def _clear(board):
    for r in range(5):
        for c in range(5):
            board[r][c] = ""


def test_reset_initial_board():
    env = _fresh()
    board = env.state.game_state["board"]
    # Black occupies top two rows, Red the bottom two, middle row empty.
    assert all(board[0][c] == "B" and board[1][c] == "B" for c in range(5))
    assert all(board[2][c] == "" for c in range(5))
    assert all(board[3][c] == "R" and board[4][c] == "R" for c in range(5))
    assert env.state.current_player_id == 0


def test_forward_move_mutates_board_and_rotates():
    env = _fresh()
    # cell 17 = row3,col2 (R) -> cell 12 = row2,col2 (empty), a legal forward step.
    done, _ = env.step("17 12")
    assert not done
    board = env.state.game_state["board"]
    assert board[2][2] == "R" and board[3][2] == ""
    assert env.state.current_player_id == 1  # turn rotated
    assert env.get_board_str() == env._render_board()


def test_capture_awards_score_and_removes_piece():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # cell 12
    board[2][1] = "B"  # cell 11 (adjacent enemy)
    # Jump R over B (cell 11) landing on cell 10 (row2,col0).
    done, _ = env.step("12 10")
    assert done  # Black now has no pieces -> Red wins
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["score"] == [10, 0]


def test_disconnected_diagonal_is_rejected_atomically():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[4][1] = "R"  # b1 is not joined diagonally to a2.
    before = [row[:] for row in board]

    done, _ = env.step("b1 a2")

    assert not done
    assert board == before
    assert env.state.current_player_id == 0


def test_available_capture_is_mandatory():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"
    board[2][1] = "B"
    before = [row[:] for row in board]

    done, _ = env.step("c3 c4")

    assert not done
    assert board == before


def test_multi_capture_path_is_atomic_and_must_be_completed():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # c3
    board[2][1] = "B"  # b3
    board[3][1] = "B"  # b2
    before = [row[:] for row in board]

    done, _ = env.step("c3 a3")
    assert not done
    assert board == before

    done, _ = env.step("c3 -> a3 -> c1")
    assert done
    assert board[4][2] == "R"
    assert board[2][1] == board[3][1] == ""
    assert env.state.game_state["score"] == [20, 0]
    assert env.state.rewards == {0: 1, 1: -1}


def test_mover_becoming_blocked_does_not_end_opponents_turn():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[1][2] = "R"  # c4 can make one final forward move to c5.
    board[0][0] = "B"  # Black still has a legal move from a5.

    done, _ = env.step("c4 c5")

    assert not done
    assert env.state.current_player_id == 1
    assert board[0][2] == "R"


def test_turn_limit_uses_capture_score_then_draws_ties():
    env = _fresh()
    env.state.game_state["score"] = [20, 10]
    assert env.on_turn_limit().rewards == {0: 1, 1: -1}

    env.state.game_state["score"] = [20, 20]
    assert env.on_turn_limit().rewards == {0: 0, 1: 0}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("not a move at all")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # offender keeps the turn


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("not a move at all")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice

    red_example, black_example = re.search(
        r"for example '([^']+)' as Red or '([^']+)' as Black", env.action_format
    ).groups()
    # Black's example needs a Red opening that leaves c3 empty and offers no capture.
    for moves in ([red_example], ["b2 a3", black_example]):
        fresh = _fresh()
        for move in moves:
            fresh.step(move)
        assert fresh.state.turn == len(moves) and fresh.state.error_count == 0


def test_illegal_but_wellformatted_move_rejected():
    env = _fresh()
    # cell 20 = row4,col0 (R) jumping to cell 10 over own piece at row3,col0 -> illegal.
    done, _ = env.step("20 10")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_huge_numeric_coordinate_is_rejected_without_exception():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]

    done, _ = env.step(f"{'9' * 5000} 12")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["board"] == before


def test_non_ascii_digit_cell_ids_are_rejected():
    env = _fresh()
    before = [row[:] for row in env.state.game_state["board"]]
    done, _ = env.step("\u0661\u0667 \u0661\u0662")  # Arabic-Indic "17 12"
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["board"] == before


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage again")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_render_lists_legal_moves_and_scores():
    env = _fresh()
    board = env.render(0)
    assert "Score: Red (Player 0) 0, Black (Player 1) 0" in board
    listed = board.split("Legal moves: ")[1].strip().split(", ")
    assert sorted(listed) == sorted(env._legal_moves(0))
    assert "a2 a3" in listed and "b2 c3" in listed and "a2 b3" not in listed
    assert "'c4 c3'" in env.prompt(1)


def test_legal_moves_are_complete_capture_sequences_when_a_capture_exists():
    env = _fresh()
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # c3
    board[2][1] = "B"  # b3
    board[3][1] = "B"  # b2

    assert env._legal_moves(0) == ["c3 a3 c1", "c3 a1"]
    assert env.render(0).rstrip().endswith("Legal moves: c3 a3 c1, c3 a1")


def _assert_listed_moves_match_apply(env):
    pid = env.state.current_player_id
    listed = set(env._legal_moves(pid))
    squares = [f"{f}{r}" for f in "abcde" for r in "12345"]
    candidates = {f"{a} {b}" for a in squares for b in squares} | listed
    for move in candidates:
        clone = AlquerqueEnv()
        clone.restore(env.snapshot())
        clone.step(move)
        assert (clone.state.error_count == 0) == (move in listed), move


def test_every_listed_move_is_accepted_and_others_are_rejected():
    env = _fresh()
    for _ in range(5):
        _assert_listed_moves_match_apply(env)
        done, _ = env.step(env._legal_moves(env.state.current_player_id)[0])
        assert not done and env.state.error_count == 0

    staged = _fresh()
    board = staged.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"  # c3 can capture b3 then b2 (via a3), or b2 diagonally
    board[2][1] = board[3][1] = board[0][4] = "B"
    _assert_listed_moves_match_apply(staged)


def test_every_move_is_described_with_board_coordinates():
    env = _fresh()
    env.step("17 12")
    board = env.state.game_state["board"]
    _clear(board)
    board[2][2] = "R"
    board[1][1] = "B"  # b4 jumps c3 to land on d2
    board[0][0] = "B"
    env.step("b4 d2")

    descriptions = [m for _, m, t, _ in env.state.events if m.startswith("Player")]
    assert descriptions[0] == "Player 0 (R) moved c2 -> c3."
    assert descriptions[1] == "Player 1 (B) moved b4 -> d2, capturing 1 piece(s)! (+10)"
