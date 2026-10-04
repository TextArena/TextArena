import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta
from textarena.envs.Checkers.renderer import create_board_str


class CheckersEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^([0-7])\s+([0-7])\s+([0-7])\s+([0-7])$"
    action_format = (
        "a move 'rowFrom colFrom rowTo colTo' as four numbers from 0 to 7 separated by spaces, "
        "for example '5 0 4 1' as Red or '2 1 3 2' as Black"
    )

    max_turns = ta.Param(
        50, "The number of turns, counting both players and treating a multi-jump as one turn, before the game is a "
            "draw.", min=1,
    )

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
        if player_id == 0:
            colour, own, other, start, forward, example = "Red", "r", "b", "rows 5-7 at the bottom", "up (towards row 0)", "5 0 4 1"
        else:
            colour, own, other, start, forward, example = "Black", "b", "r", "rows 0-2 at the top", "down (towards row 7)", "2 1 3 2"
        return (
            f"You are Player {player_id} playing a game of Checkers (English draughts) as {colour}. Red (Player 0) moves first.\n"
            f"On the board your men are '{own}' and your kings '{own.upper()}'; your opponent's are '{other}' and '{other.upper()}', and '.' is empty. "
            f"Your pieces start on {start}, and your men move {forward}.\n"
            "Make your move in the format 'rowFrom colFrom rowTo colTo' using the row and column numbers (0-7) shown on the board, "
            f"e.g. '{example}'.\nRules:\n"
            "  • A man moves one square diagonally forward onto an empty square; a king moves one square diagonally in any direction.\n"
            "  • Capture by jumping diagonally over an adjacent opposing piece onto the empty square right behind it, giving that landing square as the destination. "
            "Men capture only forward; kings capture in any diagonal direction.\n"
            "  • Captures are mandatory; continue jumping with the same piece while another capture is available, submitting each jump as a separate move.\n"
            "  • A man that reaches the far row is Kinged; this ends the turn, even in the middle of a capture sequence.\n"
            "  • You win when your opponent has no pieces left or cannot move on their turn.\n"
            f"  • The game is a draw after {self.max_turns} turns in total (each player's move is one turn; a multi-jump counts as one turn).\n"
        )

    def render(self, player_id: int) -> str:
        text = f"Current board:\n{self._render_board()}"
        forced = self.game_state["forced_piece"]
        if forced is not None:
            text += (
                f"\nYour capture continues: jump again with your piece on ({forced[0]},{forced[1]}). "
                f"Legal jumps: {', '.join(self.game_state['valid_moves'])}"
            )
        return text

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        row_from, col_from, row_to, col_to = map(int, move.groups())
        error = self._move_error(player_id, row_from, col_from, row_to, col_to)
        if error is not None:
            return self.invalid(f"Move '{row_from} {col_from} {row_to} {col_to}' is illegal. {error}")
        captured = abs(row_to - row_from) == 2
        promoted = self._move_piece(player_id, row_from, col_from, row_to, col_to)
        self.game_state["forced_piece"] = None

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
            self.broadcast(f"Player {player_id} must continue jumping with the piece on ({row_to},{col_to}).", ta.ObservationType.GAME_MESSAGE)
            # The engine counts submitted actions, while a compulsory
            # multi-jump is one checkers turn. Offset each continuation so the
            # configured limit is evaluated only after the chain is complete.
            if self.state.max_turns is not None:
                self.state.max_turns += 1
            self.set_next_player(player_id)
            return None

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

    def _move_error(self, player_id: int, r1: int, c1: int, r2: int, c2: int) -> Optional[str]:
        """Why a single step or jump is illegal under English/American checkers rules, or None if it is legal."""
        if not (0 <= r1 < 8 and 0 <= c1 < 8 and 0 <= r2 < 8 and 0 <= c2 < 8):
            return "Both squares must be on the board."
        piece = self.game_state['board'][r1][c1]; target = self.game_state['board'][r2][c2]
        if piece not in (('r', 'R') if player_id == 0 else ('b', 'B')):
            return f"There is no piece of yours on ({r1},{c1})."
        forced_piece = self.game_state.get("forced_piece")
        continue_jumping = None if forced_piece is None else f"You must continue jumping with your piece on ({forced_piece[0]},{forced_piece[1]})."
        if forced_piece is not None and forced_piece != (r1, c1):
            return continue_jumping
        if target != '.':
            return f"The destination ({r2},{c2}) is not empty."

        dr = r2 - r1; dc = abs(c2 - c1)
        directions = (-1, 1) if piece in ('R', 'B') else ((-1,) if piece == 'r' else (1,))
        is_capture = dc == 2 and dr in tuple(2 * direction for direction in directions)
        if is_capture:
            return None if self._is_valid_capture(r1, c1, r2, c2) else "A jump must pass over an adjacent opposing piece."
        if forced_piece is not None:
            return continue_jumping
        if dc == 1 and dr in directions:
            if self._player_has_capture(player_id):
                return f"A capture is available and captures are mandatory. Legal moves: {', '.join(self._legal_moves(player_id))}."
            return None
        if piece in ('r', 'b') and dc == abs(dr) and dr in (-2 * directions[0], -directions[0]):
            return "Men move and capture only diagonally forward; only kings may move backward."
        return "Pieces move one square diagonally, or jump two squares diagonally over an opposing piece."

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
