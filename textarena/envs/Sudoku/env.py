import re, copy
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Sudoku.renderer import create_board_str


class SudokuEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    max_action_chars = 4096

    def __init__(self, clues: int = 30, max_turns: Optional[int] = 100):
        """
        Args:
            clues (int): The exact number of initially filled cells.
            max_turns (int): The maximum number of moves allowed.
        """
        if (
            not isinstance(clues, int)
            or isinstance(clues, bool)
            or not 17 <= clues <= 80
        ):
            raise ValueError(f"clues must be between 17 and 80, received {clues}")
        if (
            not isinstance(max_turns, int)
            or isinstance(max_turns, bool)
            or max_turns <= 0
        ):
            raise ValueError("max_turns must be a positive integer")
        self.clues = clues
        self.max_turns = max_turns

    @property
    def full_grid(self) -> List[List[int]]:
        return self.game_state["full_grid"]

    @property
    def game_board(self) -> List[List[int]]:
        return self.game_state["initial_board"]

    def get_board_str(self): return create_board_str(board=self.game_state["board"])

    def setup(self) -> Dict[str, Any]:
        full_grid, puzzle_grid = self._generate_board()
        return {
            "board": copy.deepcopy(puzzle_grid),
            "rendered_board": create_board_str(puzzle_grid),
            "completed": False,
            "full_grid": full_grid,
            "initial_board": puzzle_grid,
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id}. You are playing Sudoku.\n"
            "Here is the current state of the Sudoku grid. Each row is numbered from 1 to 9, and each column is also numbered from 1 to 9.\n"
            "Empty cells are represented by '.', and pre-filled cells contain digits from 1 to 9.\n\n"
            "Current Sudoku Grid:\n"
            "Your objective is to fill the empty cells in the 9x9 grid with digits from 1 to 9 such that:\n"
            "1. Each row contains all digits from 1 to 9 without repetition.\n"
            "2. Each column contains all digits from 1 to 9 without repetition.\n"
            "3. Each of the nine 3x3 subgrids contains all digits from 1 to 9 without repetition.\n\n"
            "Rules and Instructions:\n"
            "1. **Do not overwrite** the initial numbers provided in the grid.\n"
            "2. **Only fill** empty cells represented by '.'.\n"
            "3. Reply with your move in the format 'row column number', e.g. '5 3 7'.\n"
            "4. **Ensure** that your move does not violate Sudoku rules. Invalid moves will result in penalties.\n"
            "Examples:\n"
            "- **Valid Move**:\n"
            "  - Grid Snippet Before Move:\n"
            "  \n"
            "  - Move: `5 3 7`\n"
            "  - Explanation: Placing 7 at row 5, column 3 does not violate any Sudoku rules.\n\n"
            "- **Invalid Move** (Overwriting a pre-filled cell):\n"
            "  - Grid Snippet Before Move:\n"
            "  \n"
            "  - Move: `1 1 9`\n"
            "  - Explanation: Cell (1,1) is already filled with 5. You cannot overwrite it.\n\n"
            "- **Invalid Move** (Violating Sudoku rules):\n"
            "  - Grid Snippet Before Move:\n"
            "  \n"
            "  - Move: `1 3 5`\n"
            "  - Explanation: Placing 5 in row 1, column 3 violates the rule since 5 already exists in row 1.\n\n"
            "The history of your moves and thoughts will be appended as you play more rounds. Use the history of your move to improve your decision making by avoiding the moves you have tried. Good luck!\n\n"
        )

    def render(self, player_id: int) -> str:
        return f"Board state: \n{self.get_board_str()}"

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        if action_text.startswith("[") or action_text.endswith("]"):
            if not (action_text.startswith("[") and action_text.endswith("]")):
                return self.invalid("Invalid move format: mismatched brackets.")
            action_text = action_text[1:-1].strip()
        match = re.fullmatch(
            r"(\d+)\s*[,\s]\s*(\d+)\s*[,\s]\s*(\d+)",
            action_text,
        )
        if not match:
            return self.invalid(f"Invalid move format. Player {player_id} did not respond with valid 'row column number'.")

        row, col, num = map(int, match.groups())
        if row < 1 or row > 9 or col < 1 or col > 9 or num < 1 or num > 9:
            return self.invalid(f"Invalid move. Player {player_id} attempted to place {num} at ({row}, {col}), which is out of bounds.")

        row_idx, col_idx = row - 1, col - 1
        board = self.game_state["board"]
        if board[row_idx][col_idx] != 0:
            return self.invalid(f"Invalid move. Player {player_id} attempted to overwrite a pre-filled cell ({row}, {col}).")
        if not self._is_move_correct(row_idx, col_idx, num):
            return self.invalid(f"Invalid move. Player {player_id} attempted to place {num} at ({row}, {col}), which violates Sudoku rules.")

        board[row_idx][col_idx] = num
        self.game_state["rendered_board"] = create_board_str(board)

        if self._is_puzzle_complete():
            self.game_state["completed"] = True
            return self.outcome({0: 1}, reason=f"Congratulations! Player {player_id} completed the Sudoku puzzle.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        return self.outcome({0: pct_complete}, reason=f"The turn limit has been reached. You correctly filled {round(pct_complete * 100)}% of the empty cells.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    # ------------------------------------------------------- board generation
    def _generate_board(self) -> Tuple[List[List[int]], List[List[int]]]:
        # This is a known uniquely solvable 17-clue puzzle and its solution.
        # Digit, row, and column symmetries produce a large deterministic family
        # of equivalent puzzles without rerunning an expensive uniqueness search.
        base_puzzle = [
            [0, 0, 0, 0, 0, 0, 0, 1, 0],
            [4, 0, 0, 0, 0, 0, 0, 0, 0],
            [0, 2, 0, 0, 0, 0, 0, 0, 0],
            [0, 0, 0, 0, 5, 0, 4, 0, 7],
            [0, 0, 8, 0, 0, 0, 3, 0, 0],
            [0, 0, 1, 0, 9, 0, 0, 0, 0],
            [3, 0, 0, 4, 0, 0, 2, 0, 0],
            [0, 5, 0, 1, 0, 0, 0, 0, 0],
            [0, 0, 0, 8, 0, 6, 0, 0, 0],
        ]
        base_solution = [
            [6, 9, 3, 7, 8, 4, 5, 1, 2],
            [4, 8, 7, 5, 1, 2, 9, 3, 6],
            [1, 2, 5, 9, 6, 3, 8, 7, 4],
            [9, 3, 2, 6, 5, 1, 4, 8, 7],
            [5, 6, 8, 2, 4, 7, 3, 9, 1],
            [7, 4, 1, 3, 9, 8, 6, 2, 5],
            [3, 1, 9, 4, 7, 5, 2, 6, 8],
            [8, 5, 6, 1, 2, 9, 7, 4, 3],
            [2, 7, 4, 8, 3, 6, 1, 5, 9],
        ]

        digits = list(range(1, 10))
        self.rng.shuffle(digits)
        digit_map = {old: new for old, new in zip(range(1, 10), digits)}

        bands = [0, 1, 2]
        self.rng.shuffle(bands)
        row_order = []
        for band in bands:
            rows = [band * 3 + offset for offset in range(3)]
            self.rng.shuffle(rows)
            row_order.extend(rows)

        stacks = [0, 1, 2]
        self.rng.shuffle(stacks)
        col_order = []
        for stack in stacks:
            cols = [stack * 3 + offset for offset in range(3)]
            self.rng.shuffle(cols)
            col_order.extend(cols)

        def transform(grid: List[List[int]]) -> List[List[int]]:
            return [
                [digit_map[grid[row][col]] if grid[row][col] else 0 for col in col_order]
                for row in row_order
            ]

        full_grid = transform(base_solution)
        puzzle_grid = transform(base_puzzle)
        extra_positions = [
            (row, col)
            for row in range(9)
            for col in range(9)
            if puzzle_grid[row][col] == 0
        ]
        self.rng.shuffle(extra_positions)
        for row, col in extra_positions[: self.clues - 17]:
            puzzle_grid[row][col] = full_grid[row][col]
        return full_grid, puzzle_grid

    # ---------------------------------------------------------------- helpers
    def _get_grid_string_with_indices(self, game_board: Optional[List[List[int]]] = None) -> str:
        if game_board is None: game_board = self.game_state["board"]
        header = "   " + " ".join([f"C{j+1}" + ("  " if (j + 1) % 3 == 0 else "") for j in range(9)])  # Column headers
        lines = [header]
        for i, row in enumerate(game_board):
            row_str = f"R{i+1} "  # Row header
            for j, num in enumerate(row):
                cell = str(num) if num != 0 else "."
                row_str += f" {cell} "
                if (j + 1) % 3 == 0 and j < 8:
                    row_str += "| "
            lines.append(row_str.strip())
            if (i + 1) % 3 == 0 and i < 8:
                lines.append("   " + "- " * 16)
        return "\n".join(lines)

    def _is_move_correct(self, row: int, col: int, num: int) -> bool:
        return self.full_grid[row][col] == num

    def _is_puzzle_complete(self) -> bool:
        for i in range(9):
            for j in range(9):
                num = self.game_state["board"][i][j]
                if num == 0 or not self._is_move_correct_complete(i, j, num):
                    return False
        return True

    def _is_move_correct_complete(self, row: int, col: int, num: int) -> bool:
        return self._is_move_correct(row, col, num)

    def _get_percentage_completion(self) -> float:
        correct = 0; total = 0
        for i in range(9):
            for j in range(9):
                if self.game_board[i][j] != 0:  # Skip original clues
                    continue
                total += 1
                if self.game_state["board"][i][j] == self.full_grid[i][j]:
                    correct += 1
        return correct/total if total > 0 else 0.0
