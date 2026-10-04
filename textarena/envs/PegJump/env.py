import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class PegJumpEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    ACTION_RE = re.compile(r"(?P<source>\d{1,2})(?:\s*,\s*|\s+)(?P<target>\d{1,2})")
    BOARD_SIZE = 15

    _BASE_TRIPLES: List[Tuple[int, int, int]] = [
        (1, 2, 4), (1, 3, 6), (2, 4, 7), (2, 5, 9), (3, 5, 8), (3, 6, 10), (4, 5, 6), (4, 7, 11), (4, 8, 13),
        (5, 8, 12), (5, 9, 14), (6, 9, 13), (6, 10, 15), (7, 8, 9), (8, 9, 10),
        (11, 12, 13), (12, 13, 14), (13, 14, 15),
    ]
    def __init__(self, initial_empty: int = 1):
        if (
            not isinstance(initial_empty, int)
            or isinstance(initial_empty, bool)
            or not 1 <= initial_empty <= self.BOARD_SIZE
        ):
            raise ValueError("initial_empty must be an integer from 1 to 15")
        self.ALLOWED_MOVES: List[Tuple[int, int, int]] = self._BASE_TRIPLES + [
            (target, over, source) for source, over, target in self._BASE_TRIPLES
        ]
        self.initial_empty = initial_empty

    def setup(self) -> Dict[str, Any]:
        board = [False] + [True] * self.BOARD_SIZE
        board[self.initial_empty] = False
        return {"board": board}

    def prompt(self, player_id: int) -> str:
        source, over, target = self._legal_moves()[0]
        return (
            "You are playing PegJump, a triangular peg solitaire with 15 holes numbered 1 to 15 row by row from the "
            "top (hole 1 is the apex, holes 11 to 15 the bottom row). On the board, ● is a peg and ○ is an empty hole.\n"
            "A move jumps one peg over an adjacent peg into the empty hole directly beyond it, in a straight line "
            "along a row or a diagonal. The jumped peg is removed.\n"
            f"Reply with the source and target holes, e.g. '{source} {target}' jumps the peg in hole {source} over "
            f"hole {over} into hole {target}. The legal jumps are listed under the board.\n"
            "Goal: finish with exactly one peg left. The game ends when one peg remains or no jump is possible.\n"
            "An illegal or malformed move changes nothing and you may try again, but two invalid moves in a row end the game."
        )

    def render(self, player_id: int) -> str:
        legal = ", ".join(f"{source} {target}" for source, _, target in self._legal_moves()) or "none"
        return f"Pegs left: {self.game_state['board'].count(True)}\n{self._render_board()}\nLegal jumps: {legal}"

    def _render_board(self) -> str:
        """Return a string visualising the triangle with hole numbers."""
        b = self.game_state["board"]
        rows: List[str] = []
        idx = 1
        for r in range(5):  # rows 0–4  (1, 2, 3, 4, 5 holes)
            tokens: List[str] = []
            for _ in range(r + 1):
                peg = b[idx]
                symbol = "●" if peg else "○"
                tokens.append(f"{idx:>3}{symbol}")  # two-digit index + peg/empty
                idx += 1
            # centre-align by left-padding
            indent = " " * (3 * (4 - r))
            rows.append(indent + " ".join(tokens))
        return "\n".join(rows)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = self.ACTION_RE.fullmatch(move.strip())
        if not match:
            return self.invalid("Invalid syntax. Reply with 'from to' hole numbers, e.g. '4 1'.")
        frm, to = int(match.group("source")), int(match.group("target"))
        board = self.game_state["board"]
        if not (1 <= frm <= self.BOARD_SIZE and 1 <= to <= self.BOARD_SIZE):
            return self.invalid(f"Illegal move: holes are numbered 1 to {self.BOARD_SIZE}.")
        over = self._get_over(frm, to)
        if over is None:
            return self.invalid(f"Illegal move: hole {to} is not two holes away from hole {frm} in a straight line.")
        if not board[frm]:
            return self.invalid(f"Illegal move: hole {frm} has no peg.")
        if not board[over]:
            return self.invalid(f"Illegal move: hole {over} between {frm} and {to} has no peg to jump over.")
        if board[to]:
            return self.invalid(f"Illegal move: hole {to} is not empty.")
        # Execute move
        board[frm] = False
        board[over] = False
        board[to] = True
        # Check terminal conditions
        peg_cnt = board.count(True)
        if peg_cnt == 1:        return self.outcome({0: 1.0}, reason="Solved with one peg remaining!")
        elif not self._has_move(): return self.outcome({0: self._get_percentage_completion()}, reason="No moves left.")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_over(self, frm: int, to: int) -> Optional[int]:
        """Return the hole *over* which `frm` jumps to reach `to`, or None."""
        for (f, o, t) in self.ALLOWED_MOVES:
            if f == frm and t == to: return o
        return None

    def _has_move(self) -> bool:
        return bool(self._legal_moves())

    def _legal_moves(self) -> List[Tuple[int, int, int]]:
        board = self.game_state["board"]
        return sorted((f, o, t) for f, o, t in self.ALLOWED_MOVES if board[f] and board[o] and not board[t])

    def _get_percentage_completion(self) -> float:
        # A standard opening has 14 pegs and therefore requires 13 jumps to
        # finish with one.  Measure completed jumps so the untouched opening is
        # worth 0 rather than 1/14.
        pegs_left = self.game_state["board"].count(True)
        return float(max(0.0, min(1.0, (self.BOARD_SIZE - 1 - pegs_left) / (self.BOARD_SIZE - 2))))
