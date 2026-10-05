"""Standard chess rules: board state, FEN, legal moves and game-end detection.

A dependency-free replacement for the parts of python-chess that the Chess
environment uses. ``Board``, ``Move``, ``Piece`` and ``Outcome`` follow the
python-chess API and semantics: UCI parsing, FEN output (the en passant square
is only written when an en passant capture is legal), the order in which legal
moves are listed, and the automatic and claimable draw rules all match.

Squares are numbered from 0 (a1) to 63 (h8). The board is a 64-entry list that
holds 0 for an empty square and +piece_type / -piece_type for a white / black
piece.
"""
import dataclasses
import enum
import re
from typing import Dict, Iterator, List, NamedTuple, Optional, Sequence, Tuple

Color = bool
WHITE: Color = True
BLACK: Color = False
COLORS = [WHITE, BLACK]

PieceType = int
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6
PIECE_TYPES = [PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING]
PIECE_SYMBOLS = [None, "p", "n", "b", "r", "q", "k"]

Square = int
FILE_NAMES = ["a", "b", "c", "d", "e", "f", "g", "h"]
RANK_NAMES = ["1", "2", "3", "4", "5", "6", "7", "8"]
SQUARE_NAMES = [file + rank for rank in RANK_NAMES for file in FILE_NAMES]
SQUARES = list(range(64))
(
    A1, B1, C1, D1, E1, F1, G1, H1,
    A2, B2, C2, D2, E2, F2, G2, H2,
    A3, B3, C3, D3, E3, F3, G3, H3,
    A4, B4, C4, D4, E4, F4, G4, H4,
    A5, B5, C5, D5, E5, F5, G5, H5,
    A6, B6, C6, D6, E6, F6, G6, H6,
    A7, B7, C7, D7, E7, F7, G7, H7,
    A8, B8, C8, D8, E8, F8, G8, H8,
) = SQUARES

STARTING_BOARD_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"
STARTING_FEN = f"{STARTING_BOARD_FEN} w KQkq - 0 1"
_EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1"


def parse_square(name: str) -> Square:
    """The square called ``name`` (e.g. ``"e4"``); raises ``ValueError`` for anything else."""
    return SQUARE_NAMES.index(name)


def square_name(square: Square) -> str:
    return SQUARE_NAMES[square]


def square_file(square: Square) -> int:
    return square & 7


def square_rank(square: Square) -> int:
    return square >> 3


# --------------------------------------------------------------------------- tables
def _walk(square: Square, file_step: int, rank_step: int, limit: int = 7) -> Tuple[Square, ...]:
    """Squares reached by repeating one step from ``square``, nearest first."""
    file, rank = square_file(square), square_rank(square)
    path: List[Square] = []
    while len(path) < limit:
        file, rank = file + file_step, rank + rank_step
        if not (0 <= file < 8 and 0 <= rank < 8):
            break
        path.append(rank * 8 + file)
    return tuple(path)


def _leaps(steps: Sequence[Tuple[int, int]]) -> List[Tuple[Square, ...]]:
    """For every square, the squares a single step away, listed from h8 down to a1."""
    return [
        tuple(sorted((to for step in steps for to in _walk(square, *step, limit=1)), reverse=True))
        for square in SQUARES
    ]


def _rays(directions: Sequence[Tuple[int, int]]) -> List[Tuple[Tuple[Square, ...], ...]]:
    return [tuple(ray for ray in (_walk(square, *step) for step in directions) if ray) for square in SQUARES]


_KNIGHT_TARGETS = _leaps([(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)])
_KING_TARGETS = _leaps([(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)])
# Squares attacked by a pawn of the given color standing on each square.
_PAWN_ATTACKS = {WHITE: _leaps([(-1, 1), (1, 1)]), BLACK: _leaps([(-1, -1), (1, -1)])}
_ROOK_RAYS = _rays([(0, 1), (1, 0), (0, -1), (-1, 0)])
_BISHOP_RAYS = _rays([(1, 1), (-1, 1), (1, -1), (-1, -1)])
_SLIDER_RAYS = {
    BISHOP: _BISHOP_RAYS,
    ROOK: _ROOK_RAYS,
    QUEEN: [rook + bishop for rook, bishop in zip(_ROOK_RAYS, _BISHOP_RAYS)],
}
_PROMOTIONS = (QUEEN, ROOK, BISHOP, KNIGHT)
_PIECE_CHARS = "kqrbnp.PNBRQK"  # indexed by the signed piece code + 6
_FEN_CASTLING_REGEX = re.compile(r"^(?:-|[KQABCDEFGH]{0,2}[kqabcdefgh]{0,2})\Z")


