import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Minesweeper.renderer import create_board_str


class MinesweeperEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    max_grid_cells = 10_000
    max_action_chars = 4096

    def __init__(self, rows: int = 8, cols: int = 8, num_mines: int = 10, max_turns: int = 100):
        """
        Args:
            rows (int): the number of rows
            cols (int): the number of columns
            num_mines (int): the number of mines
        """
        if not isinstance(rows, int) or isinstance(rows, bool) or rows <= 0:
            raise ValueError("rows must be a positive integer")
        if not isinstance(cols, int) or isinstance(cols, bool) or cols <= 0:
            raise ValueError("cols must be a positive integer")
        if rows * cols > self.max_grid_cells:
            raise ValueError(
                f"rows and cols create more than {self.max_grid_cells} cells"
            )
        if not isinstance(num_mines, int) or isinstance(num_mines, bool) or num_mines < 0:
            raise ValueError("num_mines must be a non-negative integer")
        max_safe_zone = min(3, rows) * min(3, cols)
        max_mines = rows * cols - max_safe_zone
        if num_mines > max_mines:
            raise ValueError(
                f"num_mines must be at most {max_mines} so every first move "
                "can have a mine-free 3x3 safe zone"
            )
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        self.rows = rows
        self.cols = cols
        self.num_mines = num_mines
        self.max_turns = max_turns

    # Tests (and the renderer) access these as attributes; they live in game_state.
    @property
    def grid(self) -> List[List[int]]: return self.game_state["grid"]
    @grid.setter
    def grid(self, value): self.game_state["grid"] = value

    @property
    def revealed(self) -> List[List[bool]]: return self.game_state["revealed"]
    @revealed.setter
    def revealed(self, value): self.game_state["revealed"] = value

    @property
    def flags(self) -> List[List[bool]]: return self.game_state["flags"]
    @flags.setter
    def flags(self, value): self.game_state["flags"] = value

    @property
    def first_move(self) -> bool: return self.game_state["first_move"]
    @first_move.setter
    def first_move(self, value): self.game_state["first_move"] = value

    @property
    def initial_move_pos(self) -> Optional[Tuple[int, int]]: return self.game_state.get("initial_move_pos")
    @initial_move_pos.setter
    def initial_move_pos(self, value): self.game_state["initial_move_pos"] = value

    def get_board_str(self):
        return create_board_str(self.grid, self.revealed, self.flags)

    def setup(self) -> Dict[str, Any]:
        game_state = {
            "grid": [[0 for _ in range(self.cols)] for _ in range(self.rows)],
            "revealed": [[False for _ in range(self.cols)] for _ in range(self.rows)],
            "flags": [[False for _ in range(self.cols)] for _ in range(self.rows)],
            "first_move": True,  # Track if it's the first move to ensure playability
            "initial_move_pos": None,
            "initial_revealed": None,
        }
        self.state.game_state = game_state  # so _render_board can read it during setup
        game_state["rendered_board"] = self._render_board()
        return game_state

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing the Minesweeper game.\nThe objective of the game is to reveal all cells that do not contain mines.\n"
            "To make a move, simply reply with the row and column coordinates you want to reveal, in the format 'row col'.\n"
            "For example:\n"
            "- '3 2' to reveal the cell in Row 3, Column 2.\n"
            "- '5 6' to reveal the cell in Row 5, Column 6.\n"
            "On your first move, you will reveal an area around the cell you choose to ensure a safe start.\n"
            "The current board layout is shown below. Cells that are unrevealed are represented by a dot ('.'), revealed numbers show the count of adjacent mines.\n"
            "Be mindful not to choose already revealed cells.\n"
            "Here is the current board layout:\n"
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n\n{self.get_board_str()}"

    def _render_board(self) -> str:
        """Render the game board using the public renderer."""
        return create_board_str(self.grid, self.revealed, self.flags)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        if action_text.startswith("[") or action_text.endswith("]"):
            if not (action_text.startswith("[") and action_text.endswith("]")):
                return self.invalid("Invalid coordinate format: mismatched brackets.")
            action_text = action_text[1:-1].strip()
        match = re.fullmatch(r"(\d+)(?:\s*,\s*|\s+)(\d+)", action_text)
        if match is None:
            return self.invalid("You did not respond with valid 'row col' coordinates, e.g. '3 2'.")

        row, col = int(match.group(1)), int(match.group(2))
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return self.invalid("The specified row and column coordinates are out of bounds.")
        if self.revealed[row][col]:
            return self.invalid(f"The cell at ({row}, {col}) has already been revealed.")

        was_first_move = self.first_move
        if was_first_move:  ## Handle the first move
            self.clear_all_flags()
            self.setup_mines(row, col)
            self.initial_move_pos = (row, col)
            self.first_move = False

        if self.grid[row][col] == -1:
            # Choosing a mine is a legal losing action, not a retryable format
            # error. Reveal it so the terminal board explains the outcome.
            self.revealed[row][col] = True
            self.broadcast(
                f"You hit a mine at ({row}, {col}).",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            self.game_state["rendered_board"] = self._render_board()
            return self.outcome(
                {0: self._get_percentage_completion()},
                reason=f"You hit a mine at ({row}, {col}). Game over.",
            )

        queue = deque([(row, col)])  # Start with the initial cell in the queue
        self.revealed[row][col] = True
        while queue:
            current_row, current_col = queue.popleft()
            # If the cell has no adjacent mines, add its neighbors to the queue
            if self.grid[current_row][current_col] == 0:
                for dr, dc in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                    neighbor_row, neighbor_col = current_row + dr, current_col + dc
                    if 0 <= neighbor_row < self.rows and 0 <= neighbor_col < self.cols:
                        if not self.revealed[neighbor_row][neighbor_col]:
                            self.revealed[neighbor_row][neighbor_col] = True
                            queue.append((neighbor_row, neighbor_col))

        if was_first_move:
            self.game_state["initial_revealed"] = [
                revealed_row[:] for revealed_row in self.revealed
            ]
        self.broadcast(f"You revealed the cell at ({row}, {col}).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.game_state["rendered_board"] = self._render_board()

        if self._is_solved():
            return self.outcome({0: 1}, reason="Congratulations! You have successfully cleared the Minesweeper board.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        return self.outcome({0: pct_complete}, reason=f"The turn limit has been reached. You successfully uncovered {round(pct_complete * 100)}% of the safe cells.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_percentage_completion(self) -> float:
        """ Return the percentage of safe (non-mine) cells that have been revealed after the safe zone """
        if self.first_move:
            # If no moves have been made yet, return 0
            return 0.0

        initial_revealed = self.game_state.get("initial_revealed")
        if initial_revealed is None:
            initial_row, initial_col = self.initial_move_pos
            initial_revealed = self._initial_reveal_mask(initial_row, initial_col)

        # Count total safe cells that were not part of the initial reveal.
        safe_total_after_initial = 0
        revealed_safe_after_initial = 0

        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] != -1:  # Safe cell
                    if not initial_revealed[r][c]:
                        safe_total_after_initial += 1
                        if self.revealed[r][c]:
                            revealed_safe_after_initial += 1

        if safe_total_after_initial == 0:
            return 1.0 if self._is_solved() else 0.0
        return revealed_safe_after_initial / safe_total_after_initial

    def _was_in_initial_safe_zone(self, row: int, col: int) -> bool:
        """ Check if a cell would have been revealed in the initial safe zone """
        if self.initial_move_pos is None:
            return False

        initial_row, initial_col = self.initial_move_pos

        # Check if the cell is within the 3x3 safe zone around the initial move
        if (initial_row - 1 <= row <= initial_row + 1 and
                initial_col - 1 <= col <= initial_col + 1):
            return True

        # Also check if it would have been auto-revealed due to flood-fill from a 0 cell
        return self._would_be_revealed_initially(row, col, initial_row, initial_col)

    def _would_be_revealed_initially(self, target_row: int, target_col: int, start_row: int, start_col: int) -> bool:
        """ Simulate what cells would be revealed from the initial move """
        return self._initial_reveal_mask(start_row, start_col)[target_row][target_col]

    def _initial_reveal_mask(
        self, start_row: int, start_col: int
    ) -> List[List[bool]]:
        """Compute the first-click flood fill once for completion scoring."""
        temp_revealed = [[False for _ in range(self.cols)] for _ in range(self.rows)]
        queue = deque([(start_row, start_col)])
        temp_revealed[start_row][start_col] = True

        while queue:
            current_row, current_col = queue.popleft()
            if self.grid[current_row][current_col] == 0:
                for dr, dc in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
                    neighbor_row, neighbor_col = current_row + dr, current_col + dc
                    if 0 <= neighbor_row < self.rows and 0 <= neighbor_col < self.cols:
                        if not temp_revealed[neighbor_row][neighbor_col] and self.grid[neighbor_row][neighbor_col] != -1:
                            temp_revealed[neighbor_row][neighbor_col] = True
                            queue.append((neighbor_row, neighbor_col))

        return temp_revealed

    def setup_mines(self, safe_row: int, safe_col: int):
        candidates = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if (
                r < safe_row - 1
                or r > safe_row + 1
                or c < safe_col - 1
                or c > safe_col + 1
            )
        ]
        if self.num_mines > len(candidates):
            raise ValueError(
                "num_mines exceeds the cells available outside the first-move safe zone"
            )
        for r, c in self.rng.sample(candidates, self.num_mines):
            self.grid[r][c] = -1
        self.calculate_adjacent_numbers()

    def calculate_adjacent_numbers(self):
        directions = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == -1:
                    continue
                self.grid[r][c] = 0
                mine_count = sum((0 <= r + dr < self.rows and 0 <= c + dc < self.cols and self.grid[r + dr][c + dc] == -1) for dr, dc in directions)
                self.grid[r][c] = mine_count

    def clear_all_flags(self):
        self.flags = [[False for _ in range(self.cols)] for _ in range(self.rows)]

    def _is_solved(self) -> bool:
        # Win condition: all non-mine cells are revealed
        return all(self.revealed[r][c] for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] != -1)
