import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.Chess.board import QUEEN, WHITE, Board, Move
from textarena.envs.Chess.renderer import create_board_str


class ChessEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"(?i)^([a-h][1-8][a-h][1-8][qrbn]?)$"
    action_format = "a move in UCI format, the start square followed by the end square (add q, r, b or n to promote a pawn), for example 'e2e4'"

    is_open = ta.Param(True, "Show the board to the acting player before each move.")
    max_turns = ta.Param(30, "The total number of moves (both players combined) before the game is drawn.", min=1)
    show_valid = ta.Param(True, "Show the list of legal moves before each move.")

    def setup(self) -> Dict[str, Any]:
        board = Board()
        valid_moves = ', '.join([move.uci() for move in board.legal_moves])
        return {"board": board, "valid_moves": valid_moves}

    def roles(self) -> Dict[int, str]:
        return {0: "White", 1: "Black"}

    def prompt(self, player_id: int) -> str:
        move, castle, promote = ("e2e4", "e1g1", "e7e8q") if player_id == 0 else ("e7e5", "e8g8", "e2e1q")
        lines = [
            f"You are playing {self.roles()[player_id]} in a game of Chess.",
            f"Reply with one move in UCI format: the start square followed by the end square, e.g. '{move}'. Castle by "
            f"moving the king two squares (e.g. '{castle}'), and promote a pawn by adding q, r, b or n (e.g. '{promote}').",
        ]
        if self.is_open:
            lines.append(
                "On the board, uppercase letters are White's pieces and lowercase letters are Black's (K king, Q queen, "
                "R rook, B bishop, N knight, P pawn), and '.' is an empty square."
            )
        elif self.show_valid:
            lines.append("The board is not shown, so track the position from the move history.")
        else:
            lines.append(
                "The board and the list of legal moves are not shown, so track the position from the move history."
            )
        lines.append(f"The game is drawn after {self.max_turns} moves in total (both players combined) if it has not ended sooner.")
        return "\n".join(lines)

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
            return self.invalid(self._illegal_reason(board, chess_move, move_uci))
        board.push(chess_move)
        self.game_state["valid_moves"] = ', '.join(legal.uci() for legal in board.legal_moves)
        self.broadcast(f"{self.roles()[player_id]} played {move_uci}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

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
            return self.winner(winner_id, reason=f"{self.roles()[winner_id]} wins by {termination}.")
        if board.is_repetition(3):
            self.game_state["valid_moves"] = ""
            return self.draw(reason="Game ended in a draw by threefold repetition.")
        if board.is_fifty_moves():
            self.game_state["valid_moves"] = ""
            return self.draw(reason="Game ended in a draw by fifty-move rule.")
        if board.is_check():
            self.broadcast(f"{self.roles()[1 - player_id]} is in check.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return None

    def _illegal_reason(self, board: Board, chess_move: Move, move_uci: str) -> str:
        start, piece = move_uci[:2], board.piece_at(chess_move.from_square)
        mover, other = (self.roles()[0], self.roles()[1]) if board.turn == WHITE else (self.roles()[1], self.roles()[0])
        if chess_move.promotion is None and Move(chess_move.from_square, chess_move.to_square, QUEEN) in board.legal_moves:
            return f"{move_uci} needs a promotion letter: add q, r, b or n, for example '{move_uci}q'."
        if chess_move.promotion is not None and Move(chess_move.from_square, chess_move.to_square) in board.legal_moves:
            return f"{move_uci} is not a promotion: only a pawn reaching the last rank takes a letter, so write '{move_uci[:4]}'."
        if piece is None:
            return f"{move_uci} is not a legal move: there is no piece on {start}."
        if piece.color != board.turn:
            return f"{move_uci} is not a legal move: the piece on {start} is {other}'s, and {mover} is to move."
        if board.is_check():
            return f"{move_uci} is not a legal move in this position. {mover} is in check."
        return f"{move_uci} is not a legal move in this position."

    def get_board_str(self):
        return create_board_str(board=self.game_state["board"])

    @staticmethod
    def _board_with_coords(board: Board) -> str:
        inner_width = len(str(board).splitlines()[0])
        top = bottom = f"   +{'-' * (inner_width + 2)}+"
        body = [f" {rank} | {row} |" for rank, row in zip(range(8, 0, -1), str(board).splitlines())]
        files = "    " + " ".join("a b c d e f g h".split()).center(inner_width + 2)
        return "\n".join([top, *body, bottom, files])
