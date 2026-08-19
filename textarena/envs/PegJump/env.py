import re
from typing import Dict, List, Optional, Tuple, Any

import textarena as ta


class PegJumpEnv(ta.Env):
    ACTION_RE = re.compile(r"\[(\d{1,2})\s*\s*(\d{1,2})\]", re.I)
    BOARD_SIZE = 15

    _BASE_TRIPLES: List[Tuple[int, int, int]] = [
        (1, 2, 4), (1, 3, 6), (2, 4, 7), (2, 5, 9), (3, 5, 8), (3, 6, 10), (4, 5, 6), (4, 7, 11), (4, 8, 13),
        (5, 8, 12), (5, 9, 14), (6, 9, 13), (6, 10, 15), (7, 8, 9), (7, 11, 13), (8, 9, 10), (8, 12, 14),
        (9, 12, 13), (9, 13, 15), (10, 9, 8),
    ]
    def __init__(self, initial_empty: int = 1):
        super().__init__()
        if not (1 <= initial_empty <= self.BOARD_SIZE): raise ValueError("initial_empty must be 1-15")
        self.ALLOWED_MOVES: List[Tuple[int, int, int]] = self._BASE_TRIPLES + [(t, o, f) for (f, o, t) in self._BASE_TRIPLES if (t, o, f) not in self._BASE_TRIPLES]

        self.initial_empty = initial_empty

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        board = [False] + [True] * self.BOARD_SIZE
        board[self.initial_empty] = False
        self.state.reset(game_state={"board": board}, player_prompt_function=self._prompt)
        self._observe_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro")

    def _render_board(self) -> str:
        """Return a string visualising the triangle with hole numbers."""
        b = self.state.game_state["board"]
        rows: List[str] = []
        idx = 1
        for r in range(5):  # rows 0–4  (1, 2, 3, 4, 5 holes)
            tokens: List[str] = []
            for _ in range(r + 1):
                peg = b[idx]
                symbol = "●" if peg else "○"
                tokens.append(f"{idx:>3}{symbol}"   )  # two-digit index + peg/empty
                idx += 1
            # centre-align by left-padding
            indent = " " * (3 * (4 - r))
            rows.append(indent + " ".join(tokens))
        return "\n".join(rows)
    

    def _observe_state(self):
        self.state.add_observation(message=self.m("board", "current_board", count=self.state.game_state['board'].count(True), board=self._render_board()), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = self.ACTION_RE.fullmatch(action.strip())
        if not match:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format"))
            return self.state.step()
        frm, to = int(match.group(1)), int(match.group(2))
        board = self.state.game_state["board"]
        over = self._get_over(frm, to)
        if over is None or (frm, over, to) not in self.ALLOWED_MOVES or not board[frm] or not board[over] or board[to]:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "illegal_move"))
            return self.state.step()
        # Execute move
        board[frm] = False
        board[over] = False
        board[to] = True
        # Check terminal conditions
        peg_cnt = board.count(True)
        if peg_cnt == 1:            self.state.set_outcome(reward=1.0, reason=self.m("outcome", "win"))
        elif not self._has_move():  self.state.set_outcome(reward=self._get_percentage_completion(), reason=self.m("outcome", "no_moves"))
        else:                       self._observe_state()
        return self.state.step()

    def _get_over(self, frm: int, to: int) -> Optional[int]:
        """Return the hole *over* which `frm` jumps to reach `to`, or None."""
        for (f, o, t) in self.ALLOWED_MOVES:
            if f == frm and t == to: return o
        return None

    def _has_move(self) -> bool:
        board = self.state.game_state["board"]
        for f, o, t in self.ALLOWED_MOVES:
            if board[f] and board[o] and not board[t]: return True
        return False

    def _get_percentage_completion(self) -> float:
        return 1 - (self.state.game_state["board"].count(True) - 1) / 14  # 14 jumps max → 1 peg