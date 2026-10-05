"""Differential tests: the built-in engine must agree with python-chess.

python-chess is not a dependency; these tests are skipped when it is not installed.
"""
import random

import pytest

from textarena.envs.Chess import board as engine

chess = pytest.importorskip("chess")

START_FENS = [
    chess.STARTING_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
    "4k3/pppppppp/8/8/8/8/PPPPPPPP/4K3 w - - 0 1",
    "n1n1k3/PPP5/8/8/8/8/5ppp/4K1N1 w - - 0 1",
    "8/8/3k4/8/8/4K3/2R5/8 w - - 140 90",
    "8/8/3k4/8/3n4/4KB2/8/8 w - - 0 1",
]


def assert_same(mine, ref, claims=False):
    assert [move.uci() for move in mine.legal_moves] == [move.uci() for move in ref.legal_moves]
    assert mine.fen() == ref.fen()
    assert str(mine) == str(ref)
    assert (mine.is_check(), mine.is_checkmate(), mine.is_stalemate()) == (
        ref.is_check(), ref.is_checkmate(), ref.is_stalemate())
    assert [mine.has_insufficient_material(color) for color in (True, False)] == [
        ref.has_insufficient_material(color) for color in (True, False)]
    assert mine.has_legal_en_passant() == ref.has_legal_en_passant()
    assert _outcome(mine.outcome()) == _outcome(ref.outcome())
    assert [mine.is_repetition(count) for count in (2, 3, 4, 5)] == [ref.is_repetition(count) for count in (2, 3, 4, 5)]
    assert (mine.is_fifty_moves(), mine.is_seventyfive_moves()) == (ref.is_fifty_moves(), ref.is_seventyfive_moves())
    if claims:
        assert mine.can_claim_threefold_repetition() == ref.can_claim_threefold_repetition()
        assert mine.can_claim_fifty_moves() == ref.can_claim_fifty_moves()
        assert _outcome(mine.outcome(claim_draw=True)) == _outcome(ref.outcome(claim_draw=True))


def _outcome(outcome):
    return None if outcome is None else (outcome.termination.name, outcome.winner)


def _choose(ref, moves, rng):
    special = [move for move in moves if ref.is_castling(move) or ref.is_en_passant(move) or move.promotion]
    if special and rng.random() < 0.5:
        return rng.choice(special)
    if len(ref.move_stack) >= 2 and rng.random() < 0.3:
        last = ref.move_stack[-2]
        back = chess.Move(last.to_square, last.from_square)
        if back in moves:
            return back
    return rng.choice(moves)


@pytest.mark.parametrize("seed", range(12))
def test_random_playouts_match_python_chess(seed):
    rng = random.Random(seed)
    for _ in range(4):
        fen = rng.choice(START_FENS)
        mine, ref = engine.Board(fen), chess.Board(fen)
        assert_same(mine, ref)
        for ply in range(rng.choice([40, 120])):
            moves = list(ref.legal_moves)
            if not moves:
                break
            move = _choose(ref, moves, rng)
            uci = move.uci()
            if ref.is_castling(move) and rng.random() < 0.5:
                uci = uci[:2] + {"g": "h", "c": "a"}[uci[2]] + uci[3]
            ref.push_uci(uci)
            mine.push_uci(uci)
            assert_same(mine, ref, claims=ply % 10 == 0)
        while ref.move_stack:
            assert mine.pop() == engine.Move.from_uci(ref.pop().uci())
        assert_same(mine, ref)


SHUFFLE = ["g1f3", "g8f6", "f3g1", "f6g8"]


