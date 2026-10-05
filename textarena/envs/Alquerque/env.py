import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

FILES = "abcde"
RANKS = "12345"

def coord_to_rc(coord: str) -> Tuple[int, int]:
    """'a1' → (4,0)   (row 4 is bottom rank)."""
    f, r = coord[0].lower(), coord[1]
    return len(RANKS) - int(r), FILES.index(f)

def rc_to_coord(r: int, c: int) -> str:
    return f"{FILES[c]}{RANKS[len(RANKS) - 1 - r]}"


class AlquerqueEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    BOARD_N = 5
    MAX_MOVES = 60
    SCORE_PER_CAPTURE = 10

    _CELL_TOKEN = r"(?:[a-eA-E][1-5]|[0-9]+)"
    action_pattern = rf"^({_CELL_TOKEN}(?:(?:\s*->\s*|\s+){_CELL_TOKEN})+)$"
    action_format = (
        "a move 'from to' in board coordinates, listing every landing point of a multi-jump capture, "
        "for example 'c2 c3' as Red or 'c4 c3' as Black"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cell_to_rc = {i: (i // self.BOARD_N, i % self.BOARD_N) for i in range(self.BOARD_N ** 2)}
        self.rc_to_cell = {(r, c): i for i, (r, c) in self.cell_to_rc.items()}
        self.neighbours = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if not (dr == dc == 0)]
        self.forward_dirs = {0: [(-1, 0), (-1, -1), (-1, 1)], 1: [(1, 0),  (1, -1),  (1, 1)]}
        self.max_turns = self.MAX_MOVES

    def setup(self) -> Dict[str, Any]:
        board = [['' for _ in range(self.BOARD_N)] for _ in range(self.BOARD_N)] # Empty board then fill rows
        for cell, (r, c) in self.cell_to_rc.items():
            if r < 2:   board[r][c] = 'B'       # Black top
            elif r > 2: board[r][c] = 'R'       # Red  bottom
        return {"board": board, "score": [0, 0], "move_count": 0}

    def prompt(self, player_id: int) -> str:
        piece = 'R' if player_id == 0 else 'B'
        opp   = 'B' if player_id == 0 else 'R'
        example, forward = ("c2 c3", "toward rank 5") if player_id == 0 else ("c4 c3", "toward rank 1")
        return (
            f"You are Player {player_id} ({piece}). Opponent is ({opp}). Red (Player 0) starts on ranks 1-2 and moves first; "
            "Black (Player 1) starts on ranks 4-5.\n"
            "The board is a 5x5 grid of points: files a-e run left to right, ranks 1-5 bottom to top. Lines join neighbouring points "
            "horizontally and vertically, and diagonally only through a1, c1, e1, b2, d2, a3, c3, e3, b4, d4, a5, c5 and e5.\n"
            f"Submit moves as 'from to', e.g. '{example}'.\n"
            f"- A normal move is one forward step ({forward}, straight or diagonally along a line) to an adjacent empty vertex.\n"
            "- A capture is a jump over an adjacent enemy piece landing on the empty node beyond, in any direction along a line.\n"
            "- Captures are mandatory. Continue a capture in the same action while another jump is available "
            "(for example, 'c3 a3 c1').\n"
            f"Each capture yields {self.SCORE_PER_CAPTURE} points.\n"
            f"You lose if you have no pieces or no legal move on your turn. After {self.MAX_MOVES} moves in total, "
            "the higher score wins and equal scores draw."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        text = (
            f"Move #{gs['move_count']}\n\n{self._render_board()}\n\n"
            f"Score: Red (Player 0) {gs['score'][0]}, Black (Player 1) {gs['score'][1]} | Moves left: {self.MAX_MOVES - gs['move_count']}"
        )
        if not self.state.done:
            text += "\nLegal moves: " + ", ".join(self._legal_moves(player_id))
        return text

    def get_board_str(self) -> str:
        return self._render_board()

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        piece = 'R' if player_id == 0 else 'B'
        opp   = 'B' if player_id == 0 else 'R'

        board = self.game_state["board"]
        cells = [self._txt_to_cell(token) for token in re.findall(self._CELL_TOKEN, move.group(1))]
        if any(cell is None for cell in cells):
            return self.invalid("Unknown square.")

        path: List[int] = [cell for cell in cells if cell is not None]
        frm = path[0]
        fr, fc = self.cell_to_rc[frm]
        if board[fr][fc] != piece:
            return self.invalid("Source is not your piece.")

        must_capture = self._has_capture(player_id, board)
        trial = [row[:] for row in board]
        captures = 0

        for index, (frm, to) in enumerate(zip(path, path[1:])):
            fr, fc = self.cell_to_rc[frm]
            tr, tc = self.cell_to_rc[to]
            dr, dc = tr - fr, tc - fc
            if trial[fr][fc] != piece:
                return self.invalid("Every segment must continue with the same piece.")
            if trial[tr][tc] != '':
                return self.invalid("Destination not empty.")

            is_jump = (
                (dr == 0 and abs(dc) == 2)
                or (dc == 0 and abs(dr) == 2)
                or (abs(dr) == abs(dc) == 2 and self._diagonal_vertex(fr, fc))
            )
            if is_jump:
                mid_r, mid_c = fr + dr // 2, fc + dc // 2
                if trial[mid_r][mid_c] != opp:
                    return self.invalid("A capture must jump an opponent piece.")
                trial[tr][tc], trial[fr][fc], trial[mid_r][mid_c] = piece, '', ''
                captures += 1
                continue

            if index > 0 or must_capture:
                return self.invalid("A capture is available and must be completed.")
            if len(path) != 2 or (dr, dc) not in self.forward_dirs[player_id] or not self._is_connected_step(fr, fc, tr, tc):
                return self.invalid("Illegal move.")
            trial[tr][tc], trial[fr][fc] = piece, ''

        if captures:
            last_r, last_c = self.cell_to_rc[path[-1]]
            if self._has_capture_from(trial, last_r, last_c, piece, opp):
                return self.invalid("The capture sequence is incomplete.")
        elif must_capture:
            return self.invalid("A capture is available and must be taken.")

        for row, trial_row in zip(board, trial):
            row[:] = trial_row
        description = f"Player {player_id} ({piece}) moved " + " -> ".join(rc_to_coord(*self.cell_to_rc[cell]) for cell in path)
        if captures:
            points = captures * self.SCORE_PER_CAPTURE
            self.game_state["score"][player_id] += points
            description += f", capturing {captures} piece(s)! (+{points})"
        else:
            description += "."
        self.broadcast(description, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return self._after_move(player_id)

    def _after_move(self, player_id: int) -> Optional[ta.Outcome]:
        gs = self.game_state
        gs["move_count"] += 1

        # Only the player whose turn is next loses for having no pieces or
        # legal move. The mover may currently be blocked but become mobile
        # again after the opponent's reply.
        opponent_id = 1 - player_id
        opponent_piece = 'R' if opponent_id == 0 else 'B'
        if not any(opponent_piece in row for row in gs["board"]):
            return self.winner(player_id, reason=f"Player {opponent_id} has no pieces.")
        if not self._has_legal_move(opponent_id):
            return self.winner(player_id, reason=f"Player {opponent_id} cannot move.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        s0, s1 = self.game_state["score"]
        if s0 > s1: return self.winner(0, reason="Higher capture score.")
        if s1 > s0: return self.winner(1, reason="Higher capture score.")
        return self.draw(reason="Move limit reached.")

    def _render_board(self) -> str:
        bd = self.game_state["board"]
        rows = []
        for r in range(self.BOARD_N):
            rank = str(self.BOARD_N - r)
            row = [bd[r][c] if bd[r][c] else '.' for c in range(self.BOARD_N)]
            rows.append(f"{rank} | " + " ".join(row))
        rows.append("    " + " ".join(FILES))
        return "\n".join(rows)

    def _txt_to_cell(self, txt: str) -> Optional[int]:
        """Accept either numeric id or chess-style coord; return cell id or None."""
        if txt.isdigit():
            try:
                cell = int(txt)
            except ValueError:
                return None
            return cell if cell in self.cell_to_rc else None
        if re.fullmatch(r"[a-eA-E][1-5]", txt):
            r, c = coord_to_rc(txt)
            return r * self.BOARD_N + c
        return None

    def _diagonal_vertex(self, r: int, c: int) -> bool:
        """Only alternating vertices are joined by the board's diagonal lines."""
        return (r + c) % 2 == 0

    def _is_connected_step(self, fr: int, fc: int, tr: int, tc: int) -> bool:
        dr, dc = tr - fr, tc - fc
        if abs(dr) + abs(dc) == 1:
            return True
        return abs(dr) == abs(dc) == 1 and self._diagonal_vertex(fr, fc)

    def _has_capture_from(self, board, r: int, c: int, piece: str, opp: str) -> bool:
        for dr, dc in self.neighbours:
            if dr and dc and not self._diagonal_vertex(r, c):
                continue
            mr, mc = r + dr, c + dc
            nr, nc = r + 2 * dr, c + 2 * dc
            if (
                0 <= nr < self.BOARD_N
                and 0 <= nc < self.BOARD_N
                and board[mr][mc] == opp
                and board[nr][nc] == ''
            ):
                return True
        return False

    def _has_capture(self, pid: int, board=None) -> bool:
        board = self.game_state["board"] if board is None else board
        piece = 'R' if pid == 0 else 'B'
        opp = 'B' if pid == 0 else 'R'
        return any(
            board[r][c] == piece and self._has_capture_from(board, r, c, piece, opp)
            for r in range(self.BOARD_N)
            for c in range(self.BOARD_N)
        )

    def _has_legal_move(self, pid: int) -> bool:
        piece  = 'R' if pid == 0 else 'B'
        board  = self.game_state["board"]

        for (r, c), cell_id in self.rc_to_cell.items():
            if board[r][c] != piece: continue

            # forward steps
            for dr, dc in self.forward_dirs[pid]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N \
                   and board[nr][nc] == '' \
                   and self._is_connected_step(r, c, nr, nc):
                    return True

            # single captures
            for dr, dc in self.neighbours:
                if dr and dc and not self._diagonal_vertex(r, c):
                    continue
                nr, nc = r + dr * 2, c + dc * 2
                mr, mc = r + dr,      c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N \
                   and board[nr][nc] == '' \
                   and board[mr][mc] not in ('', piece):
                    return True
        return False

    def _legal_moves(self, pid: int) -> List[str]:
        """Every complete capture sequence if a capture exists, otherwise every forward step."""
        piece = 'R' if pid == 0 else 'B'
        opp = 'B' if pid == 0 else 'R'
        board = self.game_state["board"]
        squares = [(r, c) for r in range(self.BOARD_N) for c in range(self.BOARD_N) if board[r][c] == piece]
        sequences: List[List[Tuple[int, int]]] = []
        for square in squares:
            self._collect_capture_sequences(board, [square], piece, opp, sequences)
        if sequences:
            return [" ".join(rc_to_coord(r, c) for r, c in sequence) for sequence in sequences]
        steps = []
        for r, c in squares:
            for dr, dc in self.forward_dirs[pid]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N and board[nr][nc] == '' \
                   and self._is_connected_step(r, c, nr, nc):
                    steps.append(f"{rc_to_coord(r, c)} {rc_to_coord(nr, nc)}")
        return steps

    def _collect_capture_sequences(self, board, path: List[Tuple[int, int]], piece: str, opp: str, out: List[List[Tuple[int, int]]]) -> None:
        r, c = path[-1]
        extended = False
        for dr, dc in self.neighbours:
            if dr and dc and not self._diagonal_vertex(r, c):
                continue
            mr, mc, nr, nc = r + dr, c + dc, r + 2 * dr, c + 2 * dc
            if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N and board[mr][mc] == opp and board[nr][nc] == '':
                trial = [row[:] for row in board]
                trial[r][c], trial[mr][mc], trial[nr][nc] = '', '', piece
                self._collect_capture_sequences(trial, path + [(nr, nc)], piece, opp, out)
                extended = True
        if not extended and len(path) > 1:
            out.append(path)
