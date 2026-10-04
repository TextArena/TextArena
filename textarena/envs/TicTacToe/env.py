import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.TicTacToe.renderer import create_board_str


class TicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^([0-8])$"
    action_format = "a cell number from 0 to 8, for example '4'"

    def setup(self) -> Dict[str, Any]:
        return {"board": [['' for _ in range(3)] for _ in range(3)]}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Tic Tac Toe.\n"
            "Your goal is to win three in a row (horizontally, vertically, or diagonally) on the board.\n"
            "On your turn, reply with the square number (0-8) you want to put your mark in next.\n"
            "For example, '4' places your mark in the center cell of the board.\n\n"
            f"As Player {player_id}, you will be '{'X' if player_id == 1 else 'O'}', "
            f"while your opponent is '{'O' if player_id == 1 else 'X'}'.\n"
        )

    def render(self, player_id: int) -> str:
        board = self.game_state["board"]
        available = [f"'{r * 3 + c}'" for r in range(3) for c in range(3) if board[r][c] == '']
        return f"Current Board:\n\n{self._render_board()}\n\nAvailable Moves: {', '.join(available)}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        board = self.game_state["board"]
        cell = int(move.group(1))
        if not 0 <= cell <= 8:
            return self.invalid(f"{cell}. Must be between 0 and 8.")
        row, col = divmod(cell, 3)
        if board[row][col] != '':
            return self.invalid(f"cell {cell} is already occupied.")

        symbol = 'X' if player_id == 1 else 'O'
        board[row][col] = symbol
        self.broadcast(f"Player {player_id} placed their symbol ({symbol}) in cell {cell}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if self._check_winner():
            return self.winner(player_id, reason=f"Player {player_id} has won!")
        if all(cell != '' for row in board for cell in row):
            return self.draw(reason="The game is a draw!")
        return None

    def get_board_str(self) -> str:
        return create_board_str(board=self.game_state["board"])

    def _render_board(self) -> str:
        board = self.game_state["board"]
        return "\n---+---+---\n".join(
            "|".join(f" {board[r][c]} " if board[r][c] else f" {r * 3 + c} " for c in range(3)) for r in range(3)
        )

    def _check_winner(self) -> bool:
        board = self.game_state["board"]
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] != '' or board[0][i] == board[1][i] == board[2][i] != '':
                return True
        return board[0][0] == board[1][1] == board[2][2] != '' or board[0][2] == board[1][1] == board[2][0] != ''
