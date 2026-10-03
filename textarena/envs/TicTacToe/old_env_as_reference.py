import re
from typing import Optional, Dict, Tuple, Any

import textarena as ta
from textarena.envs.TicTacToe.renderer import create_board_str

class TicTacToeEnv(ta.Env):
    def __init__(self):
        super().__init__()
        self.cell_mapping = {i * 3 + j: (i, j) for i in range(3) for j in range(3)}

    def get_board_str(self): return create_board_str(board=self.state.game_state["board"])
    def _render_board(self): return "\n---+---+---\n".join("|".join(f" {self.state.game_state['board'][r][c]} " if self.state.game_state['board'][r][c] else f" {str(r * 3 + c)} " for c in range(3)) for r in range(3))
    
    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        self.state.reset(game_state={"board": [['' for _ in range(3)] for _ in range(3)]}, player_prompt_function=self._prompt)
        self._observer_current_state()

    def _prompt(self, player_id:int, game_state:Dict[str,Any])-> str:
        return (
            f"You are Player {player_id} in Tic Tac Toe.\n"
            "Your goal is to win three in a row (horizontally, vertically, or diagonally) on the board.\n"
            "On your turn, you should select the square number (0-8) you want to put your mark in next.\n"
            "For example, '[4]' places your mark in the center cell of the board.\n\n"
            f"As Player {player_id}, you will be '{'X' if player_id == 1 else 'O'}', "
            f"while your opponent is '{'O' if player_id == 1 else 'X'}'.\n"
        )

    def _observer_current_state(self):
        available_moves = [f"'[{str(r*3+c)}]'" for r in range(3) for c in range(3) if self.state.game_state["board"][r][c] == '']
        self.state.add_observation(message=f"Current Board:\n\n{self._render_board()}\n\nAvailable Moves: {', '.join(available_moves)}", observation_type=ta.ObservationType.GAME_BOARD)

    def step(self,action:str)->Tuple[bool,ta.Info]:
        self.current_player = 'X' if self.state.current_player_id == 1 else 'O'
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[\s*(\d+)\s*\]").search(action)
        if match is None: # Invalid format
            self.state.set_invalid_move(reason="The submitted move does not follow the correct format.")
        else:
            cell = int(match.group(1))
            if cell not in self.cell_mapping: # Ensure the cell is within 0–8
                self.state.set_invalid_move(reason=f"{cell}. Must be between 0 and 8.")
            else:
                row, col = self.cell_mapping[cell]
                if self.state.game_state["board"][row][col] == '':
                    self.state.game_state["board"][row][col] = self.current_player # Make the move
                    self.state.add_observation(message=f"Player {self.state.current_player_id} placed their symbol ({self.current_player}) in cell {cell}.", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    if self._check_winner(): # Check for winner or draw
                        self.state.set_winner(player_id=self.state.current_player_id, reason=f"Player {self.state.current_player_id} has won!")
                    elif all(cell != '' for row in self.state.game_state["board"] for cell in row):
                        self.state.set_draw(reason="The game is a draw!")
                else:
                    self.state.set_invalid_move(reason=f"cell {cell} is already occupied.")
        self._observer_current_state()
        return self.state.step()

    def _check_winner(self) -> bool:
        board = self.state.game_state["board"]
        for i in range(3):
            if (board[i][0] == board[i][1] == board[i][2] != '' or board[0][i] == board[1][i] == board[2][i] != ''):    return True
        if (board[0][0] == board[1][1] == board[2][2] != '' or board[0][2] == board[1][1] == board[2][0] != ''):        return True
        return False
 