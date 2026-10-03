import re
from collections import deque
from typing import Optional, Dict, Tuple, List, Any

import textarena as ta
from textarena.envs.SimpleTak.renderer import create_board_str

class SimpleTakEnv(ta.Env):
    def __init__(self, board_size: int = 5):
        """
        Args:
            board_size (int): The size of the NxN board (default 5).
        """
        super().__init__()
        self.board_size = board_size
        self.cell_mapping = {i: (i // board_size, i % board_size) for i in range(board_size * board_size)}

    def get_board_str(self): return create_board_str(board=self.state.game_state["board"], board_size=self.board_size)
    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(self.board_size)] for _ in range(self.board_size)]}, player_prompt_function=self._prompt)
        self._observe_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        player_stone = 'O' if player_id == 0 else 'X'
        opponent_stone = 'O' if player_id == 1 else 'X'
        return self.m("player_prompt", "intro", player_id=player_id, player_stone=player_stone, opponent_stone=opponent_stone)

    def _observe_current_state(self) -> None:
        available_moves = []
        for i in range(self.board_size * self.board_size):
            r, c = self.cell_mapping[i]
            if self.state.game_state["board"][r][c] == '': 
                available_moves.append(f"[{i}]")
        message = self.m("board", "current_state", rendered_board=self._render_board(), available_moves=", ".join(available_moves))
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_BOARD)

    def _render_board(self) -> str:
        max_cell_num = self.board_size * self.board_size - 1
        digit_count = len(str(max_cell_num))
        cell_width = max(digit_count, 2)  # at least 2 for occupant symbols
        def cell_str(r: int, c: int) -> str:
            if self.state.game_state["board"][r][c] == '': return str(r * self.board_size + c) # If empty, show cell number
            else: return self.state.game_state["board"][r][c] # Occupied by 'O' or 'X'
        def build_hline() -> str:
            line_parts = []
            for _ in range(self.board_size): line_parts.append("-" * (cell_width + 2))  # +2 for spacing around content
            return "+" + "+".join(line_parts) + "+"
        lines = []
        lines.append(build_hline())
        for r in range(self.board_size):
            row_cells = []
            for c in range(self.board_size):
                text = cell_str(r, c)
                text_centered = f" {text:^{cell_width}} "
                row_cells.append(text_centered)
            row_line = "|" + "|".join(row_cells) + "|"
            lines.append(row_line)
            lines.append(build_hline())
        return "\n".join(lines)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        symbol = 'O' if self.state.current_player_id == 0 else 'X'
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        # match = re.compile(r"\[\s*(\d+)\s*\]").search(action) # Regex to parse moves like [12]
        matches = list(re.compile(r"\[\s*(\d+)\s*\]").finditer(action))
        match = matches[-1] if matches else None
        if match is None:
            self.state.set_invalid_move(reason=self.m("invalid_move", "invalid_move_format"))
        else:
            cell_num = int(match.group(1))
            if cell_num not in self.cell_mapping: # Check if cell_num in valid range
                self.state.set_invalid_move(reason=self.m("invalid_move", "cell_out_of_range", cell_num=cell_num, max_board_num=self.board_size**2 - 1))
            else:
                row, col = self.cell_mapping[cell_num]
                board = self.state.game_state["board"]
                if board[row][col] == '':
                    board[row][col] = symbol # Place the stone
                    self.state.add_observation(message=self.m("action", "placement", current_player_id=self.state.current_player_id, symbol=symbol, cell_num=cell_num), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self._check_win(symbol): # Check for a winning path
                        self.state.set_winner(player_id=self.state.current_player_id, reason=self.m("outcome", "winner", current_player_id=self.state.current_player_id, symbol=symbol))
                    else:
                        if all(board[r][c] != '' for r in range(self.board_size) for c in range(self.board_size)): # If board is fully occupied and no winner => draw
                            self.state.set_draw(reason=self.m("outcome", "draw"))
                else:
                    self.state.set_invalid_move(reason=self.m("invalid_move", "cell_already_occupied", cell_num=cell_num))
        self._observe_current_state()
        return self.state.step()

    def _check_win(self, symbol: str) -> bool:
        n   = self.board_size
        bd  = self.state.game_state["board"]
        dirs = [(0,1), (1,0), (0,-1), (-1,0)]           # 4-neighbour connectivity

        def bfs(starts: List[Tuple[int,int]], target_edge) -> bool:
            """ Generic flood-fill. `target_edge` is a lambda that tests whether (r,c) lies on the opposite edge we’re trying to reach. """
            q = deque(starts)
            vis = set(starts)
            while q:
                r, c = q.popleft()
                if target_edge(r, c):
                    return True
                for dr, dc in dirs:
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < n and 0 <= nc < n and (nr, nc) not in vis and bd[nr][nc] == symbol:
                        vis.add((nr, nc))
                        q.append((nr, nc))
            return False

        # top → bottom
        top_starts = [(0, c) for c in range(n) if bd[0][c] == symbol]
        if bfs(top_starts, lambda r, _c: r == n-1):
            return True

        # left → right
        left_starts = [(r, 0) for r in range(n) if bd[r][0] == symbol]
        if bfs(left_starts, lambda _r, c: c == n-1):
            return True

        return False