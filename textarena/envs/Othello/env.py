import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Othello.renderer import PIECE_SYMBOLS, create_board_str


DIRS = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
EMPTY, BLACK, WHITE = "", "B", "W"
COLOUR_NAMES = {BLACK: "Black", WHITE: "White"}

class OthelloEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"^\s*\[?\s*(\d+)(?:\s*,\s*|\s+)(\d+)\s*\]?\s*$"

    def __init__(self, board_size: int = 8, show_valid: bool = True):
        if (
            not isinstance(board_size, int)
            or isinstance(board_size, bool)
            or board_size % 2
            or board_size < 4
        ):
            raise ValueError("board_size must be an even integer ≥ 4")
        if not isinstance(show_valid, bool):
            raise ValueError("show_valid must be a boolean")
        self.N = board_size
        self.show_valid = show_valid

    @property
    def action_format(self) -> str:
        row, col = self.N // 2 - 2, self.N // 2 - 1  # one of Black's opening moves, (2, 3) on 8x8
        return f"the row and column of your move, each from 0 to {self.N - 1}, for example '{row}, {col}'"

    def setup(self) -> Dict[str, Any]:
        board = [[EMPTY for _ in range(self.N)] for _ in range(self.N)]
        m1, m2 = self.N // 2 - 1, self.N // 2  # initial four stones in the middle
        board[m1][m1] = board[m2][m2] = WHITE
        board[m1][m2] = board[m2][m1] = BLACK
        b_count, w_count = self._counts(board)
        return {
            "board": board, "rendered_board": self._render_board(board),
            "black_count": b_count, "white_count": w_count,
            "valid_moves": self._valid_moves(board, BLACK),
        }

    def roles(self) -> Dict[int, str]:
        return {0: "Black", 1: "White"}

    def prompt(self, player_id: int) -> str:
        piece = BLACK if player_id == 0 else WHITE
        return (
            f"You are Player {player_id} playing {COLOUR_NAMES[piece]} in a game of Othello.\n"
            f"On the board, Black discs are shown as '{PIECE_SYMBOLS[BLACK]}' and White discs as '{PIECE_SYMBOLS[WHITE]}'; your discs are '{PIECE_SYMBOLS[piece]}'.\n"
            "Your goal is to have more pieces of your color on the board by the end of the game.\n"
            f"On your turn, place a piece such that it flanks one or more of your opponent's pieces-in any direction (horizontal, vertical, or diagonal)-between your new piece and another of your existing pieces. "
            f"All flanked opponent pieces will be flipped to your color.\n"
            "If you have no legal move, your turn is skipped automatically. The game ends when the board is full or neither player can move; "
            "the player with more discs wins, and equal counts are a draw.\n"
            f"Reply with the row and column of your move (numbered from 0, as labelled on the board), e.g. '2, 3'."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        obs = f"Game Board:\n{gs['rendered_board']}"
        if self.show_valid:
            obs += "\nValid moves: " + ", ".join([f"'{r}, {c}'" for r, c in gs["valid_moves"]]) if gs["valid_moves"] else "\nNo valid moves - you may have to skip."
        obs += f"\nScores - {self._label(BLACK)}: {gs['black_count']}, {self._label(WHITE)}: {gs['white_count']}\n"
        return obs

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        board = gs["board"]
        piece = BLACK if player_id == 0 else WHITE
        opp = BLACK if piece == WHITE else WHITE

        try:
            r, c = map(int, move.groups())
        except ValueError:
            return self.invalid("Coordinates are too large.")
        valid = self._valid_moves(board, piece)
        if [r, c] not in valid:
            reason = f"({r}, {c}) is not a legal move: a move must be on an empty square and flip at least one opposing disc."
            if self.show_valid:
                reason += " Valid moves: " + ", ".join(f"'{vr}, {vc}'" for vr, vc in valid)
            return self.invalid(reason)

        flipped = self._place_and_flip(board, r, c, piece)
        self.broadcast(f"Player {player_id} ({self._label(piece)}) played ({r}, {c}) flipping {flipped} piece(s)", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        b, w = self._counts(board)
        gs.update({"rendered_board": self._render_board(board), "black_count": b, "white_count": w})

        opp_valid = self._valid_moves(board, opp)
        gs["valid_moves"] = opp_valid
        if self._game_over(board):
            return self._final_outcome(b, w)
        if not opp_valid:  # opponent has no legal move: they skip, same player moves again
            opp_pid = 1 - player_id
            self.broadcast(f"Player {opp_pid} ({self._label(opp)}) has no valid moves and must skip.", ta.ObservationType.GAME_MESSAGE)
            gs["valid_moves"] = self._valid_moves(board, piece)
            self.set_next_player(player_id)
        return None

    def get_board_str(self) -> str:
        return create_board_str(self.game_state["board"])

    def _label(self, piece: str) -> str:
        return f"{COLOUR_NAMES[piece]} {PIECE_SYMBOLS[piece]}"

    def _in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.N and 0 <= c < self.N

    def _counts(self, board) -> Tuple[int, int]:
        return sum(row.count(BLACK) for row in board), sum(row.count(WHITE) for row in board)

    def _valid_moves(self, board, piece) -> List[List[int]]:
        return [[r, c] for r in range(self.N) for c in range(self.N) if board[r][c] == EMPTY and self._would_flip(board, r, c, piece)]

    def _would_flip(self, board, r, c, piece) -> bool:
        opp = BLACK if piece == WHITE else WHITE
        for dr, dc in DIRS:
            rr, cc = r + dr, c + dc
            if not (self._in_bounds(rr, cc) and board[rr][cc] == opp): continue
            while self._in_bounds(rr, cc) and board[rr][cc] == opp:
                rr += dr; cc += dc
            if self._in_bounds(rr, cc) and board[rr][cc] == piece: return True
        return False

    def _place_and_flip(self, board, r, c, piece) -> int:
        opp = BLACK if piece == WHITE else WHITE
        board[r][c] = piece
        flipped = 0
        for dr, dc in DIRS:
            rr, cc = r + dr, c + dc
            line: List[Tuple[int, int]] = []
            while self._in_bounds(rr, cc) and board[rr][cc] == opp:
                line.append((rr, cc))
                rr += dr; cc += dc
            if self._in_bounds(rr, cc) and board[rr][cc] == piece:
                for fr, fc in line:
                    board[fr][fc] = piece
                flipped += len(line)
        return flipped

    def _game_over(self, board) -> bool:
        return all(cell != EMPTY for row in board for cell in row) or (not self._valid_moves(board, BLACK) and not self._valid_moves(board, WHITE))

    def _render_board(self, board) -> str:
        return create_board_str(board)

    def _final_outcome(self, b: int, w: int) -> ta.Outcome:
        if b > w: return self.winner(0, reason=f"Black wins {b}-{w}.")
        if w > b: return self.winner(1, reason=f"White wins {w}-{b}.")
        return self.draw(reason=f"Draw {b}-{w}.")
