"""Deterministic game-logic tests for Crusade (2 players, knight moves)."""
import copy

import pytest

import textarena as ta
from textarena.envs.Crusade.env import CrusadeEnv


def _fresh():
    env = CrusadeEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_capturing_last_enemy_piece_wins():
    env = _fresh()
    gs = env.state.game_state
    # Clear the board and stage a single winning capture for player 0 (White).
    gs["board"] = [["" for _ in range(8)] for _ in range(8)]
    gs["board"][0][0] = "W"   # a8
    gs["board"][2][1] = "B"   # b6 (a knight hop away)
    done, _ = env.step("a8 b6")
    assert done and env.state.rewards == {0: 1, 1: -1}
    assert gs["score"][0] == 1


def test_turn_rotation_after_valid_move():
    env = _fresh()
    assert env.state.current_player_id == 0
    # b2 -> c4 is a legal knight move on the default starting board.
    done, _ = env.step("b2 c4")
    assert not done and env.state.current_player_id == 1


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no move here")
    assert not done and env.state.error_count == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("no move here")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]

    assert "for example 'b1 c3' as White or 'b8 c6' as Black" in env.action_format
    fresh = _fresh()
    fresh.step("b1 c3")
    fresh.step("b8 c6")
    assert fresh.state.turn == 2 and fresh.state.error_count == 0


def test_moving_opponent_piece_rejected():
    env = _fresh()
    # a8/b6 are Black pieces on the default board; player 0 controls White.
    done, _ = env.step("a8 b6")
    assert not done and env.state.error_count == 1


def test_non_knight_move_rejected():
    env = _fresh()
    # a2 -> a3 is a single step forward, not a knight move.
    done, _ = env.step("a2 a3")
    assert not done and env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("a2 a3")  # illegal, second consecutive strike
    assert done and env.state.rewards == {0: -1, 1: 1}


@pytest.mark.parametrize("action", ("[b2 c4", "b2 c4]"))
def test_unbalanced_brackets_are_atomic_invalid_moves(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


def test_huge_numeric_square_is_rejected_without_integer_conversion(monkeypatch):
    import textarena.envs.Crusade.env as crusade_module

    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    real_int = int

    def guarded_int(text):
        if isinstance(text, str) and len(text) > 2:
            pytest.fail("attempted to convert an unbounded cell ID")
        return real_int(text)

    monkeypatch.setattr(crusade_module, "int", guarded_int, raising=False)

    done, _ = env.step(f"{'9' * 100_000} 0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_numeric_cells_are_accepted():
    env = _fresh()

    done, _ = env.step("00048 00042")  # a2 -> c3

    assert not done
    assert env.state.game_state["board"][6][0] == ""
    assert env.state.game_state["board"][5][2] == "W"
    assert env.state.current_player_id == 1


def test_landing_on_own_piece_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step("a2 c1")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_capture_score_decides_exact_move_limit_and_renders_final_board():
    class OneMoveCrusade(CrusadeEnv):
        MAX_MOVES = 1

    env = OneMoveCrusade()
    env.reset(num_players=2, seed=42)
    gs = env.state.game_state
    gs["board"] = [["" for _ in range(8)] for _ in range(8)]
    gs["board"][0][0] = "W"  # a8
    gs["board"][2][1] = "B"  # b6
    gs["board"][0][7] = "B"  # h8 keeps Black alive and mobile

    done, _ = env.step("a8 b6")

    assert done
    assert env.state.turn == 1
    assert gs["move_count"] == 1
    assert gs["score"] == [1, 0]
    assert env.state.rewards == {0: 1, 1: -1}
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert "6 | . W" in final_board


def test_tied_score_draws_at_exact_move_limit():
    class OneMoveCrusade(CrusadeEnv):
        MAX_MOVES = 1

    env = OneMoveCrusade()
    env.reset(num_players=2, seed=42)

    done, _ = env.step("b2 c4")

    assert done
    assert env.state.turn == 1
    assert env.state.game_state["move_count"] == 1
    assert env.state.rewards == {0: 0, 1: 0}


def test_moves_are_described_in_algebraic_coordinates_whatever_the_input_form():
    env = _fresh()
    env.step("00048 00042")  # a2 -> c3
    env.step("B7 C5")

    descriptions = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ACTION_DESCRIPTION]
    assert descriptions == [
        "Player 0 moved their piece from a2 to c3.",
        "Player 1 moved their piece from b7 to c5.",
    ]


def test_render_shows_capture_score_and_remaining_moves():
    env = _fresh()
    gs = env.state.game_state
    gs["board"] = [["" for _ in range(8)] for _ in range(8)]
    gs["board"][0][0] = "W"  # a8
    gs["board"][2][1] = "B"  # b6
    gs["board"][7][7] = "B"  # h1
    env.step("a8 b6")

    board = env.render(1)

    assert "Score: White (Player 0) 1, Black (Player 1) 0 | Moves left: 39" in board


def test_snapshot_restores_board_score_and_actor():
    env = _fresh()
    snapshot = env.snapshot()

    env.step("b2 c4")
    env.restore(snapshot)

    assert env.state.current_player_id == 0
    assert env.state.turn == 0
    assert env.state.game_state["move_count"] == 0
    assert env.state.game_state["score"] == [0, 0]
    assert env.state.game_state["board"][6][1] == "W"
