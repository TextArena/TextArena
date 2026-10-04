import re
from collections import deque
from typing import Any, Dict, List, Tuple, Union

import textarena as ta
from textarena.envs.SimpleTak.renderer import create_board_str


class SimpleTakEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^(\d+)$"

    board_size = ta.Param(5, "The side length of the board.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        size = self.board_size
        self.cell_mapping = {i: (i // size, i % size) for i in range(size * size)}

    @property
    def action_format(self) -> str:
        last = self.board_size ** 2 - 1
        return f"the number of an empty cell from 0 to {last}, for example '{min(2, last)}'"

    def setup(self) -> Dict[str, Any]:
        return {"board": [['' for _ in range(self.board_size)] for _ in range(self.board_size)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in SimpleTak on a {self.board_size}x{self.board_size} board. Player 0 moves first.\n"
            f"On the board, your stones appear as '{'O' if player_id == 0 else 'X'}' and "
            f"your opponent's stones appear as '{'O' if player_id == 1 else 'X'}'.\n\n"
            f"On your turn, choose one empty cell by its number (0 to {self.board_size ** 2 - 1}, counted left to right and top to bottom) "
            "and place your stone there. Empty cells show their number on the board.\n"
            "For example, '2' places your stone in cell 2.\n\n"
            "Your objective is to form a continuous path of your stones that connects two opposite edges of the board "
            "(top-to-bottom or left-to-right). Stones connect only horizontally or vertically, not diagonally.\n"
            "The first player to complete such a path wins. If the board fills up without one, the game is a draw."
        )

    def render(self, player_id: int) -> str:
        available_moves = []
        for i in range(self.board_size * self.board_size):
            r, c = self.cell_mapping[i]
            if self.game_state["board"][r][c] == '':
                available_moves.append(f"'{i}'")
        return f"Current Board:\n\n{self._render_board()}\nAvailable Moves: " + ", ".join(available_moves)

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        try:
            cell_num = int(move.group(1))
        except ValueError:
            return self.invalid("Cell number is too large.")
        if cell_num not in self.cell_mapping:
            return self.invalid(f"Invalid cell number {cell_num}. Must be between 0 and {self.board_size**2 - 1}.")
        row, col = self.cell_mapping[cell_num]
        board = self.game_state["board"]
        if board[row][col] != '':
            return self.invalid(f"Cell {cell_num} is already occupied. Choose an empty cell.")

        symbol = 'O' if player_id == 0 else 'X'
        board[row][col] = symbol
        self.broadcast(f"Player {player_id} placed their symbol ({symbol}) in cell {cell_num}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if self._check_win(symbol):
            return self.winner(player_id, reason=f"Player {player_id} ('{symbol}') connected two opposite edges!")
        if all(board[r][c] != '' for r in range(self.board_size) for c in range(self.board_size)):
            return self.draw(reason="The board is full. It's a draw!")
        return None

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"], board_size=self.board_size)

    def _render_board(self) -> str:
        max_cell_num = self.board_size * self.board_size - 1
        digit_count = len(str(max_cell_num))
        cell_width = max(digit_count, 2)  # at least 2 for occupant symbols
        def cell_str(r: int, c: int) -> str:
            if self.game_state["board"][r][c] == '': return str(r * self.board_size + c) # If empty, show cell number
            else: return self.game_state["board"][r][c] # Occupied by 'O' or 'X'
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

    def _check_win(self, symbol: str) -> bool:
        n   = self.board_size
        bd  = self.game_state["board"]
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
