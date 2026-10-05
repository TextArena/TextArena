import re
from typing import Any, Dict, List, Union

import textarena as ta

GRID = 5
CONNECT = 4  # length of the line needed to win; edges do not wrap
NUM_CELLS = GRID * GRID
DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))  # horizontal, vertical, both diagonals
SYMBOLS = {0: "\u25a0", 1: "\u25b2"}  # Player 0 -> ■, Player 1 -> ▲


def create_board_str(board: List[List[str]]) -> str:
    """Empty cells show their index; filled cells show the mark."""
    rows = ["|".join(f" {(board[r][c] or str(r * GRID + c)):>2} " for c in range(GRID)) for r in range(GRID)]
    separator = "\n" + "+".join(["----"] * GRID) + "\n"
    return separator.join(rows)


class JoJoJoinEnv(ta.GameEnv):
    """Place marks on a 5x5 board; four in a row (any direction) wins."""
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^([0-9]+)$"
    action_format = f"a cell number from 0 to {NUM_CELLS - 1}, for example '12'"

    def setup(self) -> Dict[str, Any]:
        return {"board": [["" for _ in range(GRID)] for _ in range(GRID)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in JoJoJoin, played on a 5x5 board with cells numbered 0-24.\n"
            "On your turn, place your mark on any empty cell by replying with its number, e.g. '12'.\n"
            "YOU WIN by getting FOUR of your marks in a row \u2014 four consecutive cells horizontally, vertically, or diagonally.\n"
            f"As Player {player_id} you are '{SYMBOLS[player_id]}'; your opponent is '{SYMBOLS[1 - player_id]}'."
        )

    def render(self, player_id: int) -> str:
        board = self.game_state["board"]
        moves = [f"'{r * GRID + c}'" for r in range(GRID) for c in range(GRID) if board[r][c] == ""]
        return f"Current Board:\n\n{create_board_str(board)}\n\nAvailable Moves: {', '.join(moves)}"

    def get_board_str(self) -> str:
        return create_board_str(self.game_state["board"])

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        digits = move.group(1)
        significant = digits.lstrip("0") or "0"
        if len(significant) > 2 or int(significant) >= NUM_CELLS:  # bounded before int() so huge inputs stay cheap
            shown = digits if len(digits) <= 6 else f"{digits[:6]}..."
            return self.invalid(f"{shown} is not a valid cell. Must be between 0 and {NUM_CELLS - 1}.")
        cell = int(significant)
        row, col = divmod(cell, GRID)
        board = self.game_state["board"]
        if board[row][col]:
            return self.invalid(f"Cell {cell} is already occupied.")

        symbol = SYMBOLS[player_id]
        board[row][col] = symbol
        self.broadcast(f"Player {player_id} placed their mark ({symbol}) in cell {cell}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if self._completes_line(row, col):
            return self.winner(player_id, reason=f"Player {player_id} has won!")
        if all(mark for line in board for mark in line):
            return self.draw(reason="The game is a draw!")
        return None

    def _completes_line(self, row: int, col: int) -> bool:
        """True if the mark just placed at (row, col) is part of CONNECT or more in a line."""
        board = self.game_state["board"]
        symbol = board[row][col]
        for dr, dc in DIRECTIONS:
            count = 1
            for sign in (1, -1):
                r, c = row + sign * dr, col + sign * dc
                while 0 <= r < GRID and 0 <= c < GRID and board[r][c] == symbol:
                    count += 1
                    r, c = r + sign * dr, c + sign * dc
            if count >= CONNECT:
                return True
        return False
