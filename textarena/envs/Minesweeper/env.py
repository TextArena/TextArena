import re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Minesweeper.renderer import create_board_str


class MinesweeperEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_grid_cells = 10_000
    max_action_chars = 4096

    rows = ta.Param(8, "The number of rows. The board can have at most 10,000 cells.", min=1)
    cols = ta.Param(8, "The number of columns.", min=1)
    num_mines = ta.Param(
        10, "The number of mines. It must leave room for the mine-free area around the first reveal, so it can be at "
            "most `rows × cols − 9` on boards of at least 3×3.", min=0,
    )
    max_turns = ta.Param(100, "The maximum number of reveals.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.rows * self.cols > self.max_grid_cells:
            raise ValueError(
                f"rows and cols create more than {self.max_grid_cells} cells"
            )
        max_safe_zone = min(3, self.rows) * min(3, self.cols)
        max_mines = self.rows * self.cols - max_safe_zone
        if self.num_mines > max_mines:
            raise ValueError(
                f"num_mines must be at most {max_mines} so every first move "
                "can have a mine-free 3x3 safe zone"
            )

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
        example_row, example_col = self.rows // 2, self.cols // 2
        return (
            f"You are playing Minesweeper on a {self.rows}x{self.cols} grid with {self.num_mines} hidden mines.\n"
            "The objective of the game is to reveal every cell that does not contain a mine.\n"
            f"Rows are numbered 0 to {self.rows - 1} from top to bottom and columns 0 to {self.cols - 1} from left "
            "to right, as labeled on the board.\n"
            f"On your turn, reveal one hidden cell by replying with 'row col'. For example, '{example_row} {example_col}' "
            f"reveals the cell in row {example_row}, column {example_col}.\n"
            "Hidden cells are shown as '.'. A revealed cell shows how many of its eight neighbors contain mines, "
            "and revealing a 0 automatically reveals its neighbors as well.\n"
            "Your first reveal is always safe: no mine is placed on or next to the first cell you choose.\n"
            "Revealing a mine ends the game.\n"
            f"You have {self.max_turns} turns; each reveal uses one turn.\n"
            "Choosing a cell outside the board, an already revealed cell, or a malformed reply is an invalid move. "
            "It changes nothing and you may try again, but two invalid moves in a row end the game."
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n\n{self.get_board_str()}"

    def _render_board(self) -> str:
        """Render the game board using the public renderer."""
        return create_board_str(self.grid, self.revealed, self.flags)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        action_text = move.strip()
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
