import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.Breakthrough.renderer import create_board_str


class BreakthroughEnv(ta.GameEnv):
    min_players = 2
    max_players = 2

    def __init__(self, is_open: bool = True, board_size: int = 8):
        """
        Args:
            is_open: If True, the board state is revealed after every move to both players.
            board_size: Dimension of the board, default 8x8.
        """
        if not isinstance(is_open, bool):
            raise ValueError("is_open must be a boolean")
        if not isinstance(board_size, int) or isinstance(board_size, bool) or not 4 <= board_size <= 26:
            raise ValueError("board_size must be an integer between 4 and 26")
        self.is_open = is_open
        self.board_size = board_size
        self._file_to_col = {chr(ord('a') + i): i for i in range(board_size)}
        self._col_to_file = {v: k for k, v in self._file_to_col.items()}
        last_file = chr(ord('a') + board_size - 1)
        self.action_pattern = rf"(?i)^\s*\[?([a-{last_file}])([1-9]\d?)([a-{last_file}])([1-9]\d?)\]?\s*$"

    @property
    def action_format(self) -> str:
        size = self.board_size
        return (
            f"a move in UCI-like notation, the start square followed by the end square (columns a to "
            f"{self._col_to_file[size - 1]}, rows 1 to {size}), for example 'a2a3' as White or 'a{size - 1}a{size - 2}' as Black"
        )

    def setup(self) -> Dict[str, Any]:
        board = self._build_board()
        return {"board": board, "valid_moves": self._get_valid_moves(0, board)}

    def roles(self) -> Dict[int, str]:
        return {0: "White", 1: "Black"}

    def prompt(self, player_id: int) -> str:
        size = self.board_size
        last_file = self._col_to_file[size - 1]
        example = "a2a3" if player_id == 0 else f"a{size - 1}a{size - 2}"
        text = (
            f"You are playing {'White' if player_id == 0 else 'Black'} in a game of Breakthrough. You move {'up' if player_id == 0 else 'down'} on the {size}x{size} board.\n"
            f"Each side starts with {2 * size} pieces filling its two home rows: White (W) on rows 1 and 2, Black (B) on rows {size - 1} and {size}. White moves first.\n"
            "In your turn you can move a single piece one step forward or diagonally forward.\n"
            "A piece may move diagonally into an empty square or capture an opponent there; it cannot capture straight ahead.\n"
            "When stepping into a square with an opponent piece, you capture it and the opponent's piece is removed permanently from the board.\n"
            f"Use UCI-like notation, e.g. '{example}' to move from {example[:len(example) // 2]} to {example[len(example) // 2:]}.\n"
            f"* Columns are lettered 'a' (leftmost) to '{last_file}', and rows are numbered from '1' (the bottom row, from White's perspective) to '{size}'.\n"
            f"* Black's home row is the top row (row {size}). White's home row is the bottom row (row 1).\n"
            "The first player whose piece reaches the opponent's home row wins. If all your pieces are captured, you lose."
        )
        if not self.is_open:
            text += "\nThe board is not shown in this variant: keep track of the position from the starting setup and the announced moves."
        return text

    def render(self, player_id: int) -> Optional[str]:
        return self._render_board() if self.is_open else None

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        start_file, start_rank, end_file, end_rank = (g.lower() for g in move.groups())
        move_str = f"{start_file}{start_rank}{end_file}{end_rank}"  # e.g. 'a2a3'

        # Convert to 0-based indices internally
        start_col = self._file_to_col.get(start_file, -1)
        start_row = int(start_rank) - 1  # '2' -> row=1
        end_col = self._file_to_col.get(end_file, -1)
        end_row = int(end_rank) - 1
        if not self._is_on_board(start_row, start_col) or not self._is_on_board(end_row, end_col):
            return self.invalid("Move is out of board bounds.")
        if not self._is_valid_move(player_id, start_row, start_col, end_row, end_col): # Verify that the move is valid according to Breakthrough rules
            return self.invalid("That move does not follow the Breakthrough rules or is not your piece.")

        board = self.game_state["board"]
        piece = board[start_row][start_col]
        board[start_row][start_col] = ""
        board[end_row][end_col] = piece
        self.broadcast(f"Player {player_id} moves {move_str} ({piece}).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        outcome = self._check_winner(player_id)
        if outcome is None:
            self.game_state["valid_moves"] = self._get_valid_moves(1 - player_id)
        else:
            self.game_state["valid_moves"] = []
        return outcome

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"], board_size=self.board_size)

    def _build_board(self):
        board = [["" for _ in range(self.board_size)] for _ in range(self.board_size)]
        [board[r].__setitem__(c, "W") for r in range(2) for c in range(self.board_size)] # White rows
        [board[r].__setitem__(c, "B") for r in range(self.board_size-2,self.board_size) for c in range(self.board_size)] # Black rows
        return board

    def _is_valid_move(self, player_id: int, start_row: int, start_col: int, end_row: int, end_col: int) -> bool:
        piece = self.game_state["board"][start_row][start_col]
        if player_id == 0 and piece != "W": return False
        if player_id == 1 and piece != "B": return False
        row_dir = 1 if player_id == 0 else -1  # White moves row+1, Black row-1
        if end_row - start_row != row_dir: return False
        col_diff = abs(end_col - start_col)
        if col_diff > 1: return False
        dest_piece = self.game_state["board"][end_row][end_col] # Next, check occupancy conditions
        if col_diff == 1: # diagonal move => empty or capturing an opponent
            if player_id == 0 and dest_piece == "W": return False
            if player_id == 1 and dest_piece == "B": return False
        else: # Straight forward => must be empty
            if dest_piece != "": return False
        return True

    def _is_on_board(self, row: int, col: int) -> bool:
        if row < 0 or row >= self.board_size: return False
        if col < 0 or col >= self.board_size: return False
        return True

    def _get_valid_moves(self, player_id: int, board=None):
        board = self.game_state["board"] if board is None else board
        piece = "W" if player_id == 0 else "B"
        direction = 1 if player_id == 0 else -1
        moves = []
        for row in range(self.board_size):
            for col in range(self.board_size):
                if board[row][col] != piece:
                    continue
                end_row = row + direction
                if not 0 <= end_row < self.board_size:
                    continue
                for end_col in (col - 1, col, col + 1):
                    if not 0 <= end_col < self.board_size:
                        continue
                    target = board[end_row][end_col]
                    if (end_col == col and target != "") or target == piece:
                        continue
                    moves.append(
                        f"{self._col_to_file[col]}{row + 1}"
                        f"{self._col_to_file[end_col]}{end_row + 1}"
                    )
        return moves

    def _check_winner(self, player_id: int) -> Optional[ta.Outcome]:
        board = self.game_state["board"]
        for c in range(self.board_size): # White
            if board[self.board_size - 1][c] == "W":
                return self.winner(0, reason="White reached Black's home row.")
        for c in range(self.board_size): # Black
            if board[0][c] == "B":
                return self.winner(1, reason="Black reached White's home row.")

        white_count = sum(board[r][c] == "W" for r in range(self.board_size) for c in range(self.board_size))
        black_count = sum(board[r][c] == "B" for r in range(self.board_size) for c in range(self.board_size))
        if white_count == 0:
            return self.winner(1, reason="All White pieces captured.")
        if black_count == 0:
            return self.winner(0, reason="All Black pieces captured.")

        next_player = 1 - player_id
        if not self._get_valid_moves(next_player):
            self.broadcast(self._render_board(), ta.ObservationType.GAME_BOARD)
            return self.winner(player_id, reason=f"Player {next_player} has no more moves.")
        return None

    def _render_board(self) -> str:
        lines = []
        size = self.board_size
        for row_index in range(size - 1, -1, -1):
            row_label = str(row_index + 1).rjust(2, " ")
            row_str = [f"{row_label} |"]
            for col_index in range(size):
                piece = self.game_state["board"][row_index][col_index]
                row_str.append(piece if piece else ".")
            lines.append(" ".join(row_str))
        col_labels = "     " + " ".join(list(self._col_to_file[i] for i in range(size))) # Column labels
        lines.append(col_labels)
        return "\n"+"\n".join(lines)
