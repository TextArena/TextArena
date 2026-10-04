import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.ConnectFour.renderer import create_board_str


class ConnectFourEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"(?i)^(?:col\s*)?([0-9]+)$"

    def __init__(self, is_open: bool = True, num_rows: int = 6, num_cols: int = 7):
        """
        Args:
            is_open (bool): If True, the game state is visible to the players.
            num_rows (int): Number of rows in the game board.
            num_cols (int): Number of columns in the game board.
        """
        if not isinstance(is_open, bool):
            raise ValueError("is_open must be a boolean")
        if not isinstance(num_rows, int) or isinstance(num_rows, bool) or num_rows < 1:
            raise ValueError("num_rows must be a positive integer")
        if not isinstance(num_cols, int) or isinstance(num_cols, bool) or num_cols < 1:
            raise ValueError("num_cols must be a positive integer")
        self.is_open = is_open
        self.num_rows = num_rows
        self.num_cols = num_cols

    @property
    def action_format(self) -> str:
        last = self.num_cols - 1
        return f"a column number from 0 to {last}, for example '{min(4, last)}' or 'col {min(1, last)}'"

    def setup(self) -> Dict[str, Any]:
        return {
            "board": [["." for _ in range(self.num_cols)] for _ in range(self.num_rows)],
            "move_history": [],
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Connect Four.\nYour disc symbol: {'X' if player_id == 0 else 'O'}.\n"
            f"The game board has {self.num_rows} rows and {self.num_cols} columns.\n"
            f"Players take turns dropping their disc into one of the columns (0 to {self.num_cols - 1}).\n"
            "The first to connect (their own) four discs vertically, horizontally, or diagonally wins.\n"
            "On your turn, reply with the column number you want to drop your disc into.\nFor example: '4' or 'col 1'."
        )

    def on_start(self):
        if not self.is_open:
            self.broadcast("The game board is not visible to players.", ta.ObservationType.GAME_BOARD)

    def render(self, player_id: int) -> Optional[str]:
        if not self.is_open:
            return None
        open_columns = [str(c) for c in range(self.num_cols) if self.game_state["board"][0][c] == "."]
        return f"Board state:\n{self._render_board()}\nAvailable columns: {', '.join(open_columns) or 'none'}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        try:
            col = int(move.group(1))
        except ValueError:
            return self.invalid(f"Player {player_id}, Invalid action. Column number is too large.")
        if not (0 <= col < self.num_cols):
            return self.invalid(f"Player {player_id}, Invalid action. Column {col} is out of bounds.")
        board = self.game_state["board"]
        if board[0][col] != ".":
            return self.invalid(f"Player {player_id}, Invalid action. Column {col} is full.")

        row = self._get_available_row(col)
        player_symbol = "X" if player_id == 0 else "O"
        self.broadcast(f"Player {player_id} dropped their disk ({player_symbol}) into column {col}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        board[row][col] = player_symbol
        self.game_state["move_history"].append((player_id, col))
        if self._check_win(row, col):
            return self.winner(player_id, reason=f"Player {player_id} wins by connecting four!")
        if self._check_draw():
            return self.draw(reason="Game ended in a draw.")
        return None

    def get_board_str(self):
        if not self.is_open:
            moves = ", ".join(f"P{pid}:col {col}" for pid, col in self.game_state["move_history"])
            return "Hidden Connect Four board.\nPublic move history: " + (moves or "(no moves)")
        return create_board_str(board=self.game_state["board"])

    def _render_board(self) -> str:
        return create_board_str(board=self.game_state["board"])

    def _get_available_row(self, col: int) -> int:
        for r in range(self.num_rows - 1, -1, -1):
            if self.game_state["board"][r][col] == ".":
                return r
        raise Exception("The column should be validated before calling the _get_available_row function.")

    def _check_win(self, row: int, col: int) -> bool:
        board = self.game_state["board"]
        for direction in [((0, 1), (0, -1)), ((1, 0), (-1, 0)), ((1, 1), (-1, -1)), ((1, -1), (-1, 1))]:
            total = 1  # Count the disc just placed
            for delta_row, delta_col in direction:
                total += self._check_direction(board, row, col, delta_row, delta_col, board[row][col])
            if total >= 4: return True
        return False

    def _check_direction(self, board, row, col, delta_row, delta_col, disc) -> int:
        count = 0
        r, c = row + delta_row, col + delta_col
        while 0 <= r < self.num_rows and 0 <= c < self.num_cols and board[r][c] == disc:
            count += 1
            r += delta_row
            c += delta_col
        return count

    def _check_draw(self) -> bool:
        return all(self.game_state["board"][0][c] != "." for c in range(self.num_cols))
