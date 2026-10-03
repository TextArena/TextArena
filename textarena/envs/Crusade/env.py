import re
from typing import Dict, Tuple, Optional, Any, List

import textarena as ta

FILES = "abcdefgh"
RANKS = "12345678"

def coord_to_rc(coord: str) -> Tuple[int, int]:
    f, r = coord[0].lower(), coord[1]
    return len(RANKS) - int(r), FILES.index(f)

def rc_to_coord(r: int, c: int) -> str:
    return f"{FILES[c]}{RANKS[len(RANKS) - 1 - r]}"

class CrusadeEnv(ta.Env):
    BOARD_N = 8
    MAX_MOVES = 40
    SCORE_PER_CAPTURE = 1

    def __init__(self):
        super().__init__()
        self.CELL_TO_RC = {i: (i // self.BOARD_N, i % self.BOARD_N) for i in range(self.BOARD_N ** 2)}
        self.RC_TO_CELL = {(r, c): i for i, (r, c) in self.CELL_TO_RC.items()}
        self.KNIGHT_DIRS = [(2, 1), (2, -1), (-2, 1), (-2, -1), (1, 2), (1, -2), (-1, 2), (-1, -2)]
        coord_re  = r"[a-hA-H][1-8]"
        self.MOVE_RE = re.compile(rf"\[\s*({coord_re}|\d+)\s+({coord_re}|\d+)\s*\]")

    def _legal_moves_for_player(self, pid: int) -> List[str]:
        piece  = 'W' if pid == 0 else 'B'
        moves  = []
        for (r, c), cell_id in self.RC_TO_CELL.items():
            if self.state.game_state["board"][r][c] != piece: continue
            src = rc_to_coord(r, c)
            for dr, dc in self.KNIGHT_DIRS:
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.BOARD_N and 0 <= nc < self.BOARD_N:
                    if self.state.game_state["board"][nr][nc] != piece: # empty or opponent
                        dst = rc_to_coord(nr, nc)
                        moves.append(f"[{src} {dst}]")
        return moves

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)

        board = [['' for _ in range(self.BOARD_N)] for _ in range(self.BOARD_N)]
        for cell, (r, c) in self.CELL_TO_RC.items():
            if r < 2:   board[r][c] = 'B'
            elif r > 5: board[r][c] = 'W'

        self.state.reset(game_state={"board": board, "score": [0, 0], "move_count": 0}, player_prompt_function=self._prompt)
        self._observe_current_state(self.state.current_player_id)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        piece = 'W' if player_id == 0 else 'B'
        opp = 'B' if player_id == 0 else 'W'
        return self.m("player_prompt", "intro", player_id=player_id, piece=piece, opp=opp, score_per_capture=self.SCORE_PER_CAPTURE, max_moves=self.MAX_MOVES)

    def _render_board(self) -> str:
        rows = []
        for r in range(self.BOARD_N):
            rank = str(self.BOARD_N - r)
            row = [self.state.game_state["board"][r][c] if self.state.game_state["board"][r][c] else '.' for c in range(self.BOARD_N)]
            rows.append(f"{rank} | " + " ".join(row))
        rows.append("    " + " ".join(FILES))
        return "\n".join(rows)

    def _observe_current_state(self, player_id: int):
        self.state.add_observation(
            to_id=player_id, 
            message=self.m("board", "current_board", move_count=self.state.game_state['move_count'], board=self._render_board(), moves=", ".join(self._legal_moves_for_player(player_id))), 
            observation_type=ta.ObservationType.GAME_BOARD
        )

    def _txt_to_cell(self, txt: str) -> Optional[int]:
        if txt.isdigit(): return int(txt) if int(txt) in self.CELL_TO_RC else None
        if re.fullmatch(r"[a-hA-H][1-8]", txt):
            r, c = coord_to_rc(txt)
            return r * self.BOARD_N + c
        return None

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        piece = 'W' if self.state.current_player_id == 0 else 'B'

        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        m = self.MOVE_RE.search(action)
        if not m: self.state.set_invalid_move(reason=self.m("invalid_move", "bad_format")); return self.state.step()

        frm = self._txt_to_cell(m.group(1))
        to  = self._txt_to_cell(m.group(2))
        if frm is None or to is None: self.state.set_invalid_move(reason=self.m("invalid_move", "unknown_square")); return self.state.step()

        fr, fc = self.CELL_TO_RC[frm]
        tr, tc = self.CELL_TO_RC[to]
        dr, dc = tr - fr, tc - fc

        if self.state.game_state["board"][fr][fc] != piece: self.state.set_invalid_move(reason=self.m("invalid_move", "not_your_piece"));    return self.state.step()
        if self.state.game_state["board"][tr][tc] == piece: self.state.set_invalid_move(reason=self.m("invalid_move", "own_piece"));    return self.state.step()
        if (dr, dc) not in self.KNIGHT_DIRS:                self.state.set_invalid_move(reason=self.m("invalid_move", "not_knight"));           return self.state.step()

        # Handle capture
        message = self.m("game_action", "moved", player_id=self.state.current_player_id, frm=m.group(1), to=m.group(2))
        if self.state.game_state["board"][tr][tc] == ('B' if self.state.current_player_id == 0 else 'W'):
            self.state.game_state["score"][self.state.current_player_id] += self.SCORE_PER_CAPTURE
            message = self.m("game_action", "capture", observation=message, score_per_capture=self.SCORE_PER_CAPTURE)
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.state.game_state["board"][tr][tc], self.state.game_state["board"][fr][fc] = piece, ''
        self._after_move()
        return self.state.step()

    def _after_move(self):
        self.state.game_state["move_count"] += 1

        for pid in (0, 1):
            piece = 'W' if pid == 0 else 'B'
            if not any(piece in row for row in self.state.game_state["board"]): self.state.set_winner(1 - pid, reason=self.m("outcome", "no_pieces", player_id=pid));  return
            if not self._legal_moves_for_player(pid):                           self.state.set_winner(1 - pid, reason=self.m("outcome", "cannot_move", player_id=pid));    return

        if self.state.game_state["move_count"] >= self.MAX_MOVES:
            s0, s1 = self.state.game_state["score"]
            if   s0 > s1: self.state.set_winner(0, reason=self.m("outcome", "higher_score"))
            elif s1 > s0: self.state.set_winner(1, reason=self.m("outcome", "higher_score"))
            else:         self.state.set_draw(reason=self.m("outcome", "move_limit"))

        self._observe_current_state(1-self.state.current_player_id)