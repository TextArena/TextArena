"""Rules tests for the built-in chess engine (``textarena.envs.Chess.board``)."""
import copy
import random

import pytest

from textarena.envs.Chess.board import (
    B8, BISHOP, BLACK, D5, D6, E1, E2, E3, E4, E7, E8, F3, G1, KING, KNIGHT, PAWN, QUEEN, ROOK, STARTING_BOARD_FEN,
    STARTING_FEN, WHITE, Board, IllegalMoveError, InvalidMoveError, Move, Outcome, Piece, Termination,
)


def legal(board):
    return [move.uci() for move in board.legal_moves]


def play(board, *ucis):
    for uci in ucis:
        board.push_uci(uci)
    return board


def perft(board, depth):
    if depth == 1:
        return board.legal_moves.count()
    total = 0
    for move in list(board.legal_moves):
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total


# Node counts from https://www.chessprogramming.org/Perft_Results
@pytest.mark.parametrize("fen, counts", [
    pytest.param(STARTING_FEN, [20, 400, 8902, 197281], id="start"),
    pytest.param("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1", [48, 2039, 97862], id="kiwipete"),
    pytest.param("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [14, 191, 2812, 43238], id="position3"),
    pytest.param("r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1", [6, 264, 9467], id="position4"),
    pytest.param("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [44, 1486, 62379], id="position5"),
    pytest.param("r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10", [46, 2079, 89890],
                 id="position6"),
])
def test_perft_matches_published_node_counts(fen, counts):
    board = Board(fen)
    assert [perft(board, depth) for depth in range(1, len(counts) + 1)] == counts
    assert board.fen() == fen


# Widely used perft edge-case positions, at their published depths.
@pytest.mark.parametrize("fen, depth, expected", [
    pytest.param("r3k2r/1b4bq/8/8/8/8/7B/R3K2R w KQkq - 0 1", 4, 1274206, id="castle-rights"),
    pytest.param("8/8/1P2K3/8/2n5/1q6/8/5k2 b - - 0 1", 5, 1004658, id="discovered-check"),
    pytest.param("4k3/1P6/8/8/8/8/K7/8 w - - 0 1", 6, 217342, id="promote-to-give-check"),
    pytest.param("8/P1k5/K7/8/8/8/8/8 w - - 0 1", 6, 92683, id="underpromote-to-give-check"),
    pytest.param("K1k5/8/P7/8/8/8/8/8 w - - 0 1", 6, 2217, id="self-stalemate"),
    pytest.param("8/8/2k5/5q2/5n2/8/5K2/8 b - - 0 1", 4, 23527, id="stalemate-and-checkmate"),
])
def test_perft_edge_cases(fen, depth, expected):
    assert perft(Board(fen), depth) == expected


# ------------------------------------------------------------------------- FEN
def test_fen_round_trip_and_defaults():
    assert Board().fen() == STARTING_FEN
    assert Board(STARTING_BOARD_FEN).fen() == f"{STARTING_BOARD_FEN} w - - 0 1"
    assert Board("8/8/8/8/8/8/8/K6k w - - 5 0").fen() == "8/8/8/8/8/8/8/K6k w - - 5 1"
    assert Board(None).fen() == "8/8/8/8/8/8/8/8 w - - 0 1"


def test_en_passant_square_is_only_written_when_a_capture_is_legal():
    board = play(Board(), "e2e4")
    assert board.ep_square == E3
    assert board.fen() == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    play(board, "d7d5", "e4e5", "f7f5")
    assert board.fen() == "rnbqkbnr/ppp1p1pp/8/3pPp2/8/8/PPPP1PPP/RNBQKBNR w KQkq f6 0 3"
    assert Board("8/8/8/K2pP2r/8/8/8/7k w - d6 0 1").fen() == "8/8/8/K2pP2r/8/8/8/7k w - - 0 1"


def test_castling_rights_from_fen_need_king_and_rook_at_home():
    assert Board("r3k3/8/8/8/8/8/8/4K2R w KQkq - 0 1").castling_xfen() == "Kq"
    assert Board("r3k2r/8/8/8/8/8/8/R3K2R w HAha - 0 1").fen() == "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"


@pytest.mark.parametrize("fen", [
    "",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP w KQkq - 0 1",
    "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppp/44/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/ppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/ppppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppx/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQxq - 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq e9 0 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - -1 1",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 x",
    "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 extra",
])
def test_malformed_fen_is_rejected(fen):
    with pytest.raises(ValueError):
        Board(fen)


def test_ascii_board_layout():
    empty_row = ". . . . . . . .\n"
    assert str(Board()) == f"r n b q k b n r\np p p p p p p p\n{empty_row * 4}P P P P P P P P\nR N B Q K B N R"


# ------------------------------------------------------------------------- UCI
def test_uci_parsing():
    assert Move.from_uci("e2e4") == Move(E2, E4)
    assert Move.from_uci("e7e8q") == Move(E7, E8, QUEEN) and Move(E7, E8, QUEEN).uci() == "e7e8q"
    assert not Move.from_uci("0000") and Move.null().uci() == "0000"
    assert Move.from_uci("e7e8k").promotion == KING
    for text in ["a1a1", "a1a1q", "E2E4", "e2e4Q", "e2e9", "e2", "e2e4qq", "Q@e4", ""]:
        with pytest.raises(InvalidMoveError):
            Move.from_uci(text)


def test_parse_and_push_uci_validate_legality():
    board = Board()
    assert board.push_uci("g1f3") == Move(G1, F3)
    with pytest.raises(IllegalMoveError):
        board.parse_uci("e2e4")
    with pytest.raises(InvalidMoveError):
        board.parse_uci("e7e7")


# ----------------------------------------------------------------- move rules
def test_legal_moves_are_listed_in_python_chess_order():
    assert ", ".join(legal(Board())) == (
        "g1h3, g1f3, b1c3, b1a3, h2h3, g2g3, f2f3, e2e3, d2d3, c2c3, b2b3, a2a3, "
        "h2h4, g2g4, f2f4, e2e4, d2d4, c2c4, b2b4, a2a4"
    )
    kiwipete = Board("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1")
    assert ", ".join(legal(kiwipete)) == (
        "e5f7, e5d7, e5g6, e5c6, e5g4, e5c4, e5d3, f3f6, f3h5, f3f5, f3g4, f3f4, f3h3, f3g3, f3e3, f3d3, "
        "c3b5, c3a4, c3d1, c3b1, e2a6, e2b5, e2c4, e2d3, e2f1, e2d1, d2h6, d2g5, d2f4, d2e3, d2c1, h1g1, "
        "h1f1, e1f1, e1d1, a1d1, a1c1, a1b1, e1g1, e1c1, d5e6, g2h3, d5d6, g2g3, b2b3, a2a3, g2g4, a2a4"
    )
    in_check = play(Board(), "e2e4", "d7d5", "f1b5")
    assert legal(in_check) == ["d8d7", "c8d7", "b8d7", "b8c6", "c7c6"]


@pytest.mark.parametrize("fen, castles", [
    ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", ["e1g1", "e1c1"]),
    ("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1", ["e8g8", "e8c8"]),
    ("r3k2r/8/8/8/8/8/5r2/R3K2R w KQkq - 0 1", ["e1c1"]),  # through check
    ("r3k2r/8/8/8/8/8/6r1/R3K2R w KQkq - 0 1", ["e1c1"]),  # into check
    ("r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1", []),  # out of check
    ("r3k2r/8/8/8/8/8/1r6/R3K2R w KQkq - 0 1", ["e1g1", "e1c1"]),  # the rook may cross an attacked b1
    ("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1", ["e1g1"]),
    ("r3k2r/8/8/8/8/8/8/R3K1NR w KQkq - 0 1", ["e1c1"]),
    ("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1", []),
])
def test_castling_needs_rights_and_an_empty_safe_path(fen, castles):
    board = Board(fen)
    king_squares = ("e1", "e8")
    assert [uci for uci in legal(board) if uci[:2] in king_squares and uci[2] in "cg"] == castles


def test_castling_rights_are_lost_when_king_or_rook_moves_or_the_rook_is_captured():
    board = Board("r3k2r/8/8/8/8/8/6b1/R3K2R b KQkq - 0 1")
    assert play(board, "g2h1").castling_xfen() == "Qkq"
    assert play(board, "a1a2").castling_xfen() == "kq"
    assert play(board, "e8d8").castling_xfen() == "-"
    assert not board.has_castling_rights(WHITE) and not board.has_castling_rights(BLACK)


def test_castling_moves_the_rook_and_accepts_king_takes_rook_notation():
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert Move.from_uci("e1h1") in board.legal_moves and Move.from_uci("e1a1") in board.legal_moves
    board.push(Move.from_uci("e1h1"))
    assert board.fen() == "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1"
    assert board.peek() == Move.from_uci("e1g1")
    play(board, "e8c8")
    assert board.fen() == "2kr3r/8/8/8/8/8/8/R4RK1 w - - 2 2"
    assert Move.from_uci("e1h1") not in Board("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1").legal_moves


def test_en_passant_is_only_possible_right_after_the_double_step():
    board = play(Board(), "e2e4", "a7a6", "e4e5", "d7d5")
    assert "e5d6" in legal(board)
    play(board, "e5d6")
    assert board.piece_at(D6) == Piece(PAWN, WHITE) and board.piece_at(D5) is None
    board = play(Board(), "e2e4", "a7a6", "e4e5", "d7d5", "b1c3", "a6a5")
    assert "e5d6" not in legal(board)


def test_en_passant_exposing_the_king_along_the_rank_is_illegal():
    board = Board("8/8/8/K2pP2r/8/8/8/7k w - d6 0 1")
    assert legal(board) == ["a5b6", "a5a6", "a5b5", "a5b4", "a5a4", "e5e6"]
    assert not board.has_legal_en_passant()


def test_en_passant_can_capture_a_checking_pawn_or_block_a_check():
    assert legal(Board("8/8/8/2Pp4/4K3/8/8/7k w - d6 0 1"))[-1] == "c5d6"
    assert legal(Board("5b2/8/8/3pP3/8/K7/8/7k w - d6 0 1")) == ["a3a4", "a3b3", "a3b2", "a3a2", "e5d6"]


def test_promotion_requires_a_piece_and_offers_all_four():
    board = Board("1n5k/P7/8/8/8/8/8/7K w - - 0 1")
    assert legal(board) == [
        "h1h2", "h1g2", "h1g1", "a7b8q", "a7b8r", "a7b8b", "a7b8n", "a7a8q", "a7a8r", "a7a8b", "a7a8n",
    ]
    assert not board.is_legal(Move.from_uci("a7a8")) and not board.is_legal(Move.from_uci("a7a8k"))
    play(board, "a7b8n")
    assert board.piece_at(B8) == Piece(KNIGHT, WHITE)


def test_pinned_pieces_stay_on_the_pin_and_double_check_needs_a_king_move():
    pinned = Board("4r1k1/8/8/8/8/8/4R3/4K3 w - - 0 1")
    assert [uci for uci in legal(pinned) if uci.startswith("e2")] == ["e2e8", "e2e7", "e2e6", "e2e5", "e2e4", "e2e3"]
    double_check = Board("4r1k1/8/8/8/R7/3n4/8/4K3 w - - 0 1")
    assert legal(double_check) == ["e1d2", "e1f1", "e1d1"]


def test_halfmove_clock_resets_on_pawn_moves_and_captures():
    board = play(Board(), "g1f3", "g8f6")
    assert board.halfmove_clock == 2 and board.fullmove_number == 2
    assert play(board, "e2e4").halfmove_clock == 0
    assert play(board, "f6e4").halfmove_clock == 0
    assert play(board, "f3g1").halfmove_clock == 1


# ------------------------------------------------------------------- game end
def test_checkmate_stalemate_and_outcome_order():
    fools_mate = Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert fools_mate.is_checkmate() and fools_mate.outcome() == Outcome(Termination.CHECKMATE, BLACK)
    assert fools_mate.result() == "0-1"
    stalemate = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert stalemate.is_stalemate() and stalemate.outcome() == Outcome(Termination.STALEMATE, None)
    # Insufficient material is reported before stalemate.
    assert Board("7k/5K2/6B1/8/8/8/8/8 b - - 0 1").outcome().termination == Termination.INSUFFICIENT_MATERIAL
    # Checkmate and stalemate take precedence over the move-count rules.
    late_mate = Board("R5k1/5ppp/8/8/8/8/8/6K1 b - - 150 100")
    assert late_mate.outcome() == Outcome(Termination.CHECKMATE, WHITE) and not late_mate.is_fifty_moves()
    assert Board("7k/5Q2/6K1/8/8/8/8/8 b - - 150 100").outcome().termination == Termination.STALEMATE


@pytest.mark.parametrize("fen, white, black", [
    ("8/8/4k3/8/8/4K3/8/8 w - - 0 1", True, True),
    ("8/8/4k3/8/8/4KN2/8/8 w - - 0 1", True, True),
    ("8/8/4k3/8/8/4KB2/8/8 w - - 0 1", True, True),
    ("8/8/4k1b1/8/8/4KB2/8/8 w - - 0 1", True, True),  # bishops on the same color
    ("8/8/4kb2/8/8/4KB2/8/8 w - - 0 1", False, False),  # opposite-colored bishops
    ("8/8/4k3/8/8/4KNN1/8/8 w - - 0 1", False, True),
    ("8/8/4kq2/8/8/4KN2/8/8 w - - 0 1", True, False),
    ("8/8/4kr2/8/8/4KN2/8/8 w - - 0 1", False, False),  # the rook could block its own king in
    ("8/8/4kn2/8/8/4KN2/8/8 w - - 0 1", False, False),
    ("8/8/4kn2/8/8/4KB2/8/8 w - - 0 1", False, False),
    ("8/8/4kq2/8/8/4KB2/8/8 w - - 0 1", True, False),
    ("8/8/4k3/8/8/4KB1B/8/8 w - - 0 1", True, True),
    ("8/8/4k3/8/8/4KBB1/8/8 w - - 0 1", False, True),
    ("8/p7/4k3/8/8/4KB2/8/8 w - - 0 1", False, False),
])
def test_insufficient_material(fen, white, black):
    board = Board(fen)
    assert (board.has_insufficient_material(WHITE), board.has_insufficient_material(BLACK)) == (white, black)
    assert board.is_insufficient_material() == (white and black)


def test_threefold_and_fivefold_repetition():
    board = Board()
    shuffle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    play(board, *shuffle, *shuffle[:3])
    assert not board.is_repetition(3) and board.can_claim_threefold_repetition()
    play(board, shuffle[3])
    assert board.is_repetition(3) and not board.is_fivefold_repetition() and board.outcome() is None
    play(board, *shuffle * 2)
    assert board.is_fivefold_repetition()
    assert board.outcome() == Outcome(Termination.FIVEFOLD_REPETITION, None)
    board.pop()
    assert not board.is_repetition(5) and board.is_repetition(4)


def test_repetition_compares_castling_rights_and_legal_en_passant():
    board = play(Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"), "e1d1", "e8d8", "d1e1", "d8e8")
    assert not board.is_repetition(2)
    assert play(board, "e1d1", "e8d8", "d1e1", "d8e8").is_repetition(2) and not board.is_repetition(3)

    # After 1. e4 no en passant capture is possible, so the en passant square does not count...
    board = play(Board(), "e2e4", *["g8f6", "g1f3", "f6g8", "f3g1"] * 2)
    assert board.is_repetition(3)
    # ...but here exd6 was possible right after ...d5, so that position never recurs.
    board = play(Board(), "e2e4", "g8f6", "e4e5", "d7d5", *["g1f3", "f6g8", "f3g1", "g8f6"] * 2)
    assert board.is_repetition(2) and not board.is_repetition(3)


def test_set_fen_forgets_the_history():
    board = play(Board(), *["g1f3", "g8f6", "f3g1", "f6g8"] * 2)
    assert board.is_repetition(3)
    board.set_fen(board.fen())
    assert not board.is_repetition(2) and board.move_stack == []


def test_fifty_and_seventyfive_move_rules():
    board = play(Board("8/8/8/8/8/6k1/8/R6K w - - 98 1"), "a1a2")
    assert board.halfmove_clock == 99 and not board.is_fifty_moves() and board.can_claim_fifty_moves()
    assert play(board, "g3f3").is_fifty_moves() and board.outcome() is None
    assert board.outcome(claim_draw=True) == Outcome(Termination.FIFTY_MOVES, None)

    board = play(Board("4k2r/8/8/8/8/8/8/R3K3 w - - 134 1"), *["e1d1", "e8d8", "d1e1", "d8e8"] * 4)
    assert board.halfmove_clock == 150 and board.is_fivefold_repetition() and board.is_seventyfive_moves()
    assert board.outcome() == Outcome(Termination.SEVENTYFIVE_MOVES, None)


# ------------------------------------------------------------ board mechanics
def test_push_pop_round_trip_restores_every_position():
    board = Board()
    rng = random.Random(7)
    fens = [board.fen()]
    for _ in range(200):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
        fens.append(board.fen())
    while board.move_stack:
        board.pop()
        fens.pop()
        assert board.fen() == fens[-1]
    assert board == Board()


def test_copies_are_equal_and_independent():
    board = play(Board(), "g1f3", "g8f6")
    clone = copy.deepcopy(board)
    assert clone == board and clone is not board and clone.move_stack == board.move_stack
    play(clone, "f3g1", "f6g8", "g1f3", "g8f6")
    assert clone.is_repetition(2) and not board.is_repetition(2)
    assert Board("rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 2 2") == board
    assert Board("rnbqkb1r/pppppppp/5n2/8/8/5N2/PPPPPPPP/RNBQKB1R w KQkq - 0 2") != board


def test_piece_queries():
    board = Board()
    assert board.piece_at(E2) == Piece(PAWN, WHITE) and board.piece_at(E2).symbol() == "P"
    assert board.piece_at(E8).symbol() == "k" and board.piece_type_at(E4) is None
    assert board.king(WHITE) == E1 and board.king(BLACK) == E8
    assert Piece.from_symbol("b") == Piece(BISHOP, BLACK) and Piece(ROOK, WHITE).symbol() == "R"