class _Castling(NamedTuple):
    right: int  # bit in Board._castling; bit i belongs to the flag "KQkq"[i]
    king_from: Square
    king_to: Square
    rook_from: Square
    rook_to: Square
    empty: Tuple[Square, ...]
    safe: Tuple[Square, ...]  # besides the king's own square, which must not be in check either


# Kingside first: the order python-chess lists castling moves in.
_CASTLINGS = {
    WHITE: (_Castling(1, E1, G1, H1, F1, (F1, G1), (F1, G1)), _Castling(2, E1, C1, A1, D1, (D1, C1, B1), (D1, C1))),
    BLACK: (_Castling(4, E8, G8, H8, F8, (F8, G8), (F8, G8)), _Castling(8, E8, C8, A8, D8, (D8, C8, B8), (D8, C8))),
}
_CASTLING_BY_KING_MOVE = {(c.king_from, c.king_to): c for side in _CASTLINGS.values() for c in side}
_CASTLING_BY_KING_TAKES_ROOK = {(c.king_from, c.rook_from): c for c in _CASTLING_BY_KING_MOVE.values()}
_CASTLING_RIGHTS = {WHITE: 1 | 2, BLACK: 4 | 8}
# The right that is lost when a move starts or ends on each square (the rooks' home squares).
_RIGHT_AT = [sum(c.right for c in _CASTLING_BY_KING_MOVE.values() if c.rook_from == square) for square in SQUARES]


# ------------------------------------------------------------------- value types
class InvalidMoveError(ValueError):
    """Raised when move notation is not syntactically valid."""


class IllegalMoveError(ValueError):
    """Raised when a move is not legal in the current position."""


@dataclasses.dataclass(frozen=True)
class Piece:
    """A piece type and color."""

    piece_type: PieceType
    color: Color

    def symbol(self) -> str:
        """``P``, ``N``, ``B``, ``R``, ``Q`` or ``K`` for white pieces, lower case for black ones."""
        symbol = PIECE_SYMBOLS[self.piece_type] or ""
        return symbol.upper() if self.color else symbol

    def __str__(self) -> str:
        return self.symbol()

    @classmethod
    def from_symbol(cls, symbol: str) -> "Piece":
        return cls(PIECE_SYMBOLS.index(symbol.lower()), symbol.isupper())


class Move(NamedTuple):
    """A move from one square to another, optionally promoting a pawn.

    ``Move(0, 0)`` is the null move, which is falsy and never legal.
    """

    from_square: Square
    to_square: Square
    promotion: Optional[PieceType] = None

    def uci(self) -> str:
        if not self:
            return "0000"
        promotion = PIECE_SYMBOLS[self.promotion] if self.promotion else ""
        return f"{SQUARE_NAMES[self.from_square]}{SQUARE_NAMES[self.to_square]}{promotion}"

    def __bool__(self) -> bool:
        return bool(self.from_square or self.to_square or self.promotion)

    def __str__(self) -> str:
        return self.uci()

    def __repr__(self) -> str:
        return f"Move.from_uci({self.uci()!r})"

    @classmethod
    def from_uci(cls, uci: str) -> "Move":
        """Parse UCI such as ``e2e4`` or ``e7e8q``; ``0000`` is the null move.

        Raises ``InvalidMoveError`` for malformed strings, including a move
        to its own square such as ``a1a1``. Promotion letters ``k`` and ``p``
        parse, but such moves are never legal.
        """
        if uci == "0000":
            return cls.null()
        if not 4 <= len(uci) <= 5:
            raise InvalidMoveError(f"expected uci string to be of length 4 or 5: {uci!r}")
        try:
            from_square = SQUARE_NAMES.index(uci[0:2])
            to_square = SQUARE_NAMES.index(uci[2:4])
            promotion = PIECE_SYMBOLS.index(uci[4]) if len(uci) == 5 else None
        except ValueError:
            raise InvalidMoveError(f"invalid uci: {uci!r}") from None
        if from_square == to_square:
            raise InvalidMoveError(f"invalid uci (use 0000 for null moves): {uci!r}")
        return cls(from_square, to_square, promotion)

    @classmethod
    def null(cls) -> "Move":
        return cls(0, 0)


