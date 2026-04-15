import re
from typing import Any, Dict, Optional, Tuple

import textarena as ta 
from textarena.envs.ConnectFour.renderer import create_board_str

class ConnectFourEnv(ta.Env):
    def __init__(self, is_open: bool=True, num_rows: int=6, num_cols: int=7):
        """
        Args:
            is_open (bool): If True, the game state is visible to the players.
            num_rows (int): Number of rows in the game board.
            num_cols (int): Number of columns in the game board.
        """
        self.is_open = is_open 
        self.num_rows = num_rows 
        self.num_cols = num_cols 

    def get_board_str(self):
        return create_board_str(board=self.state.game_state["board"])

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        game_state = {"board": [["." for _ in range(self.num_cols)] for _ in range(self.num_rows)]} 
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self.state.add_observation(message=(f"{self.t('board', 'board_visible_state')}\n{self._render_board()}" if self.is_open else self.t('board', 'board_notvisible_state')), observation_type=ta.ObservationType.GAME_BOARD)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        symbol = "X" if player_id == 0 else "O"
        return "\n".join([
            self.t("player_prompt", "intro", player_id=player_id, symbol=symbol),
            self.t("player_prompt", "board_details", num_rows=self.num_rows, num_cols=self.num_cols),
            self.t("player_prompt", "description", end_col=self.num_cols-1),
            self.t("player_prompt", "goal"),
            self.t("player_prompt", "instruction"),
        ])

    def _render_board(self) -> str:
        column_numbers = " ".join([str(c) for c in range(self.num_cols)])
        separator = "-" * (self.num_cols * 2 - 1)
        board_rows = "\n".join([" ".join(row) for row in self.state.game_state["board"]])
        return f"{column_numbers}\n{separator}\n{board_rows}"

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        is_valid, col, reason = self._validate_action(action=action) # check if the actions is valid 
        if not is_valid:  self.state.set_invalid_move(reason=reason)
        else:
            row = self._get_available_row(col) # place the disc
            player_symbol = "X" if self.state.current_player_id == 0 else "O"
            self.state.add_observation(message=self.t("action", "dropped_disk", player_id=self.state.current_player_id, player_symbol=player_symbol, col=col), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.state.game_state["board"][row][col] = player_symbol # insert disc
            if self._check_win(row, col): self.state.set_winner(player_id=self.state.current_player_id, reason=self.t("outcome", "win", player_id=self.state.current_player_id))
            elif self._check_draw(): self.state.set_draw(reason=self.t("outcome", "draw"))
            else: # update board state 
                if self.is_open: self.state.add_observation(message=f"{self.t('board', 'board_visible_state')}\n{self._render_board()}", observation_type=ta.ObservationType.GAME_BOARD)
        return self.state.step()

    def _validate_action(self, action: str) -> Tuple[bool, Optional[int], Optional[str]]:
        match = re.compile(r'.*\[(?:col\s*)?(\d+)\].*', re.IGNORECASE).search(action)
        if not match: return False, None, self.t("invalid_move", "wrong_format", player_id=self.state.current_player_id)
        col = int(match.group(1))
        if not (0 <= col < self.num_cols): return False, None, self.t("invalid_move", "out_of_range", player_id=self.state.current_player_id, col=col)
        if self.state.game_state["board"][0][col] != ".": return False, None, self.t("invalid_move", "already_full", player_id=self.state.current_player_id, col=col)
        return True, col, None 

    def _get_available_row(self, col: int) -> int:
        for r in range(self.num_rows - 1, -1, -1):
            if self.state.game_state["board"][r][col] == ".":
                return r
        raise Exception("The column should be validated before calling the _get_available_row function.")

    def _check_win(self, row: int, col:int) -> bool:
        for direction in [((0, 1), (0, -1)), ((1, 0), (-1, 0)), ((1, 1), (-1, -1)), ((1, -1), (-1, 1)),]:
            total = 1  # Count the disc just placed
            for delta_row, delta_col in direction:
                total += self._check_direction(self.state.game_state["board"], row, col, delta_row, delta_col, self.state.game_state["board"][row][col])
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
        return all(self.state.game_state["board"][0][c] != "." for c in range(self.num_cols))
