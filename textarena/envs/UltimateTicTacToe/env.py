import re
from typing import Any, Dict, List, Union

import textarena as ta
from textarena.envs.UltimateTicTacToe.renderer import create_board_str


class UltimateTicTacToeEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"^\s*\[?\s*([0-8])(?:\s*,\s*|\s+)([0-8])\s*\]?\s*$"
    action_format = "two numbers from 0 to 8, the mini-board and then the square inside it, for example '7 8'"

    def __init__(self):
        self.cell = {i: (i // 3, i % 3) for i in range(9)} # convert 0-8 → (row, col)

    def setup(self) -> Dict[str, Any]:
        game_state = {
            "board": [[[' ' for _ in range(3)] for _ in range(3)] for _ in range(9)],
            "macro_board": [[' ' for _ in range(3)] for _ in range(3)],
            "next_micro_board": None,
        }
        game_state["valid_moves"] = [f"{macro} {micro}" for macro in range(9) for micro in range(9)]
        return game_state

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in **Ultimate Tic Tac Toe**. You are `{'X' if player_id==0 else 'O'}`; X moves first.\n"
            "The board is a 3x3 grid of mini-boards numbered 0-8 (left to right, top to bottom). Each mini-board is a Tic Tac Toe grid whose squares are also numbered 0-8.\n"
            "Get three of your marks in a row inside a mini-board to win it. Win three mini-boards in a row (horizontally, vertically, or diagonally) to win the game.\n"
            "The square you pick sends your opponent to the mini-board with the same number. Won and full mini-boards are closed: nobody can play there, "
            "and a full mini-board without a winner counts for nobody. If you are sent to a closed mini-board, you may play in any open one.\n"
            "If every mini-board is closed and nobody has three in a row, the game is a draw.\n\n"
            "Submit your move as **macro micro** (two numbers 0-8):\n"
            "• *macro*  = which mini-board you play in\n• *micro* = which square inside that mini-board\n"
            "Example `7 8` ➜ place your mark in mini-board 7, square 8, and\nforce your opponent to play in mini-board 8 next (unless it is closed).\n"
            "On the board, each empty square of an open mini-board is labeled 'macro,micro' and unused squares of closed mini-boards show '.'.\n"
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        text = (
            f"Current board:\n{self._render_board()}\n\n"
            f"Mini-boards (X or O = won, D = full without a winner, number = still open):\n{self._render_macro_board()}"
        )
        if gs["valid_moves"]:
            forced = gs["next_micro_board"]
            where = "You may play in any open mini-board." if forced is None else f"You must play in mini-board {forced}."
            text += f"\n\n{where} Valid moves: " + ", ".join(f"'{move}'" for move in gs["valid_moves"])
        return text

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        macro_idx, micro_idx = map(int, move.groups())

        # convert micro index 0-8 → (row, col) inside that mini-board
        row, col = divmod(micro_idx, 3)

        gs = self.game_state
        # --- validate the move ----------------------------------------------
        if gs["next_micro_board"] is not None and macro_idx != gs["next_micro_board"]:
            return self.invalid(f"You must play in mini-board {gs['next_micro_board']}.")
        if gs["macro_board"][macro_idx // 3][macro_idx % 3] != ' ':
            return self.invalid(f"Mini-board {macro_idx} is already closed.")
        if gs["board"][macro_idx][row][col] != ' ':
            return self.invalid(f"Square {micro_idx} of mini-board {macro_idx} is already occupied.")

        # --- apply the move ---------------------------------------------------
        mark = 'X' if player_id == 0 else 'O'
        self._make_move(macro_idx, row, col, mark)

        nxt = gs["next_micro_board"]
        description = f"Player {player_id} played in mini-board {macro_idx}, square {micro_idx} (row {row}, col {col})."
        if not (self._check_winner(gs["macro_board"]) or self._is_draw()):
            nxt_txt = "may now play in any open mini-board" if nxt is None else f"must now play in mini-board {nxt}"
            description += f" Player {1 - player_id} {nxt_txt}."
        self.broadcast(description, ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # winner / draw checks
        if self._check_winner(gs["macro_board"]):
            gs["valid_moves"] = []
            return self.winner(player_id, reason=f"Player {player_id} wins Ultimate Tic Tac Toe!")
        if self._is_draw():
            gs["valid_moves"] = []
            return self.draw(reason="The game is a draw!")
        gs["valid_moves"] = self._get_valid_moves()
        return None

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"])

    def _render_board(self) -> str:
        gs  = self.game_state
        out = []
        for macro_row in range(3):
            for micro_row in range(3):
                cells = []
                for macro_col in range(3):
                    macro_idx  = macro_row * 3 + macro_col
                    board_ij   = gs["board"][macro_idx][micro_row]
                    closed     = gs["macro_board"][macro_row][macro_col] != ' '

                    for micro_col, val in enumerate(board_ij):
                        if val != ' ':
                            cells.append(f"  {val}  ")
                        elif closed:
                            cells.append("  .  ")
                        else:
                            micro_idx = micro_row * 3 + micro_col
                            cells.append(f"'{macro_idx},{micro_idx}'")

                    cells.append("|")
                out.append(" ".join(cells[:-1]))

            # horizontal separator after each macro row (except the last)
            if macro_row < 2:
                out.append("-" * len(out[-1]))
        return "\n".join(out)

    def _render_macro_board(self) -> str:
        macro = self.game_state["macro_board"]
        return "\n---+---+---\n".join(
            "|".join(f" {macro[r][c] if macro[r][c] != ' ' else r * 3 + c} " for c in range(3)) for r in range(3)
        )

    def _make_move(self, macro, row, col, mark):
        gs = self.game_state
        board = gs["board"][macro]
        board[row][col] = mark

        # if that mini-board is now won → mark macro board
        if self._check_winner(board):
            gs["macro_board"][macro // 3][macro % 3] = mark
        elif self._is_board_filled(board):
            gs["macro_board"][macro // 3][macro % 3] = 'D'

        # opponent must play in mini-board equal to the *micro* square we just used
        gs["next_micro_board"] = row * 3 + col
        nxt = gs["next_micro_board"]
        # if that board is already closed → free move
        if (gs["macro_board"][nxt // 3][nxt % 3] != ' ' or
            all(cell != ' ' for row_ in gs["board"][nxt] for cell in row_)):
            gs["next_micro_board"] = None

    def _check_winner(self, board: List[List[str]]) -> bool:
        """ Check if a given 3×3 board has a winner """
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] and board[i][0] in ('X', 'O'): return True # Check rows
            if board[0][i] == board[1][i] == board[2][i] and board[0][i] in ('X', 'O'): return True # Check columns
        if board[0][0] == board[1][1] == board[2][2] and board[0][0] in ('X', 'O'): return True # Diagonals
        if board[0][2] == board[1][1] == board[2][0] and board[0][2] in ('X', 'O'): return True # Diagonals
        return False

    def _is_board_filled(self, board_array) -> bool:
        """ Check if a given 3×3 board is full """
        return all(cell != ' ' for row in board_array for cell in row)

    def _is_draw(self) -> bool:
        return self._is_board_filled(self.game_state['macro_board'])

    def _get_valid_moves(self):
        gs = self.game_state
        forced = gs["next_micro_board"]
        macro_indices = range(9) if forced is None else (forced,)
        return [
            f"{macro} {row * 3 + col}"
            for macro in macro_indices
            if gs["macro_board"][macro // 3][macro % 3] == ' '
            for row in range(3)
            for col in range(3)
            if gs["board"][macro][row][col] == ' '
        ]