class Termination(enum.Enum):
    """Why a game ended."""

    CHECKMATE = enum.auto()
    STALEMATE = enum.auto()
    INSUFFICIENT_MATERIAL = enum.auto()
    SEVENTYFIVE_MOVES = enum.auto()
    FIVEFOLD_REPETITION = enum.auto()
    FIFTY_MOVES = enum.auto()
    THREEFOLD_REPETITION = enum.auto()


@dataclasses.dataclass
class Outcome:
    """How a game ended; ``winner`` is ``None`` for a draw."""

    termination: Termination
    winner: Optional[Color]

    def result(self) -> str:
        return "1/2-1/2" if self.winner is None else ("1-0" if self.winner else "0-1")


class _Position(NamedTuple):
    """The parts of a position that decide whether it repeats an earlier one."""

    board: Tuple[int, ...]
    turn: Color
    castling: int
    en_passant: Optional[Square]  # only set when an en passant capture is legal


class _Undo(NamedTuple):
    position: _Position
    ep_square: Optional[Square]
    halfmove_clock: int
    fullmove_number: int


class LegalMoveGenerator:
    """Live view of a board's legal moves: iterable, sized, and supports ``move in ...``."""

    def __init__(self, board: "Board") -> None:
        self.board = board

    def __iter__(self) -> Iterator[Move]:
        return self.board.generate_legal_moves()

    def __contains__(self, move: Move) -> bool:
        return self.board.is_legal(move)

    def __len__(self) -> int:
        return len(self.board._legal_moves())

    def __bool__(self) -> bool:
        return bool(self.board._legal_moves())

    def count(self) -> int:
        return len(self)

    def __repr__(self) -> str:
        return f"<LegalMoveGenerator ({', '.join(move.uci() for move in self)})>"


