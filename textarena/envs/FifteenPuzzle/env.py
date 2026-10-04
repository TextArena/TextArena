import re
from typing import Any, Dict, Union

import textarena as ta
from textarena.envs.FifteenPuzzle.renderer import create_board_str

class FifteenPuzzleEnv(ta.GameEnv):
    """ Fifteen Puzzle environment """
    min_players = 1
    max_players = 1
    action_pattern = (
        r"^\s*(?P<wrapped>\[)?\s*(?P<direction>[a-zA-Z]+)"
        r"\s*(?(wrapped)\])\s*$"
    )
    action_format = "one of the directions 'up', 'down', 'left' or 'right'"

    def __init__(self, max_turns: int = 50):
        """ Initialize the Fifteen Puzzle environment """
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.max_turns = max_turns

    @property
    def board(self):
        return self.game_state["board"]

    @board.setter
    def board(self, value):
        self.game_state["board"] = value
        self.game_state["rendered_board"] = self._render_board(value)

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        board = self._generate_board()
        return {
            "board": board,
            "rendered_board": self._render_board(board),
            "initial_board": [row[:] for row in board],  # Deep copy of the initial board
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id}. You are playing the 15-Puzzle game.\n"
            "The objective of the game is to arrange the numbered tiles in ascending order from 1 to 15, read left to right and top to bottom, with the empty space located in the bottom-right corner.\n"
            "To make a move, you can slide a tile into the empty space (represented by a double underscore, e.g. __) by using one of the following commands:\n"
            "- 'up': Move the tile below the empty space up.\n"
            "- 'down': Move the tile above the empty space down.\n"
            "- 'left': Move the tile to the right of the empty space left.\n"
            "- 'right': Move the tile to the left of the empty space right.\n"
            "To submit your move, reply with the direction, e.g. 'up', 'down', 'left', or 'right'. The moves available on the current board are listed under it.\n"
            f"You have {self.max_turns} moves to solve the puzzle.\n"
            "A move that is not available changes nothing and you may try again, but two invalid moves in a row end the game.\n"
        )

    def render(self, player_id: int) -> str:
        r, c = self._get_empty_position()
        moves = {"'up'": r < 3, "'down'": r > 0, "'left'": c < 3, "'right'": c > 0}
        legal_moves = [m for m, valid in moves.items() if valid]
        rendered_board = self._render_board(self.board)
        self.game_state["rendered_board"] = rendered_board
        return f"Current Board:\n\n{rendered_board}\nAvailable Moves: {', '.join(legal_moves)}"

    def _generate_board(self):
        """Generate a nonterminal board with a known solution within the turn limit."""
        board = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
            [13, 14, 15, None],
        ]
        solved = [row[:] for row in board]
        previous_blank = None
        for _ in range(min(self.max_turns, 100)):
            previous_blank = self._random_slide(board, previous_blank)
        # A walk can loop back to the goal; one more slide leaves a board that is
        # one move from solved, which is still within the turn limit.
        if board == solved:
            self._random_slide(board, previous_blank)
        return board

    def _random_slide(self, board, previous_blank):
        empty_row, empty_col = self._find_empty(board)
        targets = [
            (empty_row + dr, empty_col + dc)
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1))
            if 0 <= empty_row + dr < 4 and 0 <= empty_col + dc < 4
        ]
        if previous_blank in targets and len(targets) > 1:
            targets.remove(previous_blank)
        target_row, target_col = self.rng.choice(targets)
        board[empty_row][empty_col], board[target_row][target_col] = (
            board[target_row][target_col],
            board[empty_row][empty_col],
        )
        return (empty_row, empty_col)

    def _render_board(self, board):
        """ Render the current board layout """
        rendered_board = ""
        for row in board:
            rendered_board += ' '.join(['__' if x is None else f"{x:2}" for x in row]) + "\n"
        return rendered_board

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        direction = move.group("direction").lower()
        if direction not in ("up", "down", "left", "right"):
            return self.invalid(f"Unknown direction '{direction}'. Reply with 'up', 'down', 'left', or 'right'.")
        if not self._move(direction):
            return self.invalid(f"Invalid move. No tile can slide {direction} into the empty space; choose one of the available moves.")

        self.game_state["rendered_board"] = self._render_board(self.board)  # update the rendered board

        if self._is_solved():  # check if the puzzle is solved
            return self.outcome({0: 1}, reason=f"Congratulations! Player {player_id} have successfully solved the 15-Puzzle.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_completion = self._get_percentage_completion()
        return self.outcome({0: pct_completion}, reason=f"The turn limit has been reached. The puzzle progress score is {pct_completion:.0%}.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _is_solved(self) -> bool:
        """ Check if the board is in a solved state """
        correct_tiles = list(range(1, 16)) + [None]
        current_tiles = [tile for row in self.board for tile in row]
        return current_tiles == correct_tiles

    def _move(self, direction: str) -> bool:
        """ Move a tile into the empty space if the direction is valid """
        empty_row, empty_col = self._get_empty_position()
        target_row, target_col = empty_row, empty_col

        if direction == 'up' and empty_row < 3:         target_row += 1
        elif direction == 'down' and empty_row > 0:     target_row -= 1
        elif direction == 'left' and empty_col < 3:     target_col += 1
        elif direction == 'right' and empty_col > 0:    target_col -= 1
        else:                                           return False ## invalid move

        ## swap the target tile with the empty tile
        self.board[empty_row][empty_col], self.board[target_row][target_col] = (self.board[target_row][target_col], self.board[empty_row][empty_col])
        return True

    def _get_empty_position(self):
        return self._find_empty(self.board)

    @staticmethod
    def _find_empty(board):
        for r in range(4):
            for c in range(4):
                if board[r][c] is None:
                    return r, c
        raise ValueError("board must contain one empty cell")

    def _get_percentage_completion(self) -> float:
        """Net progress on the positions that started wrong: each one now correct
        counts +1 and each initially correct position now wrong counts -1, so
        only a solved board scores 1."""
        goal = list(range(1, 16)) + [None]
        fixed = broken = total = 0
        flat_current = [tile for row in self.board for tile in row]
        flat_initial = [tile for row in self.game_state["initial_board"] for tile in row]
        for idx, goal_tile in enumerate(goal):
            if flat_initial[idx] == goal_tile:
                broken += flat_current[idx] != goal_tile
            else:
                total += 1
                fixed += flat_current[idx] == goal_tile
        return max(0.0, (fixed - broken) / total) if total > 0 else 0.0
