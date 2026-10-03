import re
from typing import Optional, Dict, Tuple, Any

import textarena as ta
from textarena.envs.ThreePlayerTicTacToe.renderer import create_board_str

class ThreePlayerTicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.board_size = 5
        self.cell_mapping = {i * self.board_size + j: (i, j) for i in range(self.board_size) for j in range(self.board_size)}
        self.symbols = {0: 'A', 1: 'B', 2: 'C'}

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def reset(self, num_players: int, seed: Optional[int] = None):
        assert num_players==3, f"ThreePlayerTicTacToe only works with exactly three players. {num_players} players were provided."
        self.state = ta.FFAMultiPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(self.board_size)] for _ in range(self.board_size)]}, player_prompt_function=self._prompt)
        self._observer_current_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id, symbol=self.symbols[player_id])
    
    def _render_board(self) -> str:
        cell_width = max(len(str(self.board_size * self.board_size - 1)), 2)  # ensures symbols like 'A', 'B', 'C' are well-centered
        def cell_str(r: int, c: int) -> str: return self.state.game_state["board"][r][c] if self.state.game_state["board"][r][c] != '' else str(r * self.board_size + c)
        def build_hline() -> str: return "+" + "+".join("-" * (cell_width + 2) for _ in range(self.board_size)) + "+"
        lines = [build_hline()]
        for r in range(self.board_size):
            row_cells = [f" {cell_str(r, c):^{cell_width}} " for c in range(self.board_size)]
            row_line = "|" + "|".join(row_cells) + "|"
            lines.append(row_line)
            lines.append(build_hline())
        return "\n".join(lines)

    def _observer_current_state(self) -> None:
        available_moves = []
        for i in range(self.board_size * self.board_size):
            r, c = self.cell_mapping[i]
            if self.state.game_state["board"][r][c] == '':
                available_moves.append(f"[{i}]")
        self.state.add_observation(message=self.m("board", "current_board", board=self._render_board(), moves=", ".join(available_moves)), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.search(r"\[(\d+)\]", action)
        max_cell = self.board_size ** 2 - 1
        if not match:
            if self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format", max_cell=max_cell)):
                self.state.set_winners(player_ids=[pid for pid in range(3) if pid!=player_id], reason=self.m("invalid_move", "made_invalid", player_id=player_id))
        else:
            cell = int(match.group(1))
            if cell not in self.cell_mapping:
                if self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_range", cell=cell, max_cell=max_cell)):
                    self.state.set_winners(player_ids=[pid for pid in range(3) if pid!=player_id], reason=self.m("invalid_move", "made_invalid", player_id=player_id))
            else:
                row, col = self.cell_mapping[cell]
                if self.state.game_state["board"][row][col] == '':
                    self.state.game_state["board"][row][col] = self.symbols[player_id]
                    self.state.add_observation(message=self.m("game_action", "placed", player_id=player_id, symbol=self.symbols[player_id], row=row, col=col), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self._check_winner(self.symbols[player_id]):
                        self.state.set_winners(player_ids=[player_id], reason=self.m("outcome", "win", player_id=player_id, symbol=self.symbols[player_id]))
                    elif all(cell != '' for row in self.state.game_state["board"] for cell in row): self.state.set_draw(reason=self.m("outcome", "draw"))
                else:
                    if self.state.set_invalid_move(reason=self.m("invalid_move", "already_occupied", cell=cell)): self.state.set_winners(player_ids=[pid for pid in range(3) if pid!=player_id], reason=self.m("invalid_move", "made_invalid", player_id=player_id))
        self._observer_current_state()
        return self.state.step()

    def _check_winner(self, symbol: str) -> bool:
        win_length = 4
        # Horizontal & Vertical
        for r in range(self.board_size):
            for c in range(self.board_size - win_length + 1):
                if all(self.state.game_state["board"][r][c + i] == symbol for i in range(win_length)): return True
        for c in range(self.board_size):
            for r in range(self.board_size - win_length + 1):
                if all(self.state.game_state["board"][r + i][c] == symbol for i in range(win_length)): return True
        # Diagonal \ and /
        for r in range(self.board_size - win_length + 1):
            for c in range(self.board_size - win_length + 1):
                if all(self.state.game_state["board"][r + i][c + i] == symbol for i in range(win_length)): return True
                if all(self.state.game_state["board"][r + i][c + win_length - 1 - i] == symbol for i in range(win_length)): return True
        return False