# ------------------------------------------------------------------------- board
class Board:
    """A chess position together with the moves that led to it.

    Like python-chess, any syntactically valid FEN is accepted, and ``push``
    does not validate moves (check ``move in board.legal_moves`` first, or use
    ``push_uci``).
    """

    def __init__(self, fen: Optional[str] = STARTING_FEN) -> None:
        self.set_fen(_EMPTY_FEN if fen is None else fen)

    # ------------------------------------------------------------------ setup
    def set_fen(self, fen: str) -> None:
        """Set up the position described by ``fen`` and forget the move history.

        Trailing fields may be omitted and default to ``w - - 0 1``.
        """
        parts = fen.split()
        if not parts:
            raise ValueError("empty fen")
        board_part = parts.pop(0)
        turn_part = parts.pop(0) if parts else "w"
        if turn_part not in ("w", "b"):
            raise ValueError(f"expected 'w' or 'b' for turn part of fen: {fen!r}")
        castling_part = parts.pop(0) if parts else "-"
        if not _FEN_CASTLING_REGEX.match(castling_part):
            raise ValueError(f"invalid castling part in fen: {fen!r}")
        ep_part = parts.pop(0) if parts else "-"
        if ep_part != "-" and ep_part not in SQUARE_NAMES:
            raise ValueError(f"invalid en passant part in fen: {fen!r}")
        halfmove_clock = _parse_fen_counter(parts.pop(0), "half-move clock", fen) if parts else 0
        fullmove_number = max(_parse_fen_counter(parts.pop(0), "fullmove number", fen), 1) if parts else 1
        if parts:
            raise ValueError(f"fen string has more parts than expected: {fen!r}")

        self._board = _parse_board_fen(board_part)
        self.turn: Color = turn_part == "w"
        self._castling = self._castling_from_fen(castling_part)
        self.ep_square: Optional[Square] = None if ep_part == "-" else SQUARE_NAMES.index(ep_part)
        self.halfmove_clock = halfmove_clock
        self.fullmove_number = fullmove_number
        self.move_stack: List[Move] = []
        self._undo: List[_Undo] = []
        self._seen: Dict[_Position, int] = {}  # how often each earlier position occurred

    def _castling_from_fen(self, flags: str) -> int:
        """The castling rights named in ``flags`` that the position can actually have.

        A right survives only if the king and that rook are on their original
        squares; file letters (Shredder/X-FEN) are accepted for the corner rooks.
        """
        requested = 0
        if flags != "-":
            for flag in flags:
                name = flag.lower()
                file = 7 if name == "k" else 0 if name == "q" else FILE_NAMES.index(name)
                requested |= _RIGHT_AT[(0 if flag.isupper() else 56) + file]
        rights = 0
        for color, castlings in _CASTLINGS.items():
            sign = 1 if color else -1
            for castling in castlings:
                if (requested & castling.right and self._board[castling.king_from] == KING * sign
                        and self._board[castling.rook_from] == ROOK * sign):
                    rights |= castling.right
        return rights

    def reset(self) -> None:
        """Restore the starting position."""
        self.set_fen(STARTING_FEN)

    def clear(self) -> None:
        """Remove all pieces (white to move, no castling rights, empty history)."""
        self.set_fen(_EMPTY_FEN)

    def copy(self, *, stack: bool = True) -> "Board":
        """A copy of the board, including its move history unless ``stack`` is false."""
        board = type(self).__new__(type(self))
        board._board = self._board[:]
        board.turn = self.turn
        board._castling = self._castling
        board.ep_square = self.ep_square
        board.halfmove_clock = self.halfmove_clock
        board.fullmove_number = self.fullmove_number
        board.move_stack = self.move_stack[:] if stack else []
        board._undo = self._undo[:] if stack else []
        board._seen = dict(self._seen) if stack else {}
        return board

    def __copy__(self) -> "Board":
        return self.copy()

    def __deepcopy__(self, memo: Dict[int, object]) -> "Board":
        board = self.copy()
        memo[id(self)] = board
        return board

    # ------------------------------------------------------------- inspection
    def piece_at(self, square: Square) -> Optional[Piece]:
        piece = self._board[square]
        return Piece(abs(piece), piece > 0) if piece else None

    def piece_type_at(self, square: Square) -> Optional[PieceType]:
        return abs(self._board[square]) or None

    def color_at(self, square: Square) -> Optional[Color]:
        piece = self._board[square]
        return piece > 0 if piece else None

    def king(self, color: Color) -> Optional[Square]:
        """Square of ``color``'s king (the highest one if a FEN placed several), or ``None``."""
        try:
            return 63 - self._board[::-1].index(KING if color else -KING)
        except ValueError:
            return None

    def has_castling_rights(self, color: Color) -> bool:
        return bool(self._castling & _CASTLING_RIGHTS[color])

    def board_fen(self) -> str:
        rows = []
        for rank in range(7, -1, -1):
            row, empty = "", 0
            for piece in self._board[rank * 8:rank * 8 + 8]:
                if not piece:
                    empty += 1
                    continue
                if empty:
                    row, empty = row + str(empty), 0
                row += _PIECE_CHARS[piece + 6]
            rows.append(row + str(empty) if empty else row)
        return "/".join(rows)

    def castling_xfen(self) -> str:
        return "".join(flag for bit, flag in enumerate("KQkq") if self._castling >> bit & 1) or "-"

    def fen(self) -> str:
        """FEN of the position; the en passant square is only given when an en passant capture is legal."""
        ep_square = self._legal_en_passant_square()
        return " ".join([
            self.board_fen(),
            "w" if self.turn else "b",
            self.castling_xfen(),
            SQUARE_NAMES[ep_square] if ep_square is not None else "-",
            str(self.halfmove_clock),
            str(self.fullmove_number),
        ])

    def __str__(self) -> str:
        return "\n".join(
            " ".join(_PIECE_CHARS[piece + 6] for piece in self._board[rank * 8:rank * 8 + 8])
            for rank in range(7, -1, -1)
        )

    def __repr__(self) -> str:
        return f"Board({self.fen()!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return (self.halfmove_clock == other.halfmove_clock
                and self.fullmove_number == other.fullmove_number
                and self._position() == other._position())

    # --------------------------------------------------------- move generation
    @property
    def legal_moves(self) -> LegalMoveGenerator:
        return LegalMoveGenerator(self)

    def generate_legal_moves(self) -> Iterator[Move]:
        return iter(self._legal_moves())

    def is_legal(self, move: Move) -> bool:
        return self._normalize_castling(move) in self._legal_moves()

    def _legal_moves(self) -> List[Move]:
        """All legal moves, in the order python-chess lists them.

        Pieces other than pawns come first, from h8 down to a1 and each with
        its targets from h8 down to a1; then castling (kingside first), pawn
        captures, single and double pawn pushes, and en passant. In check,
        king moves come first.
        """
        board = self._board
        us = 1 if self.turn else -1
        king = self.king(self.turn)
        checks, pins = self._checks_and_pins(king) if king is not None else ([], {})
        moves: List[Move] = []

        evasion: Optional[Tuple[Square, ...]] = None
        if checks:
            self._add_king_moves(king, moves)
            if len(checks) > 1:
                return moves
            evasion = checks[0]

        pawns = []
        for square in range(63, -1, -1):
            piece = board[square] * us
            if piece <= 0:
                continue
            if piece == PAWN:
                pawns.append(square)
                continue
            if piece == KING:
                if checks:
                    continue
                if square == king:
                    self._add_king_moves(king, moves)
                    continue
            if piece == KNIGHT or piece == KING:
                leaps = _KNIGHT_TARGETS[square] if piece == KNIGHT else _KING_TARGETS[square]
                targets = [to for to in leaps if board[to] * us <= 0]
            else:
                targets = _slide(board, us, _SLIDER_RAYS[piece][square])
            pin = pins.get(square)
            for to in targets:
                if (pin is None or to in pin) and (evasion is None or to in evasion):
                    moves.append(Move(square, to))

        if not checks:
            self._add_castling_moves(moves)
        if pawns:
            self._add_pawn_moves(pawns, pins, evasion, moves)
            for square in self._en_passant_capturers():
                if self._en_passant_is_safe(square, king):
                    moves.append(Move(square, self.ep_square))
        return moves

    def _checks_and_pins(self, king: Square) -> Tuple[List[Tuple[Square, ...]], Dict[Square, Tuple[Square, ...]]]:
        """Attacks on the king of the side to move.

        Returns, for each checking piece, the squares where a move answers the
        check (the checker plus, for a slider, the squares in between), and
        maps each pinned piece to the squares along its pin it may move to.
        """
        board = self._board
        us = 1 if self.turn else -1
        checks: List[Tuple[Square, ...]] = []
        pins: Dict[Square, Tuple[Square, ...]] = {}
        for rays, slider in ((_ROOK_RAYS[king], ROOK), (_BISHOP_RAYS[king], BISHOP)):
            for ray in rays:
                blocker = None
                for distance, square in enumerate(ray, 1):
                    piece = board[square] * us
                    if not piece:
                        continue
                    if piece > 0:
                        if blocker is not None:
                            break
                        blocker = square
                        continue
                    if piece == -slider or piece == -QUEEN:
                        if blocker is None:
                            checks.append(ray[:distance])
                        else:
                            pins[blocker] = ray[:distance]
                    break
        for squares, attacker in (
            (_KNIGHT_TARGETS[king], KNIGHT),
            (_PAWN_ATTACKS[self.turn][king], PAWN),
            (_KING_TARGETS[king], KING),
        ):
            checks.extend((square,) for square in squares if board[square] == -attacker * us)
        return checks, pins

    def _add_king_moves(self, king: Square, moves: List[Move]) -> None:
        board = self._board
        us = 1 if self.turn else -1
        piece, board[king] = board[king], 0  # attacks through the square the king leaves still count
        for to in _KING_TARGETS[king]:
            if board[to] * us <= 0 and not self._is_attacked(to, not self.turn):
                moves.append(Move(king, to))
        board[king] = piece

    def _add_castling_moves(self, moves: List[Move]) -> None:
        if not self._castling & _CASTLING_RIGHTS[self.turn]:
            return
        board = self._board
        king = KING if self.turn else -KING
        for castling in _CASTLINGS[self.turn]:
            if (self._castling & castling.right and board[castling.king_from] == king
                    and not any(board[square] for square in castling.empty)
                    and not any(self._is_attacked(square, not self.turn) for square in castling.safe)):
                moves.append(Move(castling.king_from, castling.king_to))

    def _add_pawn_moves(self, pawns: List[Square], pins: Dict[Square, Tuple[Square, ...]],
                        evasion: Optional[Tuple[Square, ...]], moves: List[Move]) -> None:
        board = self._board
        us = 1 if self.turn else -1
        forward = 8 * us
        double_step_ranks = (0, 1) if self.turn else (6, 7)
        attacks = _PAWN_ATTACKS[self.turn]

        def allowed(square: Square, to: Square) -> bool:
            pin = pins.get(square)
            return (pin is None or to in pin) and (evasion is None or to in evasion)

        for square in pawns:
            for to in attacks[square]:
                if board[to] * us < 0 and allowed(square, to):
                    _add_pawn_move(moves, square, to)
        for square in pawns:
            to = square + forward
            if 0 <= to < 64 and not board[to] and allowed(square, to):
                _add_pawn_move(moves, square, to)
        for square in pawns:
            to = square + 2 * forward
            if (square_rank(square) in double_step_ranks and not board[square + forward] and not board[to]
                    and allowed(square, to)):
                moves.append(Move(square, to))

    def _en_passant_capturers(self) -> List[Square]:
        """Pawns placed to capture en passant, before checking that it is safe for the king."""
        ep_square = self.ep_square
        if not ep_square or self._board[ep_square]:
            return []
        pawn = PAWN if self.turn else -PAWN
        rank = 4 if self.turn else 3
        return [
            square for square in _PAWN_ATTACKS[not self.turn][ep_square]
            if self._board[square] == pawn and square_rank(square) == rank
        ]

    def _en_passant_is_safe(self, square: Square, king: Optional[Square]) -> bool:
        """Whether capturing en passant from ``square`` leaves the king out of check.

        Plays the capture on the board and tests the king directly, which also
        covers the captured pawn uncovering an attack along the rank.
        """
        if king is None:
            return True
        board = self._board
        to = self.ep_square
        captured = to - 8 if self.turn else to + 8
        pawn, victim = board[square], board[captured]
        board[square], board[captured], board[to] = 0, 0, pawn
        safe = not self._is_attacked(king, not self.turn)
        board[square], board[captured], board[to] = pawn, victim, 0
        return safe

    def _legal_en_passant_square(self) -> Optional[Square]:
        """The en passant square if an en passant capture is among the legal moves, else ``None``."""
        capturers = self._en_passant_capturers()
        if not capturers:
            return None
        king = self.king(self.turn)
        if king is not None and len(self._checks_and_pins(king)[0]) > 1:
            return None
        return self.ep_square if any(self._en_passant_is_safe(square, king) for square in capturers) else None

    def has_legal_en_passant(self) -> bool:
        return self._legal_en_passant_square() is not None

    def _is_attacked(self, square: Square, by: Color) -> bool:
        board = self._board
        sign = 1 if by else -1
        for squares, attacker in (
            (_KNIGHT_TARGETS[square], KNIGHT),
            (_PAWN_ATTACKS[not by][square], PAWN),
            (_KING_TARGETS[square], KING),
        ):
            piece = attacker * sign
            for origin in squares:
                if board[origin] == piece:
                    return True
        queen = QUEEN * sign
        for rays, slider in ((_ROOK_RAYS[square], ROOK * sign), (_BISHOP_RAYS[square], BISHOP * sign)):
            for ray in rays:
                for origin in ray:
                    piece = board[origin]
                    if piece:
                        if piece == slider or piece == queen:
                            return True
                        break
        return False

    def is_check(self) -> bool:
        king = self.king(self.turn)
        return king is not None and self._is_attacked(king, not self.turn)

    # --------------------------------------------------------- making moves
    def _normalize_castling(self, move: Move) -> Move:
        """Map castling written as king-takes-rook (``e1h1``) to the king's own move (``e1g1``).

        python-chess accepts both forms for standard chess, so players may use either.
        """
        castling = _CASTLING_BY_KING_TAKES_ROOK.get((move.from_square, move.to_square))
        if castling and move.promotion is None and abs(self._board[castling.king_from]) == KING:
            return Move(castling.king_from, castling.king_to)
        return move

    def push(self, move: Move) -> None:
        """Play ``move`` (which is not validated) and remember it for ``pop``."""
        move = self._normalize_castling(move)
        position = self._position()
        self._seen[position] = self._seen.get(position, 0) + 1
        self._undo.append(_Undo(position, self.ep_square, self.halfmove_clock, self.fullmove_number))
        self.move_stack.append(move)

        board = self._board
        white = self.turn
        ep_square = self.ep_square
        self.turn = not white
        self.ep_square = None
        self.halfmove_clock += 1
        if not white:
            self.fullmove_number += 1
        if not move:
            return

        from_square, to_square, promotion = move
        piece = board[from_square]
        captured = board[to_square]
        piece_type = abs(piece)
        if piece_type == PAWN or captured:
            self.halfmove_clock = 0

        if self._castling:
            self._castling &= ~(_RIGHT_AT[from_square] | _RIGHT_AT[to_square])
            if piece_type == KING:
                self._castling &= ~_CASTLING_RIGHTS[white]
            elif abs(captured) == KING and square_rank(to_square) == (7 if white else 0):
                # Kings can only be captured in positions set up by a FEN where the side not to move is in check.
                self._castling &= ~_CASTLING_RIGHTS[not white]

        if piece_type == PAWN:
            step = to_square - from_square
            if step == 16 and square_rank(from_square) == 1:
                self.ep_square = from_square + 8
            elif step == -16 and square_rank(from_square) == 6:
                self.ep_square = from_square - 8
            elif to_square == ep_square and abs(step) in (7, 9) and not captured:
                board[ep_square - 8 if white else ep_square + 8] = 0
        elif piece_type == KING and (from_square, to_square) in _CASTLING_BY_KING_MOVE:
            castling = _CASTLING_BY_KING_MOVE[from_square, to_square]
            board[castling.rook_to], board[castling.rook_from] = board[castling.rook_from], 0
        if promotion:
            piece = promotion if white else -promotion

        board[from_square] = 0
        board[to_square] = piece

    def pop(self) -> Move:
        """Take back the last move and return it."""
        move = self.move_stack.pop()
        undo = self._undo.pop()
        position = undo.position
        if self._seen[position] == 1:
            del self._seen[position]
        else:
            self._seen[position] -= 1
        self._board = list(position.board)
        self.turn = position.turn
        self._castling = position.castling
        self.ep_square = undo.ep_square
        self.halfmove_clock = undo.halfmove_clock
        self.fullmove_number = undo.fullmove_number
        return move

    def peek(self) -> Move:
        return self.move_stack[-1]

    def parse_uci(self, uci: str) -> Move:
        """The legal move ``uci`` denotes (castling normalized to ``e1g1`` form).

        Raises ``InvalidMoveError`` for malformed UCI and ``IllegalMoveError``
        for illegal moves. The null move ``0000`` is returned unchecked.
        """
        move = Move.from_uci(uci)
        if not move:
            return move
        move = self._normalize_castling(move)
        if not self.is_legal(move):
            raise IllegalMoveError(f"illegal uci: {uci!r} in {self.fen()}")
        return move

    def push_uci(self, uci: str) -> Move:
        move = self.parse_uci(uci)
        self.push(move)
        return move

    def is_zeroing(self, move: Move) -> bool:
        """Whether a legal move resets the halfmove clock: a pawn move or a capture."""
        enemy = -1 if self.turn else 1
        return abs(self._board[move.from_square]) == PAWN or self._board[move.to_square] * enemy > 0

    # ---------------------------------------------------------------- game end
    def is_checkmate(self) -> bool:
        return self.is_check() and not self._legal_moves()

    def is_stalemate(self) -> bool:
        return not self.is_check() and not self._legal_moves()

    def has_insufficient_material(self, color: Color) -> bool:
        """Whether ``color`` can no longer checkmate by any sequence of legal moves.

        Uses python-chess's material-only test: a lone knight or same-colored
        bishops are insufficient unless the opponent has pieces that could
        block their own king in.
        """
        sign = 1 if color else -1
        own = [piece * sign for piece in self._board if piece * sign > 0]
        if PAWN in own or ROOK in own or QUEEN in own:
            return False
        if KNIGHT in own:
            return len(own) <= 2 and all(abs(piece) in (KING, QUEEN) for piece in self._board if piece * sign < 0)
        if BISHOP in own:
            shades = {(square_file(square) + square_rank(square)) % 2
                      for square in SQUARES if abs(self._board[square]) == BISHOP}
            return len(shades) == 1 and not any(abs(piece) in (PAWN, KNIGHT) for piece in self._board)
        return True

    def is_insufficient_material(self) -> bool:
        return self.has_insufficient_material(WHITE) and self.has_insufficient_material(BLACK)

    def is_seventyfive_moves(self) -> bool:
        return self.halfmove_clock >= 150 and bool(self._legal_moves())

    def is_fifty_moves(self) -> bool:
        """The halfmove clock reached 100 and the game has not ended otherwise (by checkmate or stalemate)."""
        return self.halfmove_clock >= 100 and bool(self._legal_moves())

    def is_repetition(self, count: int = 3) -> bool:
        """Whether the current position has occurred ``count`` times since the last ``set_fen``.

        Positions are the same when the pieces, side to move, castling rights and
        any legal en passant capture are the same.
        """
        return self._seen.get(self._position(), 0) + 1 >= count

    def is_fivefold_repetition(self) -> bool:
        return self.is_repetition(5)

    def can_claim_fifty_moves(self) -> bool:
        """Whether the fifty-move rule applies now or after one of the legal moves."""
        if self.is_fifty_moves():
            return True
        if self.halfmove_clock >= 99:
            for move in self._legal_moves():
                if not self.is_zeroing(move):
                    self.push(move)
                    try:
                        if self.is_fifty_moves():
                            return True
                    finally:
                        self.pop()
        return False

    def can_claim_threefold_repetition(self) -> bool:
        """Whether the position occurred three times, or will after one of the legal moves."""
        if self.is_repetition(3):
            return True
        for move in self._legal_moves():
            self.push(move)
            try:
                if self.is_repetition(3):
                    return True
            finally:
                self.pop()
        return False

    def outcome(self, *, claim_draw: bool = False) -> Optional[Outcome]:
        """The game's result, or ``None`` while it continues.

        Checked in python-chess's order: checkmate, insufficient material,
        stalemate, the seventy-five-move rule and fivefold repetition; with
        ``claim_draw``, also the fifty-move rule and threefold repetition.
        """
        has_moves = bool(self._legal_moves())
        if not has_moves and self.is_check():
            return Outcome(Termination.CHECKMATE, not self.turn)
        if self.is_insufficient_material():
            return Outcome(Termination.INSUFFICIENT_MATERIAL, None)
        if not has_moves:
            return Outcome(Termination.STALEMATE, None)
        if self.halfmove_clock >= 150:
            return Outcome(Termination.SEVENTYFIVE_MOVES, None)
        if self.is_repetition(5):
            return Outcome(Termination.FIVEFOLD_REPETITION, None)
        if claim_draw:
            if self.can_claim_fifty_moves():
                return Outcome(Termination.FIFTY_MOVES, None)
            if self.can_claim_threefold_repetition():
                return Outcome(Termination.THREEFOLD_REPETITION, None)
        return None

    def result(self, *, claim_draw: bool = False) -> str:
        outcome = self.outcome(claim_draw=claim_draw)
        return outcome.result() if outcome else "*"

    def _position(self) -> _Position:
        return _Position(tuple(self._board), self.turn, self._castling, self._legal_en_passant_square())


