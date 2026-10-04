"""Deterministic offline tests for Lines of Action.

Two-player game on an 8x8 board. Player 0 is 'O' (top/bottom rows), Player 1 is
'X' (left/right columns), P0 moves first. Move format ``<from><to>`` using
algebraic coords; a move travels exactly as many squares as there are pieces on
that line. A full win (all pieces 8-connected) is impractical to script, so we
verify legal-move mechanics, rotation, and invalid-move handling.
"""
import copy

from textarena.envs.LinesOfAction.env import LinesOfActionEnv


def _fresh():
    env = LinesOfActionEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_board():
    env = _fresh()
    assert env.state.current_player_id == 0
    board = env.state.game_state["board"]
    assert board[0][1] == "O" and board[0][6] == "O"
    assert board[1][0] == "X" and board[1][7] == "X"
    # corners empty
    assert board[0][0] == "" and board[7][7] == ""


def test_valid_move_and_rotation():
    env = _fresh()
    # Column b has 2 pieces (b8, b1) -> vertical move distance must be 2.
    done, _ = env.step("b8b6")
    assert done is False
    assert env.state.game_state["board"][0][1] == ""   # b8 vacated
    assert env.state.game_state["board"][2][1] == "O"  # b6 occupied
    assert env.state.current_player_id == 1            # rotated to P1
    assert env.state.game_state["valid_moves"] == env._legal_moves(1)


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("move b8 to b6")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("move b8 to b6")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice

    assert "for example 'b1b3', or 'pass'" in env.action_format
    fresh = _fresh()
    fresh.step("b1b3")
    blocked = _fresh()
    _stage_blocked_o(blocked)
    blocked.step("pass")
    for game in (fresh, blocked):
        assert game.state.turn == 1 and game.state.error_count == 0


def test_no_piece_at_source():
    env = _fresh()
    # a1 (bottom-left corner) is empty for O.
    done, _ = env.step("a1a3")
    assert done is False
    assert env.state.error_count == 1


def test_wrong_distance_rejected():
    env = _fresh()
    # Column b has 2 pieces so distance must be 2, not 3.
    done, _ = env.step("b8b5")
    assert done is False
    assert env.state.error_count == 1


def test_recover_after_invalid():
    env = _fresh()
    env.step("bad")                 # invalid #1
    assert env.state.error_count == 1
    done, _ = env.step("b8b6")     # valid resubmission
    assert done is False
    assert env.state.error_count == 0
    assert env.state.current_player_id == 1


def test_second_consecutive_invalid_loses():
    env = _fresh()
    env.step("b8b5")              # invalid #1 (wrong distance)
    done, _ = env.step("garbage")    # invalid #2 -> P0 forfeits
    assert done is True
    assert env.state.rewards == {0: -1, 1: 1}


def test_player1_can_move():
    env = _fresh()
    env.step("b8b6")             # P0 moves, now P1
    # Row 4 (rank 4/5 area): X on a5 and h5, row has 2 pieces -> horizontal dist 2.
    # Use column a: a2..a7 are X (6 pieces) -> vertical distance 6 from a7 to a1.
    done, _ = env.step("a7a1")
    assert done is False
    assert env.state.current_player_id == 0


def test_generated_moves_are_legal_and_include_known_opening():
    env = _fresh()
    moves = env._legal_moves(0)
    assert "b8b6" in moves
    assert moves == env.state.game_state["valid_moves"]
    for move in moves:
        clone = _fresh()
        done, _ = clone.step(move)
        assert clone.state.error_count == 0


def test_enemy_blocking_rejection_is_atomic():
    env = _fresh()
    board = env.state.game_state["board"]
    board[:] = [["" for _ in range(8)] for _ in range(8)]
    board[0][0] = "O"
    board[0][1] = "X"
    board[0][3] = "X"  # line count is three; b8 blocks a8 -> d8
    before = copy.deepcopy(board)
    done, _ = env.step("a8d8")
    assert not done
    assert board == before
    assert env.state.current_player_id == 0


def test_move_connecting_mover_wins_short_staged_game():
    env = _fresh()
    board = env.state.game_state["board"]
    board[:] = [["" for _ in range(8)] for _ in range(8)]
    board[0][0] = "O"  # a8
    board[0][2] = "O"  # c8
    board[6][7] = "X"
    board[4][7] = "X"
    done, _ = env.step("a8b7")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_capture_that_leaves_only_opponent_connected_awards_opponent():
    env = _fresh()
    board = env.state.game_state["board"]
    board[:] = [["" for _ in range(8)] for _ in range(8)]
    board[0][0] = "O"  # a8
    board[7][0] = "O"  # a1, remains disconnected from c8
    board[0][2] = "X"  # c8, captured
    board[7][7] = "X"  # h1, the sole remaining X
    done, _ = env.step("a8c8")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_simultaneous_connection_awards_moving_player():
    env = _fresh()
    board = env.state.game_state["board"]
    board[:] = [["" for _ in range(8)] for _ in range(8)]
    board[0][0] = "O"  # a8 moves to c8
    board[1][3] = "O"  # d7 becomes adjacent to c8
    board[0][2] = "X"  # captured, leaving one connected X piece
    board[7][7] = "X"

    done, _ = env.step("a8c8")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["valid_moves"] == []


def test_repetition_hash_records_next_side_to_move():
    env = _fresh()
    env.step("b8b6")
    expected = env._hash_position(env.state.game_state["board"], 1)
    wrong_side = env._hash_position(env.state.game_state["board"], 0)
    assert env.state.game_state["rep_counter"][expected] == 1
    assert env.state.game_state["rep_counter"][wrong_side] == 0


def test_pass_is_rejected_while_a_move_exists():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("pass")
    assert not done
    assert env.state.game_state == before
    assert env.state.current_player_id == 0


def _stage_blocked_o(env):
    """O (a8, h1) has no legal move: every line is blocked by X or leaves the board."""
    board = env.state.game_state["board"]
    board[:] = [["" for _ in range(8)] for _ in range(8)]
    board[0][0] = board[7][7] = "O"
    for r, c in [(0, 1), (1, 0), (1, 1), (7, 6), (6, 7), (6, 6)]:
        board[r][c] = "X"
    return board


def test_render_lists_legal_moves_for_the_acting_player():
    env = _fresh()
    board = env.render(0)
    assert "Legal moves:" in board
    listed = board.split("Legal moves:")[1].strip().split(", ")
    assert sorted(listed) == sorted(env._legal_moves(0))


def test_player_without_moves_is_told_to_pass_and_can_pass():
    env = _fresh()
    _stage_blocked_o(env)
    assert env._legal_moves(0) == []
    assert "pass" in env.prompt(0)

    assert env.render(0).rstrip().endswith("Legal moves: pass")
    done, _ = env.step("pass")

    assert not done
    assert env.state.error_count == 0
    assert env.state.current_player_id == 1


def test_separated_coordinates_are_accepted_and_echoed_in_lowercase():
    env = _fresh()
    done, _ = env.step("B8 b6")
    assert not done and env.state.error_count == 0
    done, _ = env.step("a7-a1")
    assert not done and env.state.error_count == 0
    descriptions = [m for f, m, t, _ in env.state.events if m.startswith("Player 0 moved")]
    assert descriptions == ["Player 0 moved b8 -> b6"]
