import re
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta
from textarena.envs.Checkers.renderer import create_board_str

class CheckersEnv(ta.Env):
    def __init__(self, max_turns: int = 50):
        """
        Args:
            max_turns (int): Maximum number of turns before the game ends in a draw.
        """
        self.max_turns = max_turns

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)
    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        self.state.reset(game_state={"board": self._initialize_board()}, player_prompt_function=self._prompt, role_mapping={0:"Red", 1:"Black"})
        self.state.add_observation(message=f"Current board:\n{self._render_board()}", observation_type=ta.ObservationType.GAME_BOARD)

    def _initialize_board(self) -> List[List[str]]: return [['b' if row < 3 and (row + col) % 2 == 1 else 'r' if row > 4 and (row + col) % 2 == 1 else '.' for col in range(8)] for row in range(8)]
    def _render_board(self) -> str:
        header = "\n     " + "  ".join(str(col) for col in range(8)) + "\n"
        divider = "   +" + "-" * 25 + "\n"
        rows = "\n".join(f" {row} |" + "".join(f" {self.state.game_state['board'][row][col]} " for col in range(8)) for row in range(8))
        return header + divider + rows + "\n"

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return (
            f"You are Player {player_id} playing a game of Checkers as {'Red' if player_id==0 else 'Black'}.\n"
            "Make your move in the format [rowFrom colFrom rowTo colTo], e.g. '[2 1 3 2]'.\nBasic rules:\n"
            "  • Move diagonally forward by 1 if empty.\n"
            "  • Capture by jumping over an opponent piece.\n"
            "  • A piece is Kinged if it reaches the opposite end.\n"
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        self._execute_player_move(action)
        self._check_gameover()
        self.state.add_observation(message=f"Current board:\n{self._render_board()}", observation_type=ta.ObservationType.GAME_BOARD)
        return self.state.step()

    def _execute_player_move(self, action: str):
        """ Parse the action to find the requested move. If valid, make the move, otherwise set it as an invalid move """
        match = re.compile(r"\[\s*(\d)\s+(\d)\s+(\d)\s+(\d)\s*\]").search(action.strip())
        if not match: self.state.set_invalid_move(reason="No valid move format found."); return
        row_from, col_from, row_to, col_to = map(int, match.groups()) # Extract coordinates
        if self._is_valid_move(self.state.current_player_id, row_from, col_from, row_to, col_to): self._move_piece(self.state.current_player_id, row_from, col_from, row_to, col_to)
        else: self.state.set_invalid_move(reason=f"Move [{row_from} {col_from} {row_to} {col_to}] is illegal.")

    def _is_valid_move(self, player_id: int, r1: int, c1: int, r2: int, c2: int) -> bool:
        """Check if a move is valid under simplified Checkers rules. TODO: This does not handle forced captures or multi-jumps """
        if not (0 <= r1 < 8 and 0 <= c1 < 8 and 0 <= r2 < 8 and 0 <= c2 < 8):
            return False  # Out of board bounds
        piece = self.state.game_state['board'][r1][c1]; target = self.state.game_state['board'][r2][c2]
        if player_id == 0: # Check piece ownership
            if piece not in ['r', 'R']: return False # Player 0 -> must move 'r' or 'R'
        else:
            if piece not in ['b', 'B']: return False # Player 1 -> must move 'b' or 'B'
        
        if target != '.': return False   # destination must be empty
        # Simple move logic (no forced capture / multi-jump):
        dr = r2 - r1; dc = abs(c2 - c1)
        if piece in ['R', 'B']: # If it's a King, can move diagonally up or down by 1 step
            if abs(dr) == 1 and dc == 1: return True
            if abs(dr) == 2 and dc == 2: return self._is_valid_capture(r1, c1, r2, c2) # Or single capture: move by 2 if jumping over opponent
            return False
        else: # Non-king logic: must move forward 1 or capture forward
            direction = -1 if piece == 'r' else 1  # Red moves "up", Black moves "down"
            if dr == direction and dc == 1: return True # Non-capturing move
            if dr == 2 * direction and dc == 2: return self._is_valid_capture(r1, c1, r2, c2) # Capturing move
            return False

    def _is_valid_capture(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        mid_r = (r1 + r2) // 2
        mid_c = (c1 + c2) // 2
        moving_piece = self.state.game_state["board"][r1][c1]
        jumped_piece = self.state.game_state["board"][mid_r][mid_c]
        if moving_piece.lower() == 'r' and jumped_piece.lower() == 'b': return True
        if moving_piece.lower() == 'b' and jumped_piece.lower() == 'r': return True
        return False

    def _move_piece(self, player_id: int, r1: int, c1: int, r2: int, c2: int):
        piece = self.state.game_state["board"][r1][c1]
        self.state.game_state["board"][r1][c1] = '.'
        self.state.game_state["board"][r2][c2] = piece

        # If capturing, remove the jumped piece
        if abs(r2 - r1) == 2:
            mid_r = (r1 + r2) // 2
            mid_c = (c1 + c2) // 2
            self.state.game_state["board"][mid_r][mid_c] = '.'

        # Check for kinging
        if piece == 'r' and r2 == 0:    self.state.game_state["board"][r2][c2] = 'R'  # Red becomes King
        elif piece == 'b' and r2 == 7:  self.state.game_state["board"][r2][c2] = 'B'  # Black becomes King
        self.state.add_observation(message=f"Player {player_id} moved ({r1},{c1}) -> ({r2},{c2}).", observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION) # Send a summary message

    def _check_gameover(self):
        red_pieces = sum(cell.lower() == 'r' for row in self.state.game_state["board"] for cell in row)
        black_pieces = sum(cell.lower() == 'b' for row in self.state.game_state["board"] for cell in row)
        if red_pieces == 0: self.state.set_winner(player_id=1, reason="Red has no pieces left. Black wins!"); return
        if black_pieces == 0: self.state.set_winner(player_id=0, reason="Black has no pieces left. Red wins!"); return
        # If either player has no legal moves, that player loses.
        if not self._has_legal_move(1 - self.state.current_player_id): # The other player wins
            self.state.set_winner(player_id=self.state.current_player_id, reason=f"Player {1 - self.state.current_player_id} has no moves left."); return
        if not self._has_legal_move(self.state.current_player_id): # The other player wins
            self.state.set_winner(player_id=1-self.state.current_player_id, reason=f"Player {self.state.current_player_id} has no moves left."); return
        if self.state.check_turn_limit(): self.state.set_draw(reason="The turn limit has been reached.")

    def _has_legal_move(self, player_id: int) -> bool:
        for r in range(8):
            for c in range(8):
                piece = self.state.game_state['board'][r][c]
                if player_id == 0 and piece in ['r', 'R']:
                    if self._can_piece_move(r, c): return True
                elif player_id == 1 and piece in ['b', 'B']:
                    if self._can_piece_move(r, c): return True
        return False

    def _can_piece_move(self, r: int, c: int) -> bool:
        piece = self.state.game_state['board'][r][c]
        if piece == '.': return False
        if piece in ['R', 'B']: directions = [(-1, -1), (-1, 1), (1, -1), (1, 1)] # King can move in any diagonal direction
        else:                   directions = [(-1, -1), (-1, 1)] if piece=="r" else [(1, -1), (1, 1)] # Normal piece moves (Red goes "up", Black goes "down")
        # Check single-step or capture possibility
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and self.state.game_state['board'][nr][nc] == '.': return True
            nr2, nc2 = r + 2*dr, c + 2*dc # Check capture possibility
            if 0 <= nr2 < 8 and 0 <= nc2 < 8 and self.state.game_state['board'][nr2][nc2] == '.':
                jumped = self.state.game_state['board'][r + dr][c + dc]
                if piece.lower() == 'r' and jumped.lower() == 'b': return True
                if piece.lower() == 'b' and jumped.lower() == 'r': return True
        return False
