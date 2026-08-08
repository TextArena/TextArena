import re
from typing import Dict, Tuple, Any, Optional

import textarena as ta
from textarena.envs.Breakthrough.renderer import create_board_str

class BreakthroughEnv(ta.Env):
    def __init__(self, is_open: bool = True, board_size: int = 8):
        """
        Args:
            is_open: If True, the board state is revealed after every move to both players.
            board_size: Dimension of the board, default 8x8.
        """
        self.is_open = is_open
        self.board_size = board_size
        self._file_to_col = {chr(ord('a') + i): i for i in range(board_size)}
        self._col_to_file = {v: k for k, v in self._file_to_col.items()}

    def get_board_str(self):
        return create_board_str(board=self.state.game_state["board"], board_size=self.board_size)

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"board": self._build_board(), "valid_moves": None}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt, role_mapping={0:"White", 1:"Black"})
        self._augment_observations()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are playing {'White' if player_id == 0 else 'Black'} in a game of Breakthrough. You move {'up' if player_id == 0 else 'down'} on an {self.board_size}x{self.board_size} board.\n"
            "In your turn you can move a single piece one step forward or diagonally forward.\n"
            "A piece may only move diagonally if an opponent piece is there, and only move into such a preoccupied square in a diagonal step.\n"
            "When stepping into a square with an opponent piece, you capture it and the opponent's piece is removed permanently from the board.\n"
            "Use UCI-like notation in brackets, e.g. [a2a3] to move from a2 to a3.\n"
            "* 'a' corresponds to the leftmost column, '1' is the bottom row (from White's perspective).\n"
            "* Blacks's home row is the top row (row 8 for an 8x8). White's home row is the bottom row (row 1 for an 8x8).\n"
            "The first player whose piece reaches the opponent's home row wins. If your pieces are all captured, you lose."
        )

    def _build_board(self):
        board = [["" for _ in range(self.board_size)] for _ in range(self.board_size)]
        [board[r].__setitem__(c, "W") for r in range(2) for c in range(self.board_size)] # White rows
        [board[r].__setitem__(c, "B") for r in range(self.board_size-2,self.board_size) for c in range(self.board_size)] # Black rows
        return board

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._execute_player_move(action) # Attempt to parse & execute
        self._check_winner() # Check for victory conditions
        self._augment_observations() # Add open info to observations if is_open
        return self.state.step()

    def _execute_player_move(self, action: str):
        pattern = rf"\[([a-{chr(ord('a')+self.board_size-1)}])(\d{{1,2}})" \
              rf"([a-{chr(ord('a')+self.board_size-1)}])(\d{{1,2}})\]"
        match = re.search(pattern, action.strip().lower())
        if not match: self.state.set_invalid_move(reason="Please use bracketed algebraic notation like [a2a3]."); return
        start_file, start_rank, end_file, end_rank = match.groups()
        move_str = match.group(0)  # e.g. '[a2a3]'
        start_col = self._file_to_col[start_file]
        start_row = int(start_rank) - 1
        end_col = self._file_to_col[end_file]
        end_row = int(end_rank)   - 1

        # Convert to 0-based indices internally
        start_col = self._file_to_col.get(start_file, -1)
        start_row = int(start_rank) - 1  # '2' -> row=1
        end_col = self._file_to_col.get(end_file, -1)
        end_row = int(end_rank) - 1
        if not self._is_on_board(start_row, start_col) or not self._is_on_board(end_row, end_col): self.state.set_invalid_move(reason="Move is out of board bounds."); return
        if self._is_valid_move(self.state.current_player_id, start_row, start_col, end_row, end_col): # Verify that the move is valid according to Breakthrough rules
            piece = self.state.game_state["board"][start_row][start_col]
            self.state.game_state["board"][start_row][start_col] = ""
            self.state.game_state["board"][end_row][end_col] = piece
            self.state.add_observation(message=f"Player {self.state.current_player_id} moves {move_str} ({piece}).", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            self.state.set_invalid_move(reason="That move does not follow the Breakthrough rules or is not your piece.")

    def _is_valid_move(self, player_id: int, start_row: int, start_col: int, end_row: int, end_col: int) -> bool:
        piece = self.state.game_state["board"][start_row][start_col]
        if player_id == 0 and piece != "W": return False
        if player_id == 1 and piece != "B": return False
        row_dir = 1 if player_id == 0 else -1  # White moves row+1, Black row-1
        if end_row - start_row != row_dir: return False
        col_diff = abs(end_col - start_col)
        if col_diff > 1: return False
        dest_piece = self.state.game_state["board"][end_row][end_col] # Next, check occupancy conditions
        if col_diff == 1: # diagonal move => capturing an opponent
            # Must be capturing: the destination must have an opponent's piece
            if player_id == 0 and dest_piece != "B": return False
            if player_id == 1 and dest_piece != "W": return False
        else: # Straight forward => must be empty
            if dest_piece != "": return False
        return True

    def _is_on_board(self, row: int, col: int) -> bool:
        if row < 0 or row >= self.board_size: return False
        if col < 0 or col >= self.board_size: return False
        return True

    def _find_player_without_move(self):
        board = self.state.game_state["board"]
        size = self.board_size

        white_has_move = False
        for r in range(size):
            for c in range(size):
                if board[r][c] != "W": continue
                if r == size - 1: continue
                # Check 'W' forward (row +1)
                if board[r + 1][c] == "": white_has_move = True; break
                # Check 'W' forward diagonally (row +1, col +/- 1)
                if c > 0 and board[r + 1][c - 1] == "B": white_has_move = True; break
                if c < size - 1 and board[r + 1][c + 1] == "B": white_has_move = True; break
            if white_has_move: break
        if not white_has_move: return 0

        black_has_move = False
        for r in range(size):
            for c in range(size):
                if board[r][c] != "B": continue
                if r == 0: continue 
                # Check 'B' forward (row -1)
                if board[r - 1][c] == "": black_has_move = True; break
                # Check 'B' forward diagonally (row -1, col +/- 1)
                if c > 0 and board[r - 1][c - 1] == "W": black_has_move = True; break
                if c < size - 1 and board[r - 1][c + 1] == "W": black_has_move = True; break
            if black_has_move: break
        if not black_has_move: return 1
        return None

    def _check_winner(self):
        for c in range(self.board_size): # White
            if self.state.game_state["board"][self.board_size - 1][c] == "W":
                self.state.set_winner(player_id=0, reason="White reached Black's home row."); return
        for c in range(self.board_size): # Black
            if self.state.game_state["board"][0][c] == "B":
                self.state.set_winner(player_id=1, reason="Black reached White's home row."); return

        white_count = sum(self.state.game_state["board"][r][c] == "W" for r in range(self.board_size) for c in range(self.board_size))
        black_count = sum(self.state.game_state["board"][r][c] == "B" for r in range(self.board_size) for c in range(self.board_size))
        if white_count == 0:
            self.state.set_winner(player_id=1, reason="All White pieces captured."); return

        if black_count == 0:
            self.state.set_winner(player_id=0, reason="All Black pieces captured."); return

        player_without_move = self._find_player_without_move()
        if player_without_move is not None:
            self.state.add_observation(message=self._render_board(), observation_type=ta.ObservationType.GAME_BOARD)
            self.state.set_winner(player_id=1 - player_without_move, reason=f"Player {player_without_move} has no more moves.")

    def _augment_observations(self):
        if self.is_open and not self.state.done: self.state.add_observation(message=self._render_board(), observation_type=ta.ObservationType.GAME_BOARD)

    def _render_board(self) -> str:
        lines = []
        size = self.board_size
        for row_index in range(size - 1, -1, -1):
            row_label = str(row_index + 1).rjust(2, " ")
            row_str = [f"{row_label} |"]
            for col_index in range(size):
                piece = self.state.game_state["board"][row_index][col_index]
                row_str.append(piece if piece else ".")
            lines.append(" ".join(row_str))
        col_labels = "     " + " ".join(list(self._col_to_file[i] for i in range(size))) # Column labels
        lines.append(col_labels)
        return "\n"+"\n".join(lines)
