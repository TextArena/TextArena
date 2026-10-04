import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.Chess.board import WHITE, Board, Move
from textarena.envs.Chess.renderer import create_board_str


class ChessEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"(?i)^\s*\[?\s*([a-h][1-8][a-h][1-8][qrbn]?)\s*\]?\s*$"
    action_format = "a move in UCI format, the start square followed by the end square (add q, r, b or n to promote a pawn), for example 'e2e4'"

    def __init__(self, is_open: bool=True, max_turns: int=30, show_valid: bool=True):
        """
        Args:
            is_open (bool): If True, both players can see the current board state. If False, players receive minimal information.
            max_turns (int): Maximum number of turns before the game ends.
            show_valid (bool): If True, players can see a list of valid moves.
        """
        if not isinstance(is_open, bool):
            raise ValueError("is_open must be a boolean")
        if not isinstance(show_valid, bool):
            raise ValueError("show_valid must be a boolean")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.max_turns = max_turns
        self.is_open = is_open
        self.show_valid = show_valid

    def setup(self) -> Dict[str, Any]:
        board = Board()
        valid_moves = ', '.join([move.uci() for move in board.legal_moves])
        return {"board": board, "valid_moves": valid_moves}

    def roles(self) -> Dict[int, str]:
        return {0: "White", 1: "Black"}

    def prompt(self, player_id: int) -> str:
        return f"You are playing {'White' if player_id==0 else 'Black'} in a game of Chess.\n Make your moves in UCI format (e.g., 'e2e4')."

    def render(self, player_id: int) -> Optional[str]:
        board = self.game_state["board"]
        message = ""
        if self.is_open: message += f"Current board:\n{self._board_with_coords(board)}"
        if self.show_valid: message += f"\nValid moves: {', '.join([move.uci() for move in board.legal_moves])}"
        return message or None

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        board = self.game_state["board"]
        move_uci = move.group(1).lower()
        expected_player = 0 if board.turn == WHITE else 1
        if player_id != expected_player:
            return self.invalid("It is not this player's turn.")
        try:
            chess_move = Move.from_uci(move_uci)
        except ValueError:
            # Some strings accepted by the outer shape check (for example
            # ``a1a1``) are not valid UCI moves.
            return self.invalid("Invalid UCI move.")
        if chess_move not in board.legal_moves:
            return self.invalid("Illegal move.")
        board.push(chess_move)
        self.game_state["valid_moves"] = ', '.join(legal.uci() for legal in board.legal_moves)
        self.broadcast(f"Player {player_id} made the following move: {move_uci}", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # Automatic terminal conditions (checkmate, stalemate, insufficient
        # material, fivefold repetition and the 75-move rule) are reported by
        # ``Board.outcome``. Claimable draws are auto-accepted by this environment
        # only once the current position itself qualifies. Using
        # ``claim_draw=True`` here would also return true when the *next*
        # player merely has a legal move that could create a claim, ending the
        # game one ply before that move is selected.
        outcome = board.outcome(claim_draw=False)
        if outcome is not None:
            self.game_state["valid_moves"] = ""
            termination = outcome.termination.name.replace("_", " ").lower()
            if outcome.winner is None:
                return self.draw(reason=f"Game ended in a draw by {termination}.")
            winner_id = 0 if outcome.winner == WHITE else 1
            return self.winner(winner_id, reason=f"Player {winner_id} wins by {termination}.")
        if board.is_repetition(3):
            self.game_state["valid_moves"] = ""
            return self.draw(reason="Game ended in a draw by threefold repetition.")
        if board.is_fifty_moves():
            self.game_state["valid_moves"] = ""
            return self.draw(reason="Game ended in a draw by fifty-move rule.")
        return None

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"])

    @staticmethod
    def _board_with_coords(board: Board) -> str:
        inner_width = len(str(board).splitlines()[0])
        top = bottom = f"   +{'-' * (inner_width + 2)}+"
        body = [f" {rank} | {row} |" for rank, row in zip(range(8, 0, -1), str(board).splitlines())]
        files = "   " + " ".join("a b c d e f g h".split()).center(inner_width + 2)
        return "\n".join([top, *body, bottom, files])
