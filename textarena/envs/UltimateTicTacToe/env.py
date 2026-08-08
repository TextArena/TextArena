import re, random
from typing import Optional, Dict, Tuple, List, Any

import textarena as ta
from textarena.envs.UltimateTicTacToe.renderer import create_board_str

class UltimateTicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.cell = {i: (i // 3, i % 3) for i in range(9)} # convert 0-8 → (row, col)

    def get_board_str(self):
        return create_board_str(board=self.state.game_state["board"])

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state={"board": [[[' ' for _ in range(3)] for _ in range(3)] for _ in range(9)], "macro_board": [[' ' for _ in range(3)] for _ in range(3)], "next_micro_board": None}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.state.add_observation(message=f"Current board:\n{self._render_board()}", observation_type=ta.ObservationType.GAME_BOARD)

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} in **Ultimate Tic Tac Toe**.\nSubmit your move as **[macro  micro]** (two numbers 0-8):\n"
            "• *macro*  = which mini-board you play in\n• *micro* = which square inside that mini-board\n"
            "Example `[7 8]` ➜ place your mark in mini-board 7, square 8, and\nforce your opponent to play in mini-board 8 next.\n\n"
            f"You are `{'X' if player_id==1 else 'O'}`.\n"
        )

    def _render_board(self) -> str:
        gs  = self.state.game_state
        out = []
        for macro_row in range(3):
            for micro_row in range(3):
                cells = []
                for macro_col in range(3):
                    macro_idx  = macro_row * 3 + macro_col
                    board_ij   = gs["board"][macro_idx][micro_row]

                    for micro_col, val in enumerate(board_ij):
                        if val == ' ':
                            micro_idx = micro_row * 3 + micro_col
                            cells.append(f"[{macro_idx},{micro_idx}]")
                        else:
                            cells.append(f"  {val}  ")

                    cells.append("|")
                out.append(" ".join(cells[:-1])) 

            # horizontal separator after each macro row (except the last)
            if macro_row < 2:
                out.append("-" * len(out[-1]))
        return "\n".join(out)


    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.current_player = 'X' if self.state.current_player_id == 1 else 'O'
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        match = re.search(r"\[\s*(\d)\s*,?\s*(\d)\s*\]", action)
        if match is None:
            self.state.set_invalid_move(reason="Move must be in the form [macro micro] with numbers 0-8.")
            return self.state.step()

        macro_idx, micro_idx = map(int, match.groups())

        # range check
        if not (0 <= macro_idx <= 8 and 0 <= micro_idx <= 8):
            self.state.set_invalid_move(reason="Indices must each be between 0 and 8.")
            return self.state.step()

        # convert micro index 0-8 → (row, col) inside that mini-board
        row, col = divmod(micro_idx, 3)

        # --- validate and (if OK) apply the move ---------------------------
        if self._is_valid_move(macro_idx, row, col):
            self._make_move(macro_idx, row, col)

            nxt = self.state.game_state["next_micro_board"]
            nxt_txt = "any micro board" if nxt is None else f"micro board {nxt}"

            self.state.add_observation(
                message=(
                    f"Player {self.state.current_player_id} played in micro board {macro_idx}, "
                    f"cell {micro_idx} (row {row}, col {col}). "
                    f"Player {1 - self.state.current_player_id} must now play in {nxt_txt}."
                ),
                observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            self.state.add_observation(message=f"Current board:\n{self._render_board()}", observation_type=ta.ObservationType.GAME_BOARD)

            # winner / draw checks
            if self._check_winner(self.state.game_state["macro_board"]):
                self.state.set_winner(player_id=self.state.current_player_id, reason=f"Player {self.state.current_player_id} wins Ultimate Tic Tac Toe!")
            elif self._is_draw():
                self.state.set_draw(reason="The game is a draw!")

        return self.state.step()

    
    def _make_move(self, macro, row, col):
        gs = self.state.game_state
        board = gs["board"][macro]
        board[row][col] = self.current_player

        # if that mini-board is now won → mark macro board
        if self._check_winner(board):
            gs["macro_board"][macro // 3][macro % 3] = self.current_player
            # fill the conquered mini-board
            for rr in range(3):
                for cc in range(3):
                    board[rr][cc] = self.current_player

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
            if board[i][0] == board[i][1] == board[i][2] != ' ': return True # Check rows
            if board[0][i] == board[1][i] == board[2][i] != ' ': return True # Check columns
        if board[0][0] == board[1][1] == board[2][2] != ' ': return True # Diagonals
        if board[0][2] == board[1][1] == board[2][0] != ' ': return True # Diagonals
        return False

    def _is_board_filled(self, board_array: str) -> bool:
        """ Check if a given 3×3 board is full """
        if all(cell != ' ' for row in board_array for cell in row): return True
        return False

    def _is_draw(self) -> bool:
        # If all micro boards are full, it's a draw
        if all(self._is_board_filled(micro_board) for micro_board in self.state.game_state['board']): return True
        # If the macro boards are full, it's a draw
        if self._is_board_filled(self.state.game_state['macro_board']): return True
        return False

    def _is_valid_move(self, micro_board, row, col):
        """Check if a move is valid."""
        reason = None
        ## check if the micro_board, row, and col are within the valid range
        if micro_board < 0 or micro_board > 8 or row < 0 or row > 2 or col < 0 or col > 2: reason="The micro_board, row, or col is out of range."
        ## check if the cell is empty
        elif self.state.game_state["board"][micro_board][row][col] != ' ': reason="The cell is already occupied."
        ## check if the next micro board is not won but the player is playing in a different micro board
        elif self.state.game_state['next_micro_board'] is not None and micro_board != self.state.game_state['next_micro_board']: reason="The player must play in the next micro board."
        ## check if the micro board is won and the player is still playing in it.
        elif self.state.game_state['macro_board'][micro_board // 3][micro_board % 3] != ' ': reason="The micro board is already won."
        if reason: self.state.set_invalid_move(reason=reason); return False
        else: return self.state.game_state["board"][micro_board][row][col] == ' '

    def _board_is_full(self, board: List[List[str]]) -> bool:
        """ Check if a 3×3 board is full """
        return all(cell != ' ' for row in board for cell in row)
