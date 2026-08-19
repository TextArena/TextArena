import re
from typing import Optional, Dict, Tuple, List, Any

import textarena as ta
from textarena.envs.ReverseTicTacToe.renderer import create_board_str

class ReverseTicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(3)] for _ in range(3)]}, player_prompt_function=self._prompt)
        self._observer_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        symbol = 'X' if player_id == 1 else 'O'
        opponent_symbol = 'X' if player_id == 0 else 'O'
        return self.m("player_prompt", "intro", player_id=player_id, symbol=symbol, opponent_symbol=opponent_symbol)

    def get_board_str(self): return create_board_str(board=self.state.game_state["board"])
    def _render_board(self):
        board = self.state.game_state["board"]
        return "\n---+---+---\n".join(
            "|".join(
                f" {board[r][c]} " if board[r][c] else f" {r * 3 + c} "
                for c in range(3)
            )
            for r in range(3)
        )
    def _observer_current_state(self):
        available_moves = [f"'[{str(r*3+c)}]'" for r in range(3) for c in range(3) if self.state.game_state["board"][r][c] == '']
        self.state.add_observation(message=self.m("board", "current_board", board=self._render_board(), moves=', '.join(available_moves)), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        current_symbol = 'X' if self.state.current_player_id == 1 else 'O'
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\d+)\]", action)
        if not match: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            cell = int(match.group(1))
            if cell not in self.cell_mapping: self.state.set_invalid_move(reason=self.m("invalid_move", "invalid_cell"))
            else:
                row, col = self.cell_mapping[cell]
                board = self.state.game_state["board"]
                if board[row][col] == '':
                    board[row][col] = current_symbol
                    self.state.add_observation(message=self.m("game_action", "placed", player_id=self.state.current_player_id, symbol=current_symbol, cell=cell), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self._check_loss(current_symbol): self.state.set_winner(player_id=1-self.state.current_player_id, reason=self.m("outcome", "loss", player_id=self.state.current_player_id)) # The current player made 3 in a row => they LOSE => opponent wins
                    elif all(cell != '' for row in board for cell in row): self.state.set_draw(reason=self.m("outcome", "draw"))
                else: self.state.set_invalid_move(reason=self.m("invalid_move", "already_occupied", cell=cell))
        self._observer_current_state()
        return self.state.step()

    def _check_loss(self, symbol: str) -> bool:
        board = self.state.game_state["board"]
        for i in range(3):
            if board[i][0] == board[i][1] == board[i][2] == symbol: return True
            if board[0][i] == board[1][i] == board[2][i] == symbol: return True
        if board[0][0] == board[1][1] == board[2][2] == symbol:     return True
        if board[0][2] == board[1][1] == board[2][0] == symbol:     return True
        return False