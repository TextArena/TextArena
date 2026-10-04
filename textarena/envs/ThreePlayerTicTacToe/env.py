import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.ThreePlayerTicTacToe.renderer import create_board_str


class ThreePlayerTicTacToeEnv(ta.GameEnv):
    min_players = 3
    max_players = 3
    mdp_includes_actions = False
    action_pattern = r"^([0-9]{1,2})$"

    def __init__(self):
        self.board_size = 5
        self.cell_mapping = {i * self.board_size + j: (i, j) for i in range(self.board_size) for j in range(self.board_size)}
        self.symbols = {0: 'A', 1: 'B', 2: 'C'}

    @property
    def action_format(self) -> str:
        return f"a cell number from 0 to {self.board_size ** 2 - 1}, for example '4'"

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        return {"board": [['' for _ in range(self.board_size)] for _ in range(self.board_size)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Three-Player Tic Tac Toe.\nYour symbol is '{self.symbols[player_id]}'.\n"
            "You take turns placing your symbol on a 5x5 board to form a line of four.\nLines can be horizontal, vertical, or diagonal.\n"
            "Reply with the number of the cell you want to mark, e.g. '4' to mark cell 4."
        )

    def _render_board(self) -> str:
        cell_width = max(len(str(self.board_size * self.board_size - 1)), 2)  # ensures symbols like 'A', 'B', 'C' are well-centered
        def cell_str(r: int, c: int) -> str: return self.game_state["board"][r][c] if self.game_state["board"][r][c] != '' else str(r * self.board_size + c)
        def build_hline() -> str: return "+" + "+".join("-" * (cell_width + 2) for _ in range(self.board_size)) + "+"
        lines = [build_hline()]
        for r in range(self.board_size):
            row_cells = [f" {cell_str(r, c):^{cell_width}} " for c in range(self.board_size)]
            lines.append("|" + "|".join(row_cells) + "|")
            lines.append(build_hline())
        return "\n".join(lines)

    def render(self, player_id: int) -> str:
        available_moves = []
        for i in range(self.board_size * self.board_size):
            r, c = self.cell_mapping[i]
            if self.game_state["board"][r][c] == '':
                available_moves.append(str(i))
        return f"Current Board:\n\n{self._render_board()}\n\nAvailable Moves: " + ", ".join(available_moves)

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        cell = int(move.group(1))
        if cell not in self.cell_mapping:
            return self.invalid(f"Invalid cell number: {cell}. Must be between 0 and {self.board_size ** 2 - 1}.")
        row, col = self.cell_mapping[cell]
        if self.game_state["board"][row][col] != '':
            return self.invalid(f"Cell {cell} is already occupied.")
        self.game_state["board"][row][col] = self.symbols[player_id]
        self.broadcast(f"Player {player_id} places their symbol ({self.symbols[player_id]}) in field ({row}, {col}).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if self._check_winner(self.symbols[player_id]):
            return self.winner(player_id, reason=f"Player {player_id} ({self.symbols[player_id]}) wins!")
        if all(cell != '' for row in self.game_state["board"] for cell in row):
            return self.draw(reason="The game is a draw!")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        return self.loser(player_id, reason=f"Player {player_id} made an invalid move")

    def _check_winner(self, symbol: str) -> bool:
        win_length = 4
        board = self.game_state["board"]
        # Horizontal & Vertical
        for r in range(self.board_size):
            for c in range(self.board_size - win_length + 1):
                if all(board[r][c + i] == symbol for i in range(win_length)): return True
        for c in range(self.board_size):
            for r in range(self.board_size - win_length + 1):
                if all(board[r + i][c] == symbol for i in range(win_length)): return True
        # Diagonal \ and /
        for r in range(self.board_size - win_length + 1):
            for c in range(self.board_size - win_length + 1):
                if all(board[r + i][c + i] == symbol for i in range(win_length)): return True
                if all(board[r + i][c + win_length - 1 - i] == symbol for i in range(win_length)): return True
        return False
