"""Deterministic game-logic tests for Chess-v0 (backed by python-chess)."""
import copy

import chess
import pytest

from textarena.envs.Chess.env import ChessEnv


def _fresh(max_turns=30):
    env = ChessEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_starting_position():
    env = _fresh()
    board = env.state.game_state["board"]
    assert board.fen().startswith("rnbqkbnr/pppppppp")
    assert env.state.current_player_id == 0


def test_legal_move_updates_board_and_rotates():
    env = _fresh()
    done, _ = env.step("e2e4")
    assert not done
    board = env.state.game_state["board"]
    assert board.piece_at(__import__("chess").E4) is not None
    assert env.state.current_player_id == 1
    assert env.state.game_state["valid_moves"] == ", ".join(move.uci() for move in board.legal_moves)


def test_fools_mate_black_wins():
    env = _fresh()
    # 1. f3 e5 2. g4 Qh4#  -> Black delivers checkmate.
    for move in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        done, _ = env.step(move)
    assert done
    assert env.state.rewards == {1: 1, 0: -1}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("I move my pawn")
    assert not done
    assert env.state.error_count == 1


def test_illegal_move_increments_error_count():
    env = _fresh()
    done, _ = env.step("e2e5")  # pawn cannot jump three squares
    assert not done
    assert env.state.error_count == 1


def test_shape_valid_but_invalid_uci_is_rejected_atomically():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("a1a1")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before
    assert env.state.current_player_id == 0


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("nope")
    done, _ = env.step("still nope")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_castling_moves_rook_and_king():
    env = _fresh()
    for move in ["e2e4", "e7e5", "g1f3", "b8c6", "f1e2", "g8f6", "e1g1"]:
        done, _ = env.step(move)
    assert not done
    board = env.state.game_state["board"]
    assert board.piece_at(chess.G1).piece_type == chess.KING
    assert board.piece_at(chess.F1).piece_type == chess.ROOK


def test_en_passant_capture():
    env = _fresh()
    for move in ["e2e4", "a7a6", "e4e5", "d7d5", "e5d6"]:
        done, _ = env.step(move)
    assert not done
    board = env.state.game_state["board"]
    assert board.piece_at(chess.D6).piece_type == chess.PAWN
    assert board.piece_at(chess.D5) is None


def test_promotion_requires_and_applies_piece_suffix():
    env = _fresh()
    board = env.state.game_state["board"]
    board.set_fen("7k/P7/8/8/8/8/8/7K w - - 0 1")
    before = board.fen()
    env.step("a7a8")  # no promotion suffix is illegal
    assert board.fen() == before
    done, _ = env.step("a7a8q")
    assert not done
    assert board.piece_at(chess.A8).piece_type == chess.QUEEN


def test_stalemate_is_draw():
    env = _fresh()
    board = env.state.game_state["board"]
    board.set_fen("7k/5K2/8/6Q1/8/8/8/8 w - - 0 1")
    done, _ = env.step("g5g6")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert "stalemate" in env.state.game_info[0]["reason"]


def test_threefold_repetition_is_claimed_as_draw():
    env = _fresh()
    done = False
    for move in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
        done, _ = env.step(move)
        if done:
            break
    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert "threefold repetition" in env.state.game_info[0]["reason"]


def test_potential_next_move_does_not_prematurely_claim_threefold():
    env = _fresh()
    for move in ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1"]:
        done, _ = env.step(move)
        assert not done

    board = env.state.game_state["board"]
    assert not board.is_repetition(3)
    assert board.can_claim_threefold_repetition()

    done, _ = env.step("f6g8")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_fifty_move_draw_waits_until_current_position_qualifies():
    env = _fresh()
    board = env.state.game_state["board"]
    board.set_fen("8/8/8/8/8/6k1/8/R6K w - - 98 1")

    done, _ = env.step("a1a2")
    assert not done
    assert board.halfmove_clock == 99
    assert board.can_claim_fifty_moves()
    assert not board.is_fifty_moves()

    done, _ = env.step("g3f3")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert "fifty-move rule" in env.state.game_info[0]["reason"]


def test_turn_limit_draw_and_blind_rendering():
    env = _fresh(max_turns=1)
    done, _ = env.step("e2e4")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}

    blind = ChessEnv(is_open=False, show_valid=False)
    blind.reset(num_players=2, seed=42)
    assert blind.render(0) is None


def test_snapshot_restore_recovers_python_chess_state():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("e2e4")
    env.restore(snapshot)
    assert env.state.game_state["board"].fen() == chess.Board().fen()
    assert env.state.current_player_id == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_turns": 0},
        {"max_turns": 1.5},
        {"is_open": 1},
        {"show_valid": "yes"},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        ChessEnv(**kwargs)
