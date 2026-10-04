import re
from typing import Any, Dict, List, Union

import textarena as ta
from textarena.envs.Checkers.renderer import create_board_str


class CheckersEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"^\s*\[?\s*([0-7])\s+([0-7])\s+([0-7])\s+([0-7])\s*\]?\s*$"

    def __init__(self, max_turns: int = 50):
        """
        Args:
            max_turns (int): Maximum number of turns before the game ends in a draw.
        """
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.max_turns = max_turns

    def setup(self) -> Dict[str, Any]:
        board = self._initialize_board()
        return {
            "board": board,
            "forced_piece": None,
            "valid_moves": self._legal_moves_on_board(board, 0),
        }

    def roles(self) -> Dict[int, str]:
        return {0: "Red", 1: "Black"}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} playing a game of Checkers as {'Red' if player_id==0 else 'Black'}.\n"
            "Make your move in the format 'rowFrom colFrom rowTo colTo', e.g. '2 1 3 2'.\nBasic rules:\n"
            "  • Move diagonally forward by 1 if empty.\n"
            "  • Captures are mandatory; continue jumping with the same piece while another capture is available.\n"
            "  • A piece is Kinged if it reaches the opposite end.\n"
        )

    def render(self, player_id: int) -> str:
        return f"Current board:\n{self._render_board()}"

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        row_from, col_from, row_to, col_to = map(int, move.groups())
        if not self._is_valid_move(player_id, row_from, col_from, row_to, col_to):
            return self.invalid(f"Move '{row_from} {col_from} {row_to} {col_to}' is illegal.")
        captured = abs(row_to - row_from) == 2
        promoted = self._move_piece(player_id, row_from, col_from, row_to, col_to)

        board = self.game_state["board"]
        red_pieces = sum(cell.lower() == 'r' for row in board for cell in row)
        black_pieces = sum(cell.lower() == 'b' for row in board for cell in row)
        if red_pieces == 0:
            self.game_state["valid_moves"] = []
            return self.winner(1, reason="Red has no pieces left. Black wins!")
        if black_pieces == 0:
            self.game_state["valid_moves"] = []
            return self.winner(0, reason="Black has no pieces left. Red wins!")

        # A capturing turn continues with the same piece. Under English/American
        # draughts rules, reaching the king row ends a man's capturing turn.
        continuation = self._capture_moves_from(row_to, col_to) if captured and not promoted else []
        if continuation:
            self.game_state["forced_piece"] = (row_to, col_to)
            self.game_state["valid_moves"] = [" ".join(map(str, move)) for move in continuation]
            # The engine counts submitted actions, while a compulsory
            # multi-jump is one checkers turn. Offset each continuation so the
            # configured limit is evaluated only after the chain is complete.
            if self.state.max_turns is not None:
                self.state.max_turns += 1
            self.set_next_player(player_id)
            return None

        self.game_state["forced_piece"] = None
        next_player = 1 - player_id
        next_moves = self._legal_moves(next_player)
        self.game_state["valid_moves"] = next_moves
        if not next_moves:
            return self.winner(player_id, reason=f"Player {next_player} has no moves left.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.draw(reason="The turn limit has been reached.")

    def get_board_str(self):
        return create_board_str(game_state=self.game_state)

    def _initialize_board(self) -> List[List[str]]:
        return [['b' if row < 3 and (row + col) % 2 == 1 else 'r' if row > 4 and (row + col) % 2 == 1 else '.' for col in range(8)] for row in range(8)]

    def _render_board(self) -> str:
        header = "\n     " + "  ".join(str(col) for col in range(8)) + "\n"
        divider = "   +" + "-" * 25 + "\n"
        rows = "\n".join(f" {row} |" + "".join(f" {self.game_state['board'][row][col]} " for col in range(8)) for row in range(8))
        return header + divider + rows + "\n"

    def _is_valid_move(self, player_id: int, r1: int, c1: int, r2: int, c2: int) -> bool:
        """Check a single step or jump under English/American checkers rules."""
        if not (0 <= r1 < 8 and 0 <= c1 < 8 and 0 <= r2 < 8 and 0 <= c2 < 8):
            return False  # Out of board bounds
        piece = self.game_state['board'][r1][c1]; target = self.game_state['board'][r2][c2]
        if player_id == 0: # Check piece ownership
            if piece not in ['r', 'R']: return False # Player 0 -> must move 'r' or 'R'
        else:
            if piece not in ['b', 'B']: return False # Player 1 -> must move 'b' or 'B'

        if target != '.': return False   # destination must be empty
        forced_piece = self.game_state.get("forced_piece")
        if forced_piece is not None and forced_piece != (r1, c1):
            return False

        dr = r2 - r1; dc = abs(c2 - c1)
        directions = (-1, 1) if piece in ('R', 'B') else ((-1,) if piece == 'r' else (1,))
        is_capture = dc == 2 and dr in tuple(2 * direction for direction in directions)
        if is_capture:
            return self._is_valid_capture(r1, c1, r2, c2)
        if forced_piece is not None or self._player_has_capture(player_id):
            return False
        return dc == 1 and dr in directions

    def _is_valid_capture(self, r1: int, c1: int, r2: int, c2: int) -> bool:
        mid_r = (r1 + r2) // 2
        mid_c = (c1 + c2) // 2
        moving_piece = self.game_state["board"][r1][c1]
        jumped_piece = self.game_state["board"][mid_r][mid_c]
        if moving_piece.lower() == 'r' and jumped_piece.lower() == 'b': return True
        if moving_piece.lower() == 'b' and jumped_piece.lower() == 'r': return True
        return False

    def _move_piece(self, player_id: int, r1: int, c1: int, r2: int, c2: int) -> bool:
        piece = self.game_state["board"][r1][c1]
        self.game_state["board"][r1][c1] = '.'
        self.game_state["board"][r2][c2] = piece

        # If capturing, remove the jumped piece
        if abs(r2 - r1) == 2:
            mid_r = (r1 + r2) // 2
            mid_c = (c1 + c2) // 2
            self.game_state["board"][mid_r][mid_c] = '.'

        # Check for kinging
        promoted = False
        if piece == 'r' and r2 == 0:
            self.game_state["board"][r2][c2] = 'R'
            promoted = True
        elif piece == 'b' and r2 == 7:
            self.game_state["board"][r2][c2] = 'B'
            promoted = True
        self.broadcast(f"Player {player_id} moved ({r1},{c1}) -> ({r2},{c2}).", ta.ObservationType.GAME_ACTION_DESCRIPTION) # Send a summary message
        return promoted

    def _has_legal_move(self, player_id: int) -> bool:
        return bool(self._legal_moves(player_id))

    def _can_piece_move(self, r: int, c: int) -> bool:
        piece = self.game_state['board'][r][c]
        if piece == '.':
            return False
        player_id = 0 if piece.lower() == 'r' else 1
        return any(move[:2] == (r, c) for move in self._legal_move_tuples(player_id))

    def _capture_moves_from(self, r: int, c: int, board=None):
        board = self.game_state["board"] if board is None else board
        piece = board[r][c]
        if piece == '.':
            return []
        directions = (-1, 1) if piece in ('R', 'B') else ((-1,) if piece == 'r' else (1,))
        moves = []
        for dr in directions:
            for dc in (-1, 1):
                r2, c2 = r + 2 * dr, c + 2 * dc
                if not (0 <= r2 < 8 and 0 <= c2 < 8) or board[r2][c2] != '.':
                    continue
                jumped = board[r + dr][c + dc]
                if (piece.lower() == 'r' and jumped.lower() == 'b') or (
                    piece.lower() == 'b' and jumped.lower() == 'r'
                ):
                    moves.append((r, c, r2, c2))
        return moves

    def _player_has_capture(self, player_id: int) -> bool:
        return any(abs(r2 - r1) == 2 for r1, c1, r2, c2 in self._legal_move_tuples(player_id, captures_only=True))

    def _legal_move_tuples(self, player_id: int, captures_only: bool = False, board=None):
        board = self.game_state["board"] if board is None else board
        pieces = ('r', 'R') if player_id == 0 else ('b', 'B')
        forced = self.game_state.get("forced_piece") if board is self.game_state.get("board") else None
        captures = []
        simple = []
        for r in range(8):
            for c in range(8):
                piece = board[r][c]
                if piece not in pieces or (forced is not None and forced != (r, c)):
                    continue
                captures.extend(self._capture_moves_from(r, c, board))
                if forced is not None:
                    continue
                directions = (-1, 1) if piece in ('R', 'B') else ((-1,) if piece == 'r' else (1,))
                for dr in directions:
                    for dc in (-1, 1):
                        r2, c2 = r + dr, c + dc
                        if 0 <= r2 < 8 and 0 <= c2 < 8 and board[r2][c2] == '.':
                            simple.append((r, c, r2, c2))
        return captures if captures or captures_only else simple

    def _legal_moves(self, player_id: int):
        return [" ".join(map(str, move)) for move in self._legal_move_tuples(player_id)]

    def _legal_moves_on_board(self, board, player_id: int):
        return [" ".join(map(str, move)) for move in self._legal_move_tuples(player_id, board=board)]
