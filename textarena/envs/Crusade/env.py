import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

FILES = "abcdefgh"
RANKS = "12345678"

def coord_to_rc(coord: str) -> Tuple[int, int]:
    f, r = coord[0].lower(), coord[1]
    return len(RANKS) - int(r), FILES.index(f)

def rc_to_coord(r: int, c: int) -> str:
    return f"{FILES[c]}{RANKS[len(RANKS) - 1 - r]}"


def _parse_cell_id(text: str) -> Optional[int]:
    """Parse a decimal cell ID without converting an unbounded integer."""
    normalized = text.lstrip("0") or "0"
    if len(normalized) > 2:
        return None
    cell = int(normalized)
    return cell if cell < 64 else None


class CrusadeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    BOARD_N = 8
    MAX_MOVES = 40
    SCORE_PER_CAPTURE = 1

    action_pattern = (
        r"^(?P<source>[a-hA-H][1-8]|[0-9]+)\s+"
        r"(?P<target>[a-hA-H][1-8]|[0-9]+)$"
    )
    action_format = "a move 'from to' in board coordinates, for example 'b1 c3' as White or 'b8 c6' as Black"

    def __init__(self):
        self.CELL_TO_RC = {i: (i // self.BOARD_N, i % self.BOARD_N) for i in range(self.BOARD_N ** 2)}
        self.RC_TO_CELL = {(r, c): i for i, (r, c) in self.CELL_TO_RC.items()}
        self.KNIGHT_DIRS = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
        self.max_turns = self.MAX_MOVES

    def setup(self) -> Dict[str, Any]:
        board = [['' for _ in range(self.BOARD_N)] for _ in range(self.BOARD_N)]
        for cell, (r, c) in self.CELL_TO_RC.items():
            if r < 2:   board[r][c] = 'B'
            elif r > 5: board[r][c] = 'W'
        return {"board": board, "score": [0, 0], "move_count": 0}

    def prompt(self, player_id: int) -> str:
        piece = 'W' if player_id == 0 else 'B'
        opp = 'B' if player_id == 0 else 'W'
        example = 'b1 c3' if player_id == 0 else 'b8 c6'
        return (
            f"You are Player {player_id} ({piece}). Opponent is ({opp}). Submit moves as '{example}' (from → to). All pieces move like chess knights.\n"
            "White (Player 0) starts on ranks 1-2 and moves first; Black (Player 1) starts on ranks 7-8. Files a-h run left to right, ranks 1-8 bottom to top. "
            "A piece may jump over other pieces and may land on an empty square or on an enemy piece, capturing it.\n"
            f"Each capture scores {self.SCORE_PER_CAPTURE} point. Capturing every enemy piece wins at once. Otherwise the game ends after "
            f"{self.MAX_MOVES} moves in total ({self.MAX_MOVES // 2} per player): higher score wins, equal scores draw."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        return (
            f"Move #{gs['move_count']}\n\n{self._render_board()}\n\n"
            f"Score: White (Player 0) {gs['score'][0]}, Black (Player 1) {gs['score'][1]} | Moves left: {self.MAX_MOVES - gs['move_count']}\n"
            "Available Moves: " + ", ".join(self._legal_moves_for_player(player_id))
        )

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        piece = 'W' if player_id == 0 else 'B'
        board = self.game_state["board"]

        frm = self._txt_to_cell(move.group("source"))
        to = self._txt_to_cell(move.group("target"))
        if frm is None or to is None: return self.invalid("Unknown square.")

        fr, fc = self.CELL_TO_RC[frm]
        tr, tc = self.CELL_TO_RC[to]
        dr, dc = tr - fr, tc - fc

        if board[fr][fc] != piece:           return self.invalid("Source is not your piece.")
        if board[tr][tc] == piece:           return self.invalid("Cannot land on own piece.")
        if (dr, dc) not in self.KNIGHT_DIRS: return self.invalid("Not a knight move.")

        # Handle capture
        message = f"Player {player_id} moved their piece from {rc_to_coord(fr, fc)} to {rc_to_coord(tr, tc)}."
        if board[tr][tc] == ('B' if player_id == 0 else 'W'):
            self.game_state["score"][player_id] += self.SCORE_PER_CAPTURE
            message += f" Capturing a piece! (+{self.SCORE_PER_CAPTURE})"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        board[tr][tc], board[fr][fc] = piece, ''
        self.game_state["move_count"] += 1

        for pid in (0, 1):
            pid_piece = 'W' if pid == 0 else 'B'
            if not any(pid_piece in row for row in board): return self.winner(1 - pid, reason=f"Player {pid} has no pieces.")
            if not self._legal_moves_for_player(pid):      return self.winner(1 - pid, reason=f"Player {pid} cannot move.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        s0, s1 = self.game_state["score"]
        if s0 > s1: return self.winner(0, reason="Higher capture score.")
        if s1 > s0: return self.winner(1, reason="Higher capture score.")
        return self.draw(reason="Move limit reached.")

    def _legal_moves_for_player(self, pid: int) -> List[str]:
        piece = 'W' if pid == 0 else 'B'
        moves = []
        for (r, c), cell_id in self.RC_TO_CELL.items():
            if self.game_state["board"][r][c] != piece: continue
            src = rc_to_coord(r, c)
            for dr, dc in self.KNIGHT_DIRS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N:
                    if self.game_state["board"][nr][nc] != piece: # empty or opponent
                        dst = rc_to_coord(nr, nc)
                        moves.append(f"'{src} {dst}'")
        return moves

    def _render_board(self) -> str:
        rows = []
        for r in range(self.BOARD_N):
            rank = str(self.BOARD_N - r)
            row = [self.game_state["board"][r][c] if self.game_state["board"][r][c] else '.' for c in range(self.BOARD_N)]
            rows.append(f"{rank} | " + " ".join(row))
        rows.append("    " + " ".join(FILES))
        return "\n".join(rows)

    def _txt_to_cell(self, txt: str) -> Optional[int]:
        if txt.isdigit():
            return _parse_cell_id(txt)
        if re.fullmatch(r"[a-hA-H][1-8]", txt):
            r, c = coord_to_rc(txt)
            return r * self.BOARD_N + c
        return None
