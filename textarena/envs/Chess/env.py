import re, chess 
from typing import Any, Dict, Optional, Tuple

import textarena as ta
from textarena.envs.Chess.renderer import create_board_str


class ChessEnv(ta.Env):
    def __init__(self, is_open: bool=True, max_turns: int=30, show_valid: bool=True):
        """
        Args:
            is_open (bool): If True, both players can see the current board state. If False, players receive minimal information.
            max_turns (int): Maximum number of turns before the game ends.
            show_valid (bool): If True, players can see a list of valid moves.
        """
        self.max_turns = max_turns
        self.is_open = is_open 
        self.show_valid = show_valid 

    def get_board_str(self): return create_board_str(board=self.state.game_state["board"])

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        board = chess.Board()
        valid_moves = ', '.join([f'[{move.uci()}]' for move in board.legal_moves])
        game_state = {"board": board, "valid_moves": valid_moves}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt, role_mapping={0:"White", 1:"Black"})
        self._agument_observations()

    def _prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        color = 'White' if player_id==0 else 'Black'
        return self.m("player_prompt", "intro", color=color)
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._execute_player_move(action=action)
        self._check_gameover()
        self._agument_observations()
        return self.state.step()

    def _execute_player_move(self, action: str):
        match = re.compile(r"\[[a-h][1-8][a-h][1-8][qrbn]?\]", re.IGNORECASE).search(action.strip())
        if match is None: self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format")) # check if a move was provided
        else:
            move_uci = match.group(0).lower().replace("[", "").replace("]", "") # Extract the move from within the brackets
            move = chess.Move.from_uci(move_uci) # Attempt to make the move
            if move in self.state.game_state["board"].legal_moves:
                self.state.game_state["board"].push(move) # execute move
                self.state.add_observation(message=self.m("game_action", "moved", player_id=self.state.current_player_id, move_uci=move_uci), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            else: self.state.set_invalid_move(reason=self.m("invalid_move", "illegal")) # illegal move

    def _check_gameover(self):
        if self.state.game_state["board"].is_game_over():
            outcome = self.state.game_state["board"].outcome().result()
            if outcome == "1/2-1/2": self.state.set_draw(reason=self.m("outcome", "draw")) # check for draw
            else:
                winner_id = 0 if outcome == "1-0" else 1
                self.state.set_winner(player_id=winner_id, reason=self.m("outcome", "win", player_id=winner_id))

    def _agument_observations(self):
        board = self._board_with_coords(self.state.game_state['board'])
        moves = ', '.join([f'[{move.uci()}]' for move in self.state.game_state["board"].legal_moves])
        if self.is_open and self.show_valid: # display the board state and show the valid moves
            observation = self.m("board", "current_board", board=board)
            message = self.m("board", "valid_moves", observation=observation, moves=moves)
        elif self.is_open: # display the board state
            message = self.m("board", "current_board", board=board)
        elif self.show_valid: # show the valid moves
            message = self.m("board", "valid_moves", observation="", moves=moves)
        else:
            message = ""
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_BOARD)

    @staticmethod
    def _board_with_coords(board: chess.Board) -> str:
        inner_width = len(str(board).splitlines()[0])
        top = bottom = f"   +{'-' * (inner_width + 2)}+"
        body = [f" {rank} | {row} |" for rank, row in zip(range(8, 0, -1), str(board).splitlines())]
        files = "   " + " ".join("a b c d e f g h".split()).center(inner_width + 2)
        return "\n".join([top, *body, bottom, files])