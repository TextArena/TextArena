import re
from typing import Dict, Tuple, Optional, Any

import textarena as ta

FILES = "abcde"
RANKS = "12345"

def coord_to_rc(coord: str) -> Tuple[int, int]:
    """'a1' → (4,0)   (row 4 is bottom rank)."""
    f, r = coord[0].lower(), coord[1]
    return len(RANKS) - int(r), FILES.index(f)

def rc_to_coord(r: int, c: int) -> str: 
    return f"{FILES[c]}{RANKS[len(RANKS) - 1 - r]}"

class AlquerqueEnv(ta.Env):
    BOARD_N = 5
    MAX_MOVES = 60
    SCORE_PER_CAPTURE = 10

    def __init__(self):
        super().__init__()
        self.cell_to_rc = {i: (i // self.BOARD_N, i % self.BOARD_N) for i in range(self.BOARD_N ** 2)}
        self.rc_to_cell = {(r, c): i for i, (r, c) in self.cell_to_rc.items()}
        self.neighbours = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if not (dr == dc == 0)]
        self.forward_dirs = {0: [(-1, 0), (-1, -1), (-1, 1)], 1: [(1, 0),  (1, -1),  (1, 1)]}
        coord_re = r"[a-eA-E][1-5]"
        self.move_re = re.compile(rf"\[\s*({coord_re}|\d+)\s+({coord_re}|\d+)\s*\]")

    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        board = [['' for _ in range(self.BOARD_N)] for _ in range(self.BOARD_N)] # Empty board then fill rows
        for cell, (r, c) in self.cell_to_rc.items():
            if r < 2:   board[r][c] = 'B'       # Black top
            elif r > 2: board[r][c] = 'R'       # Red  bottom

        self.state.reset(game_state={"board": board, "score": [0, 0], "move_count": 0}, player_prompt_function=self._prompt)
        self._observe_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        piece = 'R' if player_id == 0 else 'B'
        opp   = 'B' if player_id == 0 else 'R'
        return self.m(
            "player_prompt", "intro",
            player_id=player_id, piece=piece, opp=opp,
            score_per_capture=self.SCORE_PER_CAPTURE, max_moves=self.MAX_MOVES,
        )

    def _render_board(self) -> str:
        bd = self.state.game_state["board"]
        rows = []
        for r in range(self.BOARD_N):
            rank = str(self.BOARD_N - r)
            row = [bd[r][c] if bd[r][c] else '.' for c in range(self.BOARD_N)]
            rows.append(f"{rank} | " + " ".join(row))
        rows.append("    " + " ".join(FILES))
        return "\n".join(rows)

    def _observe_current_state(self):
        self.state.add_observation(message=self.m("board", "current_board", move_count=self.state.game_state['move_count'], board=self._render_board()), observation_type=ta.ObservationType.GAME_BOARD)

    def _txt_to_cell(self, txt: str) -> Optional[int]:
        """Accept either numeric id or chess-style coord; return cell id or None."""
        if txt.isdigit(): return int(txt) if int(txt) in self.cell_to_rc else None
        if re.fullmatch(r"[a-eA-E][1-5]", txt):
            r, c = coord_to_rc(txt)
            return r * self.BOARD_N + c
        return None

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        pid   = self.state.current_player_id
        piece = 'R' if pid == 0 else 'B'
        opp   = 'B' if pid == 0 else 'R'

        self.state.add_observation(from_id=pid, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        m = self.move_re.search(action)
        if not m: self.state.set_invalid_move(reason=self.m("invalid_move", "bad_format")); return self.state.step()

        frm = self._txt_to_cell(m.group(1))
        to  = self._txt_to_cell(m.group(2))
        if frm is None or to is None: self.state.set_invalid_move(reason=self.m("invalid_move", "unknown_square")); return self.state.step()

        board = self.state.game_state["board"]
        fr, fc = self.cell_to_rc[frm]
        tr, tc = self.cell_to_rc[to]
        dr, dc = tr - fr, tc - fc

        # Basic legality checks
        if board[fr][fc] != piece:  self.state.set_invalid_move(reason=self.m("invalid_move", "not_your_piece"));    return self.state.step()
        if board[tr][tc] != '':     self.state.set_invalid_move(reason=self.m("invalid_move", "dest_not_empty"));       return self.state.step()

        # ── Forward step
        if (dr, dc) in self.forward_dirs[pid]:
            board[tr][tc], board[fr][fc] = piece, ''
            self._after_move()
            return self.state.step()

        # ── Single capture (any direction)
        if (abs(dr), abs(dc)) in {(2, 0), (0, 2), (2, 2)}:
            mid_r, mid_c = fr + dr // 2, fc + dc // 2
            if board[mid_r][mid_c] == opp:
                board[tr][tc], board[fr][fc]  = piece, ''
                board[mid_r][mid_c]           = ''
                self.state.game_state["score"][pid] += self.SCORE_PER_CAPTURE
                self.state.add_observation(message=self.m("game_action", "captured", player_id=pid, score_per_capture=self.SCORE_PER_CAPTURE), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self._after_move()
                return self.state.step()

        self.state.set_invalid_move(reason=self.m("invalid_move", "illegal"))
        return self.state.step()

    def _after_move(self):
        gs = self.state.game_state
        gs["move_count"] += 1

        # Win / stalemate checks
        for pid in (0, 1):
            piece = 'R' if pid == 0 else 'B'
            if not any(piece in row for row in gs["board"]):    self.state.set_winner(1 - pid, reason=self.m("outcome", "no_pieces", player_id=pid));  return
            if not self._has_legal_move(pid):                   self.state.set_winner(1 - pid, reason=self.m("outcome", "cannot_move", player_id=pid));    return

        # Move-limit check
        if gs["move_count"] >= self.MAX_MOVES:
            s0, s1 = gs["score"]
            if   s0 > s1: self.state.set_winner(0, reason=self.m("outcome", "higher_score"))
            elif s1 > s0: self.state.set_winner(1, reason=self.m("outcome", "higher_score"))
            else:         self.state.set_draw(reason=self.m("outcome", "move_limit"))

        self._observe_current_state()

    def _has_legal_move(self, pid: int) -> bool:
        piece  = 'R' if pid == 0 else 'B'
        board  = self.state.game_state["board"]

        for (r, c), cell_id in self.rc_to_cell.items():
            if board[r][c] != piece: continue

            # forward steps
            for dr, dc in self.forward_dirs[pid]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N \
                   and board[nr][nc] == '':
                    return True

            # single captures
            for dr, dc in self.neighbours:
                nr, nc = r + dr * 2, c + dc * 2
                mr, mc = r + dr,      c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N \
                   and board[nr][nc] == '' \
                   and board[mr][mc] not in ('', piece):
                    return True
        return False