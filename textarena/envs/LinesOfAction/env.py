import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Tuple, Union

import textarena as ta


class LinesOfActionEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    BOARD_N = 8
    FILES = "abcdefgh"
    RANKS = "12345678"
    action_pattern = r"(?i)^\s*\[?\s*(?:(pass)|([a-h][1-8])([a-h][1-8]))\s*\]?\s*$"

    @classmethod
    def coord_to_rc(cls, coord: str) -> Tuple[int, int]:
        f, r = coord[0].lower(), coord[1]
        return len(cls.RANKS) - int(r), cls.FILES.index(f)

    @classmethod
    def rc_to_coord(cls, r: int, c: int) -> str:
        return f"{cls.FILES[c]}{cls.RANKS[len(cls.RANKS) - 1 - r]}"

    def setup(self) -> Dict[str, Any]:
        board = self._initial_board()
        rep_counter = defaultdict(int)
        rep_counter[self._hash_position(board, 0)] += 1  # record initial position
        return {
            "board": board,
            "halfmove_clock": 0,
            "rep_counter": rep_counter,
            "valid_moves": self._legal_moves_on_board(board, 0),
        }

    def prompt(self, player_id: int) -> str:
        side  = 'O' if player_id == 0 else 'X'
        other = 'X' if side == 'O' else 'O'
        return (
            f"You are Player {player_id} in game of LinesOfAction.\nYour pieces are '{side}', opponent pieces are '{other}'.\n"
            "Move format: `b1b3` (from-coord to-coord). A legal move travels horizontally, vertically, or diagonally a number of squares equal to the total pieces (any colour) in that line. "
            "You may jump over your own pieces, but not opponent pieces; landing on an opponent captures it.  Win when all your pieces are 8-neighbour connected."
        )

    def render(self, player_id: int) -> str:
        return f"Board:\n\n{self._render_board()}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        side, enemy = ('O', 'X') if player_id == 0 else ('X', 'O')
        board = self.game_state["board"]

        pass_token, frm_coord, to_coord = move.groups()
        if pass_token is not None:
            if self._legal_moves(player_id):
                return self.invalid("Pass is only legal when no move is available.")
            self.game_state["halfmove_clock"] += 1
            next_hash = self._hash_position(board, 1 - player_id)
            self.game_state["rep_counter"][next_hash] += 1
            self.game_state["valid_moves"] = self._legal_moves(1 - player_id) or ["pass"]
            self.broadcast(f"Player {player_id} passed.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            if self.game_state["halfmove_clock"] >= 60:
                self.game_state["valid_moves"] = []
                return self.draw(reason="60 moves without capture.")
            if self.game_state["rep_counter"][next_hash] >= 3:
                self.game_state["valid_moves"] = []
                return self.draw(reason="Position repeated three times.")
            return None

        fr, fc = self.coord_to_rc(frm_coord)
        tr, tc = self.coord_to_rc(to_coord)

        # Origin piece present?
        if board[fr][fc] != side:
            return self.invalid(f"No {side} piece on {frm_coord}.")

        # Direction & distance checks
        dr, dc = tr - fr, tc - fc
        if dr == dc == 0:
            return self.invalid("Source and destination identical.")

        # Must be straight or diagonal
        if not (dr == 0 or dc == 0 or abs(dr) == abs(dc)):
            return self.invalid("Move must be straight or diagonal.")

        # Distance must equal pieces in that line
        step_r, step_c = (dr > 0) - (dr < 0), (dc > 0) - (dc < 0)
        distance = max(abs(dr), abs(dc))
        if distance != self._count_pieces_on_line(fr, fc, step_r, step_c):
            return self.invalid("Must move distance equal to pieces in line.")

        # Path blocking (can't leap enemy)
        r, c = fr + step_r, fc + step_c
        while (r, c) != (tr, tc):
            if board[r][c] == enemy:
                return self.invalid("Enemy piece blocks the path.")
            r += step_r
            c += step_c

        # Can't land on own piece
        if board[tr][tc] == side:
            return self.invalid("Destination occupied by own piece.")

        # Execute move
        captured = board[tr][tc] == enemy
        board[fr][fc] = ''
        board[tr][tc] = side

        self.game_state["halfmove_clock"] = 0 if captured else self.game_state["halfmove_clock"] + 1
        next_hash = self._hash_position(board, 1 - player_id)
        self.game_state["rep_counter"][next_hash] += 1
        msg = f"Player {player_id} moved {frm_coord} -> {to_coord}"
        if captured: msg += " capturing an enemy."
        self.broadcast(msg, ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # Win/Draw checks
        if not any(enemy in row for row in board):
            self.game_state["valid_moves"] = []
            return self.winner(player_id, reason="All opposing pieces captured.")
        if self._connected(side):
            self.game_state["valid_moves"] = []
            return self.winner(player_id, reason="All pieces connected.")
        if self._connected(enemy):
            self.game_state["valid_moves"] = []
            return self.winner(1 - player_id, reason="All pieces connected.")
        if self.game_state["halfmove_clock"] >= 60:
            self.game_state["valid_moves"] = []
            return self.draw(reason="60 moves without capture.")
        if self.game_state["rep_counter"][next_hash] >= 3:
            self.game_state["valid_moves"] = []
            return self.draw(reason="Position repeated three times.")
        self.game_state["valid_moves"] = self._legal_moves(1 - player_id) or ["pass"]
        return None

    def _initial_board(self) -> List[List[str]]:
        bd = [['' for _ in range(self.BOARD_N)] for _ in range(self.BOARD_N)]
        for i in range(1, self.BOARD_N - 1):
            bd[0][i] = 'O' # top row
            bd[self.BOARD_N-1][i] = 'O' # bottom row
            bd[i][0] = 'X' # left column
            bd[i][self.BOARD_N-1] = 'X' # right column
        return bd

    def _render_board(self) -> str:
        hline = "  +" + "+".join(["---"] * self.BOARD_N) + "+"        # row separator
        rows: List[str] = []
        rows.append("    " + "   ".join(list(self.FILES))) # top file letters
        for r in range(self.BOARD_N):
            rank_lbl = list(reversed(self.RANKS))[r]
            rows.append(hline) # horizontal line
            cells = [] # piece row
            for c in range(self.BOARD_N):
                token = self.game_state["board"][r][c] if self.game_state["board"][r][c] else " " # blank if empty
                cells.append(f" {token} ")
            rows.append(f"{rank_lbl} |" + "|".join(cells) + f"| {rank_lbl}")
        # bottom border + bottom file letters
        rows.append(hline)
        rows.append("    " + "   ".join(list(self.FILES)))
        return "\n".join(rows)

    def _count_pieces_on_line(self, r: int, c: int, dr: int, dc: int, board=None) -> int:
        bd, N = self.game_state["board"] if board is None else board, self.BOARD_N
        cnt = 1
        # forward
        nr, nc = r + dr, c + dc
        while 0 <= nr < N and 0 <= nc < N:
            if bd[nr][nc]: cnt += 1
            nr += dr; nc += dc
        # backward
        nr, nc = r - dr, c - dc
        while 0 <= nr < N and 0 <= nc < N:
            if bd[nr][nc]: cnt += 1
            nr -= dr; nc -= dc
        return cnt

    def _connected(self, side: str) -> bool:
        bd, N = self.game_state["board"], self.BOARD_N
        pieces = [(r, c) for r in range(N) for c in range(N) if bd[r][c] == side]
        if not pieces: return False
        q, seen = deque([pieces[0]]), {pieces[0]}
        dirs = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
        while q:
            r, c = q.popleft()
            for dr, dc in dirs:
                nr, nc = r+dr, c+dc
                if 0 <= nr < N and 0 <= nc < N and bd[nr][nc] == side and (nr,nc) not in seen:
                    seen.add((nr,nc)); q.append((nr,nc))
        return len(seen) == len(pieces)

    def _legal_moves(self, player_id: int):
        return self._legal_moves_on_board(self.game_state["board"], player_id)

    def _legal_moves_on_board(self, board, player_id: int):
        side, enemy = ('O', 'X') if player_id == 0 else ('X', 'O')
        moves = []
        for fr in range(self.BOARD_N):
            for fc in range(self.BOARD_N):
                if board[fr][fc] != side:
                    continue
                for step_r, step_c in (
                    (-1, -1), (-1, 0), (-1, 1), (0, -1),
                    (0, 1), (1, -1), (1, 0), (1, 1),
                ):
                    distance = self._count_pieces_on_line(fr, fc, step_r, step_c, board)
                    tr, tc = fr + step_r * distance, fc + step_c * distance
                    if not (0 <= tr < self.BOARD_N and 0 <= tc < self.BOARD_N):
                        continue
                    if board[tr][tc] == side:
                        continue
                    blocked = False
                    r, c = fr + step_r, fc + step_c
                    while (r, c) != (tr, tc):
                        if board[r][c] == enemy:
                            blocked = True
                            break
                        r += step_r
                        c += step_c
                    if not blocked:
                        moves.append(f"{self.rc_to_coord(fr, fc)}{self.rc_to_coord(tr, tc)}")
        return moves

    # repetition helpers
    @staticmethod
    def _hash_position(board: List[List[str]], side_to_move: int) -> str:
        flat = ''.join(cell or '.' for row in board for cell in row)
        return flat + str(side_to_move)

    def _pos_hash(self) -> str:
        return self._hash_position(self.game_state["board"], self.state.current_player_id)