# ---------------------------------------------------------------------- helpers
def _slide(board: List[int], us: int, rays: Tuple[Tuple[Square, ...], ...]) -> List[Square]:
    """Empty or enemy-occupied squares a slider reaches along ``rays``, from h8 down to a1."""
    targets = []
    for ray in rays:
        for to in ray:
            occupant = board[to] * us
            if occupant <= 0:
                targets.append(to)
            if occupant:
                break
    targets.sort(reverse=True)
    return targets


def _add_pawn_move(moves: List[Move], square: Square, to: Square) -> None:
    if to < 8 or to >= 56:
        moves.extend(Move(square, to, promotion) for promotion in _PROMOTIONS)
    else:
        moves.append(Move(square, to))


def _parse_fen_counter(text: str, name: str, fen: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f"invalid {name} in fen: {fen!r}") from None
    if value < 0:
        raise ValueError(f"{name} cannot be negative: {fen!r}")
    return value


def _parse_board_fen(board_fen: str) -> List[int]:
    rows = board_fen.split("/")
    if len(rows) != 8:
        raise ValueError(f"expected 8 rows in position part of fen: {board_fen!r}")
    board = [0] * 64
    for rank, row in zip(range(7, -1, -1), rows):
        file = 0
        previous = ""
        for char in row:
            if char in "12345678":
                if previous == "digit":
                    raise ValueError(f"two subsequent digits in position part of fen: {board_fen!r}")
                file += int(char)
                previous = "digit"
            elif char == "~":  # python-chess's promoted-piece marker, meaningless in standard chess
                if previous != "piece":
                    raise ValueError(f"'~' not after piece in position part of fen: {board_fen!r}")
                previous = ""
            elif char.lower() in PIECE_SYMBOLS:
                if file < 8:
                    piece_type = PIECE_SYMBOLS.index(char.lower())
                    board[rank * 8 + file] = piece_type if char.isupper() else -piece_type
                file += 1
                previous = "piece"
            else:
                raise ValueError(f"invalid character in position part of fen: {board_fen!r}")
        if file != 8:
            raise ValueError(f"expected 8 columns per row in position part of fen: {board_fen!r}")
    return board
