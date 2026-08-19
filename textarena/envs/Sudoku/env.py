import re, random, copy
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta
from textarena.envs.Sudoku.renderer import create_board_str

class SudokuEnv(ta.Env):
    def __init__(self, clues: int= 30, max_turns: Optional[int] = 100):
        """
        Args:
            clues (str): The number of clues.
            max_turns (int): The maximum number of moves allowed.
        """
        self.clues = clues
        self.max_turns = max_turns

    def get_board_str(self): return create_board_str(board=self.game_board)
    def _generate_board(self) -> List[List[int]]:
        full_grid = self._generate_full_grid() ## generate a full grid
        puzzle_grid = self._remove_cells(full_grid, self.clues) ## remove cells to create puzzle
        return full_grid, puzzle_grid
    
    def _generate_full_grid(self) -> List[List[int]]:
        grid = [[0 for _ in range(9)] for _ in range(9)]
        self._fill_grid(grid)
        return grid

    def _fill_grid(self, grid: List[List[int]]) -> bool:
        empty = self._find_empty(grid)
        if not empty: return True  # Grid is complete
        row, col = empty

        numbers = list(range(1, 10))
        random.shuffle(numbers)
        for num in numbers:
            if self.is_safe(grid, row, col, num):
                grid[row][col] = num
                if self._fill_grid(grid): return True
                grid[row][col] = 0
        return False
    
    def _find_empty(self, grid: List[List[int]]) -> Optional[Tuple[int, int]]:
        for i in range(9):
            for j in range(9):
                if grid[i][j] == 0:
                    return (i, j)
        return None

    def is_safe(self, grid: List[List[int]], row: int, col: int, num: int) -> bool:
        # Check row
        if num in grid[row]: return False
        # Check column
        if num in [grid[i][col] for i in range(9)]: return False
        # Check subgrid
        start_row, start_col = 3 * (row // 3), 3 * (col // 3)
        for i in range(start_row, start_row + 3):
            for j in range(start_col, start_col + 3):
                if grid[i][j] == num:
                    return False
        return True

    def _remove_cells(self, grid: List[List[int]], clues: int) -> List[List[int]]:
        puzzle = copy.deepcopy(grid)
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)

        while len(cells) > clues:
            row, col = cells.pop()
            removed = puzzle[row][col]
            puzzle[row][col] = 0

            # Make a copy to check for uniqueness
            grid_copy = copy.deepcopy(puzzle)
            solutions = []
            self._count_solutions(grid_copy, solutions)
            if len(solutions) != 1:
                # Not unique, revert the removal
                puzzle[row][col] = removed
        return puzzle

    def _solve_sudoku(self, grid: List[List[int]]) -> bool:
        empty = self._find_empty(grid)
        if not empty: return True  # Solved
        row, col = empty
        for num in range(1, 10):
            if self.is_safe(grid, row, col, num):
                grid[row][col] = num
                if self._solve_sudoku(grid):
                    return True
                grid[row][col] = 0
        return False

    def _count_solutions(self, grid: List[List[int]], solutions: List[List[List[int]]], limit: int = 2) -> int:
        if len(solutions) >= limit: return len(solutions)
        empty = self._find_empty(grid)
        if not empty:
            solutions.append(copy.deepcopy(grid))
            return len(solutions)
        row, col = empty

        for num in range(1, 10):
            if self.is_safe(grid, row, col, num):
                grid[row][col] = num
                self._count_solutions(grid, solutions, limit)
                grid[row][col] = 0
        return len(solutions)
    
    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed) ## intitialise the game state
        self.full_grid, self.game_board = self._generate_board()
        game_state={"board": copy.deepcopy(self.game_board), "rendered_board": self._get_grid_string_with_indices(self.game_board), "completed": False}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self.state.add_observation(message=self.m("board", "game_board", board=self._get_grid_string_with_indices()), observation_type=ta.ObservationType.GAME_BOARD)
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)


    def step(self, action: str) -> Tuple[bool, ta.Info ]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) ## update the observation
        ## validate the actions
        ## extract the format [row column number] from the action
        action_search_pattern = re.compile(r"\[(\d+)\s(\d+)\s(\d+)\]")
        match = action_search_pattern.search(action)

        if not match: self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format", player_id=player_id))
        else:
            row, col, num = map(int, match.groups())
            if row < 1 or row > 9 or col < 1 or col > 9 or num < 1 or num > 9:
                self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "out_of_bounds", player_id=player_id, num=num, row=row, col=col))
            else:
                row_idx, col_idx = row - 1, col - 1
                ## check if the cell is already filled in the initial grid
                if self.state.game_state["board"][row_idx][col_idx] != 0:
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "overwrite", player_id=player_id, row=row, col=col))
                elif self._is_move_correct(row_idx, col_idx, num):
                    self.state.game_state["board"][row_idx][col_idx] = num ## update the grid
                    self.state.add_observation(message=self.m("board", "board_state", board=self._get_grid_string_with_indices()), observation_type=ta.ObservationType.GAME_BOARD) ## update the observation
                else:
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "violates_rules", player_id=player_id, num=num, row=row, col=col))

                ## check if the game is completed
                if self._is_puzzle_complete():
                    self.state.game_state["completed"] = True
                    self.state.set_outcome(reward=1, reason=self.m("outcome", "win", player_id=player_id))
                self.state.game_state["rendered_board"] = self._get_grid_string_with_indices(self.state.game_state["board"])

        # check turn count
        if self.state.check_turn_limit() and not self.state.done:
            pct_complete = self._get_percentage_completion()
            self.state.set_outcome(reward=pct_complete, reason=self.m("outcome", "turn_limit", percent=round(pct_complete * 100)))
        return self.state.step()
            
    def _get_grid_string_with_indices(self, game_board: Optional[List[int]] = None) -> str:
        if game_board is None: game_board = self.state.game_state["board"]
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
                num = self.state.game_state["board"][i][j]
                if num == 0 or not self._is_move_correct_complete(i, j, num):
                    return False
        return True
    
    def _is_move_correct_complete(self, row: int, col: int, num: int) -> bool:
        self.state.game_state["board"][row][col] = 0
        correct = self._is_move_correct(row, col, num)
        self.state.game_state["board"][row][col] = num
        return correct

    def _get_percentage_completion(self) -> float:
        correct = 0; total = 0
        for i in range(9):
            for j in range(9):
                if self.game_board[i][j] != 0: # Skip original clues
                    continue
                total += 1
                if self.state.game_state["board"][i][j] == self.full_grid[i][j]:
                    correct += 1
        return correct/total if total > 0 else 0.0