@pytest.mark.parametrize("fen, ucis", [
    pytest.param(chess.STARTING_FEN, SHUFFLE * 5, id="threefold-and-fivefold"),
    pytest.param(chess.STARTING_FEN, ["e2e4"] + ["g8f6", "g1f3", "f6g8", "f3g1"] * 3, id="ep-square-without-capture"),
    pytest.param(chess.STARTING_FEN, ["e2e4", "g8f6", "e4e5", "d7d5"] + ["g1f3", "f6g8", "f3g1", "g8f6"] * 3,
                 id="ep-square-with-capture"),
    pytest.param("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", ["e1d1", "e8d8", "d1e1", "d8e8"] * 5,
                 id="repetition-after-losing-castling-rights"),
    pytest.param("8/8/8/8/8/6k1/8/R6K w - - 96 1", ["a1a2", "g3f3", "a2a1", "f3g3", "a1a2", "g3f3"], id="fifty-moves"),
    pytest.param("4k2r/8/8/8/8/8/8/R3K3 w - - 140 1", ["e1d1", "e8d8", "d1e1", "d8e8"] * 4, id="seventyfive-moves"),
    pytest.param("r3k2r/8/8/8/8/8/6b1/R3K2R b KQkq - 0 1", ["g2h1", "e1c1", "e8g8"], id="rook-captured-at-home"),
    pytest.param("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", ["e1h1", "e8a8"], id="king-takes-rook-castling"),
    pytest.param("rnbqkbnr/ppp1pppp/8/8/3p4/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", ["e2e4", "d4e3", "d2e3"],
                 id="en-passant"),
    pytest.param("8/8/8/K2pP2r/8/8/8/7k w - d6 0 1", ["a5b4"], id="en-passant-pinned-on-rank"),
    pytest.param("8/8/8/2Pp4/4K3/8/8/7k w - d6 0 1", ["c5d6"], id="en-passant-out-of-check"),
    pytest.param("1n2k3/P7/8/8/8/8/7p/4K1N1 w - - 0 1", ["a7b8q", "e8e7", "e1d2", "h2g1n", "b8b4"],
                 id="promotions"),
])
def test_scripted_sequences_match_python_chess(fen, ucis):
    mine, ref = engine.Board(fen), chess.Board(fen)
    assert_same(mine, ref, claims=True)
    for uci in ucis:
        ref.push_uci(uci)
        mine.push_uci(uci)
        assert_same(mine, ref, claims=True)


@pytest.mark.parametrize("fen", [
    chess.STARTING_FEN,
    "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1",
    "r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1",
    "8/8/8/K2pP2r/8/8/8/7k w - d6 0 1",
    "1n5k/P7/8/8/8/8/8/7K w - - 0 1",
    "4r1k1/8/8/8/R7/3n4/8/4K3 w - - 0 1",
])
def test_is_legal_matches_python_chess_for_every_candidate_move(fen):
    mine, ref = engine.Board(fen), chess.Board(fen)
    for from_square in range(64):
        if ref.color_at(from_square) != ref.turn:
            continue
        for to_square in range(64):
            for promotion in (None, 1, 2, 3, 4, 5, 6):
                expected = ref.is_legal(chess.Move(from_square, to_square, promotion))
                assert mine.is_legal(engine.Move(from_square, to_square, promotion)) == expected


@pytest.mark.parametrize("fen", [
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR",
    "8/8/8/8/8/8/8/K6k w - - 5 0",
    "r3k3/8/8/8/8/8/8/4K2R w KQkq - 0 1",
    "r3k2r/8/8/8/8/8/8/R3K2R w HAha - 0 1",
    "r3k2r/8/8/8/8/8/8/R3K2R w BGbg - 0 1",
    "4k3/8/8/3P4/8/8/8/4K3 w - e6 0 1",
    "4k3/8/8/8/8/8/8/4K3 w - e3 0 1",
    "4K3/8/8/8/8/8/8/4k3 b KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQ~KBNR w KQkq - 0 1",
    "",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",
    "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppp/44/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/ppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQxq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w kqKQ - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq e9 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - -1 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 x",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/~RNBQKBNR w KQkq - 0 1",
])
def test_fen_parsing_matches_python_chess(fen):
    try:
        ref = chess.Board(fen)
    except ValueError:
        with pytest.raises(ValueError):
            engine.Board(fen)
        return
    assert_same(engine.Board(fen), ref)


def test_uci_parsing_matches_python_chess():
    names = [file + rank for file in "abhz" for rank in "1289"]
    texts = ["0000", "", "e2", "e2e4 ", "E2E4", "e2e4qq", "e7e8k", "e7e8p", "e7e8Q"]
    texts += [a + b + promotion for a in names for b in names for promotion in ("", "q", "n", "k", "p", "x")]
    for text in texts:
        try:
            expected = chess.Move.from_uci(text).uci()
        except ValueError:
            expected = None
        try:
            parsed = engine.Move.from_uci(text).uci()
        except engine.InvalidMoveError:
            parsed = None
        assert parsed == expected, text
