import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.ReverseTicTacToe.renderer import create_board_str


def _parse_cell(text: str) -> Optional[int]:
    """Parse a 0-8 cell without converting an unbounded integer."""
    normalized = text.lstrip("0") or "0"
    if len(normalized) > 1 or normalized > "8":
        return None
    return int(normalized)


class ReverseTicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^(?P<cell>[0-9]+)$"
    action_format = "a cell number from 0 to 8, for example '4'"

    def __init__(self):
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def setup(self) -> Dict[str, Any]:
        return {"board": [['' for _ in range(3)] for _ in range(3)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a game of Reverse Tic Tac Toe. Your symbol is '{'X' if player_id == 1 else 'O'}'.\nThe goal is to avoid getting three in a row (horizontally, vertically, or diagonally).\n"
            f"If you make three in a row, you LOSE.\nSubmit your move as the cell number, e.g. '4' to place your symbol in cell 4.\nAs Player {player_id}, you are '{'X' if player_id == 1 else 'O'}' and your opponent is '{'X' if player_id == 0 else 'O'}'."
        )

    def render(self, player_id: int) -> str:
        board = self.game_state["board"]
        available_moves = [f"'{str(r * 3 + c)}'" for r in range(3) for c in range(3) if board[r][c] == '']
        return f"Current Board:\n\n{self._render_board()}\n\nAvailable Moves: {', '.join(available_moves)}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        cell = _parse_cell(move.group("cell"))
        if cell is None:
            return self.invalid("Invalid cell index.")
        row, col = self.cell_mapping[cell]
        board = self.game_state["board"]
        if board[row][col] != '':
            return self.invalid(f"Cell {cell} is already occupied.")

        current_symbol = 'X' if player_id == 1 else 'O'
        board[row][col] = current_symbol
        self.broadcast(f"Player {player_id} placed their symbol ({current_symbol}) in cell {cell}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        # The current player made 3 in a row => they LOSE => opponent wins
        if self._check_loss(current_symbol):
            return self.winner(1 - player_id, reason=f"Player {player_id} loses by completing a line!")
        if all(cell != '' for row in board for cell in row):
            return self.draw(reason="It's a draw! No one lost.")
        return None

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"])

    def _render_board(self):
        board = self.game_state["board"]
        return "\n---+---+---\n".join("|".join(f" {board[r][c]} " if board[r][c] else f" {str(r * 3 + c)} " for c in range(3)) for r in range(3))

    def _check_loss(self, symbol: str) -> bool:
        board = self.game_state["board"]
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] == symbol: return True
            if board[0][i] == board[1][i] == board[2][i] == symbol: return True
        if board[0][0] == board[1][1] == board[2][2] == symbol:     return True
        if board[0][2] == board[1][1] == board[2][0] == symbol:     return True
        return False
