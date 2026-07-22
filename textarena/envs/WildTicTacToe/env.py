import re
from typing import Optional, Dict, Tuple, Any

import textarena as ta
from textarena.envs.WildTicTacToe.renderer import create_board_str

class WildTicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def get_board_str(self): return create_board_str(board=self.state.game_state["board"])
    def _render_board(self): return "\n---+---+---\n".join("|".join(f" {self.state.game_state['board'][r][c]} " if self.state.game_state['board'][r][c] else f" {str(r * 3 + c)} " for c in range(3)) for r in range(3))
    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(3)] for _ in range(3)]}, player_prompt_function=self._prompt)
        self._observer_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def _observer_current_state(self):
        available_moves = [f"[{mark} {str(r*3+c)}]" for r in range(3) for c in range(3) if self.state.game_state["board"][r][c] == '' for mark in ['X', 'O']]
        self.state.add_observation(message=self.m("board", "current_board", board=self._render_board(), moves=', '.join(available_moves)), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[\s*([XO])\s+(\d+)\s*\]", re.IGNORECASE).search(action)

        if match is None: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        else:
            mark = match.group(1).upper()
            cell = int(match.group(2))
            if cell not in self.cell_mapping: self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_range", cell=cell))
            else:
                row, col = self.cell_mapping[cell]
                if self.state.game_state["board"][row][col] == '':
                    self.state.game_state["board"][row][col] = mark
                    self.state.add_observation(message=self.m("game_action", "placed", player_id=self.state.current_player_id, mark=mark, cell=cell), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self._check_winner(mark): self.state.set_winner(player_id=self.state.current_player_id, reason=self.m("outcome", "win", player_id=self.state.current_player_id, mark=mark))
                    elif all(cell != '' for row in self.state.game_state["board"] for cell in row): self.state.set_draw(reason=self.m("outcome", "draw"))
                else: self.state.set_invalid_move(reason=self.m("invalid_move", "already_occupied", cell=cell))
        self._observer_current_state()
        return self.state.step()

    def _check_winner(self, mark: str) -> bool:
        board = self.state.game_state["board"]
        for i in range(3):
            if all(board[i][j] == mark for j in range(3)) or all(board[j][i] == mark for j in range(3)):    return True
        if all(board[i][i] == mark for i in range(3)) or all(board[i][2 - i] == mark for i in range(3)):    return True
        return False
