import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.WildTicTacToe.renderer import create_board_str


def _parse_cell(text: str) -> Optional[int]:
    """Parse a 0-8 cell without converting an unbounded integer."""
    normalized = text.lstrip("0") or "0"
    if len(normalized) > 1 or normalized > "8":
        return None
    return int(normalized)


class WildTicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"(?i)^(?P<mark>[XO])\s+(?P<cell>[0-9]+)$"
    action_format = "the mark X or O followed by a cell number from 0 to 8, for example 'X 4'"

    def __init__(self):
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def setup(self) -> Dict[str, Any]:
        return {"board": [['' for _ in range(3)] for _ in range(3)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Wild Tic Tac Toe.\nOn your turn, you can place either an 'X' or an 'O' in an empty square.\n"
            "You win by aligning three of the same mark (X or O) in a row.\nYou can win with either symbol.\n"
            "Choose your move using the format 'X 4' to place X in the center.\n"
        )

    def render(self, player_id: int) -> str:
        board = self.game_state["board"]
        available_moves = [f"'{mark} {str(r * 3 + c)}'" for r in range(3) for c in range(3) if board[r][c] == '' for mark in ['X', 'O']]
        return f"Current Board:\n\n{self._render_board()}\n\nAvailable Moves: {', '.join(available_moves)}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        mark = move.group("mark").upper()
        cell = _parse_cell(move.group("cell"))
        if cell is None:
            return self.invalid("Invalid cell number. Must be between 0 and 8.")
        row, col = self.cell_mapping[cell]
        board = self.game_state["board"]
        if board[row][col] != '':
            return self.invalid(f"Invalid move. Cell {cell} is already occupied.")

        board[row][col] = mark
        self.broadcast(f"Player {player_id} placed their symbol ({mark}) in cell {cell}", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if self._check_winner(mark):
            return self.winner(player_id, reason=f"Player {player_id} wins with {mark}s!")
        if all(cell != '' for row in board for cell in row):
            return self.draw(reason="The game is a draw!")
        return None

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"])

    def _render_board(self):
        board = self.game_state["board"]
        return "\n---+---+---\n".join("|".join(f" {board[r][c]} " if board[r][c] else f" {str(r * 3 + c)} " for c in range(3)) for r in range(3))

    def _check_winner(self, mark: str) -> bool:
        board = self.game_state["board"]
        for i in range(3):
            if all(board[i][j] == mark for j in range(3)) or all(board[j][i] == mark for j in range(3)):    return True
        if all(board[i][i] == mark for i in range(3)) or all(board[i][2 - i] == mark for i in range(3)):    return True
        return False
