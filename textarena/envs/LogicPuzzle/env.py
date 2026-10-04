import re, copy, json, os
import importlib.resources
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import textarena as ta
from textarena.envs.LogicPuzzle.renderer import create_board_str


class LogicPuzzleEnv(ta.GameEnv):
    """ Logic Puzzle environment """

    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_action_chars = 4096

    difficulty = ta.Param("easy", "The set of bundled puzzles to draw from.", choices=("easy", "hard"))
    max_turns = ta.Param(30, "The maximum number of submissions.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.game_board_data = self._load_puzzle_data()

    def _load_puzzle_data(self, puzzle_path: Optional[str] = None):
        """
        Load puzzle data from a JSONL file.

        The JSONL file must have each line as a JSON object with at least a 'difficulty' field.

        Args:
            puzzle_path (str, optional): Path to the JSONL file containing puzzle data.

        Returns:
            list: A list of puzzle data objects filtered by the current difficulty level.

        Raises:
            FileNotFoundError: If the `puzzle_path` does not exist.
            ValueError: If the JSONL file has an invalid format or no matching puzzles are found.
        """
        if puzzle_path is not None:
            if not os.path.exists(puzzle_path):
                raise FileNotFoundError(f"Puzzle data file not found at: {puzzle_path}")
            with open(puzzle_path, "r", encoding="utf-8") as file:
                game_board_data = file.readlines()
        else:
            resource = importlib.resources.files("textarena.envs.LogicPuzzle").joinpath(
                "game_board_clues.jsonl"
            )
            with resource.open("r", encoding="utf-8") as file:
                game_board_data = file.readlines()

        filtered_data = []
        for line_number, line in enumerate(game_board_data, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid JSON on puzzle data line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(
                    f"Puzzle data line {line_number} must be a JSON object"
                )
            if str(record.get("difficulty", "")).lower() == self.difficulty:
                filtered_data.append(
                    self._validate_puzzle_record(record, line_number)
                )
        if not filtered_data:
            raise ValueError(f"No puzzles found matching difficulty '{self.difficulty}'.")
        return filtered_data

    @staticmethod
    def _validate_puzzle_record(record: Any, line_number: int) -> Dict[str, Any]:
        """Validate and normalize one record into parser-safe puzzle data."""
        if not isinstance(record, dict):
            raise ValueError(f"Puzzle data line {line_number} must be a JSON object")
        difficulty = record.get("difficulty")
        solution = record.get("solution")
        clues = record.get("clue")
        if not isinstance(difficulty, str) or not difficulty.strip():
            raise ValueError(
                f"Puzzle data line {line_number} has an invalid difficulty"
            )
        if not isinstance(solution, dict) or len(solution) < 2:
            raise ValueError(
                f"Puzzle data line {line_number} must contain at least two solution categories"
            )
        if (
            not isinstance(clues, list)
            or not clues
            or any(not isinstance(clue, str) or not clue.strip() for clue in clues)
        ):
            raise ValueError(f"Puzzle data line {line_number} has invalid clues")

        normalized_solution: Dict[str, List[str]] = {}
        expected_size: Optional[int] = None
        all_items: Set[str] = set()
        for category, items in solution.items():
            if not isinstance(category, str) or not category.strip():
                raise ValueError(
                    f"Puzzle data line {line_number} has an invalid category name"
                )
            if (
                not isinstance(items, list)
                or len(items) < 2
                or any(
                    not isinstance(item, str)
                    or re.fullmatch(r"[A-Za-z]+", item) is None
                    for item in items
                )
            ):
                raise ValueError(
                    f"Puzzle data line {line_number} has parser-incompatible solution items"
                )
            normalized_items = [item.lower() for item in items]
            if len(set(normalized_items)) != len(normalized_items):
                raise ValueError(
                    f"Puzzle data line {line_number} has duplicate solution items"
                )
            if expected_size is None:
                expected_size = len(normalized_items)
            elif len(normalized_items) != expected_size:
                raise ValueError(
                    f"Puzzle data line {line_number} has unequal category sizes"
                )
            if all_items.intersection(normalized_items):
                raise ValueError(
                    f"Puzzle data line {line_number} has ambiguous items across categories"
                )
            all_items.update(normalized_items)
            normalized_solution[category.lower()] = normalized_items

        normalized = copy.deepcopy(record)
        normalized["difficulty"] = difficulty.lower()
        normalized["solution"] = normalized_solution
        return normalized

    @property
    def game_board(self) -> Dict[str, Dict[str, Dict[str, Any]]]: return self.game_state["board"]

    @property
    def game_board_solution(self) -> Dict[str, Dict[str, Dict[str, str]]]: return self.game_state["solution"]

    @property
    def clues(self) -> List[str]: return self.game_state["clues"]

    @property
    def action_format(self) -> str:
        grid = next(iter(self.game_board.values()))
        row = next(iter(grid))
        col = next(iter(grid[row]))
        return (
            "a row label, a column label and the mark X or O, with several marks separated by commas, "
            f"for example '{row} {col} X'"
        )

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        selected_game_board = self.rng.choice(self.game_board_data)
        solution = selected_game_board["solution"]
        clues = selected_game_board["clue"]
        game_board, game_board_solution = self._create_game_board(solution)
        return {"board": game_board, "solution": game_board_solution, "clues": clues}

    def _create_game_board(self, solution: Dict[str, List[str]]):
        """
        Create the game board for the logic puzzle based on the solution.

        Args:
            solution (Dict[str, List[str]]): The solution for the logic puzzle.

        Returns:
            Dict[str, Dict[str, Dict[str, Any]]]: The game board data.
            Dict[str, Dict[str, Dict[str, str]]]: The game board solution data.
        """
        game_board = {}
        game_board_solution = {}
        categories = list(solution.keys())
        index = self.rng.choice(categories)
        for category in categories:
            if category != index:
                shuffled_items = solution[category][:]
                self.rng.shuffle(shuffled_items)
                game_board[f"{index}_{category}"] = {name: {item: None for item in shuffled_items} for name in solution[index]}
                game_board_solution[f"{index}_{category}"] = {name: {item: "O" if item == solution[category][solution[index].index(name)] else "X" for item in shuffled_items} for name in solution[index]}
        return game_board, game_board_solution

    def prompt(self, player_id: int) -> str:
        grid_name, grid = next(iter(self.game_board.items()))
        row = next(iter(grid))
        col = next(iter(grid[row]))
        return (
            f"You are Player {player_id} in the Logic Puzzle game.\n"
            "Your goal is to solve the puzzle by deducing from the clues which items belong together.\n"
            "Each grid pairs two categories: its rows are labeled with the items of one and its columns with the items of the other.\n"
            "\n"
            "To make a move, give the row label, then the column label, then the mark ('X' or 'O').\n"
            "Use the format: 'row col X' or 'row col O', where:\n"
            "- 'O' indicates the row item and the column item belong together.\n"
            "- 'X' indicates they do not.\n"
            "\n"
            f"Example: to mark a cell in the '{grid_name}' grid, enter '{row} {col} X' or '{row} {col} O'.\n"
            "Labels are not case-sensitive. Each row and each column of a grid has exactly one 'O'.\n"
            "The puzzle is solved once every cell of every grid holds the correct mark, including an 'X' in every non-matching cell.\n"
            "\n"
            "Note:\n"
            "- You may change a mark by marking the cell again with the other symbol; repeating a cell's current mark is invalid.\n"
            "- You may submit multiple marks separated by commas; the full batch is validated before any marks are applied, "
            "and one invalid mark rejects the whole batch.\n"
            f"- You have {self.max_turns} turns, and each submission uses one turn.\n"
            "- An invalid move changes nothing and you may try again, but two invalid moves in a row end the game."
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n\n{self._render_board(self.game_board)}\nAvailable Clues:\n{self._return_clues()}"

    def _render_board(self, game_board: Dict[str, Dict[str, Dict[str, Any]]]) -> str:
        """ Render the game board as a string """
        output = []
        for grid_name, grid_data in game_board.items():
            items = list(next(iter(grid_data.values())).keys())  ## get the column headers
            ## calculate the maximum width needed for headers and each row name
            max_name_width = max(len(name) for name in grid_data.keys()) + 2
            max_col_width = max(len(item) for item in items) + 2

            ## add grid name with a separator
            output.append(f"\n{'=' * (max_name_width + max_col_width * len(items) + len(items) + 5)}")
            output.append(f"{grid_name.center(max_name_width + max_col_width * len(items) + len(items) + 5)}")
            output.append(f"{'=' * (max_name_width + max_col_width * len(items) + len(items) + 5)}")

            ## add column headers with border
            output.append(" " * max_name_width + " | ".join(f"{item:^{max_col_width}}" for item in items) + " |")
            output.append("-" * (max_name_width + len(items) * (max_col_width + 3) - 1))

            for name, marks in grid_data.items():  ## add each row with values and borders
                row = f"{name:<{max_name_width}}" + " | ".join(f"{marks[item] if marks[item] else ' ':^{max_col_width}}" for item in items)
                output.append(f"{row} |")
            output.append("=" * (max_name_width + len(items) * (max_col_width + 3) - 1))  ## add a separator after each grid for clarity
        return "\n".join(output)

    def _return_clues(self):
        """ Return the clues in a formatted string """
        return "\n".join([f"- {clue}" for clue in self.clues])

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        raw_actions = [part.strip() for part in action_text.split(",")]
        action_pattern = re.compile(r"([a-zA-Z]+)\s+([a-zA-Z]+)\s+([XOxo])")
        if not raw_actions or any(not part for part in raw_actions):
            return self._format_error(f"Invalid move format. Player {player_id} did not respond with a valid 'row col X|O' move.")
        matches = []
        for raw_action in raw_actions:
            match = action_pattern.fullmatch(raw_action)
            if match is None:
                return self._format_error(
                    f"Invalid move format. Player {player_id} did not respond "
                    "with comma-separated 'row col X|O' moves."
                )
            matches.append(match.groups())

        # Validate the complete batch against a projected view first. Returning
        # Invalid must never leave earlier marks from the same action behind.
        projected_marks: Dict[Tuple[str, str], Optional[str]] = {}
        for match in matches:
            row, col, mark = match
            row, col, mark = row.lower(), col.lower(), mark.upper()
            if not self._is_within_bounds(row, col):
                if self._is_within_bounds(col, row):
                    return self.invalid(
                        f"Invalid move. '{row}' is a column label and '{col}' a row label; "
                        f"give the row first: '{col} {row} {mark}'."
                    )
                return self.invalid(
                    "Invalid move. The item is not within the bounds of the grid."
                )
            key = (row, col)
            current_mark = projected_marks.get(key, self._get_mark(row, col))
            if current_mark == mark:
                return self.invalid(
                    "Invalid move. The item has already been marked with the same value."
                )
            projected_marks[key] = mark

        for row, col, mark in (
            (row.lower(), col.lower(), mark.upper()) for row, col, mark in matches
        ):
            self._mark_item(row, col, mark)
            self.message(
                player_id,
                f"Marked '{row} {col} {mark}'.",
                ta.ObservationType.GAME_MESSAGE,
            )

        if self._is_solved():
            return self.outcome({0: 1}, reason=f"Congratulations! Player {player_id} has solved the logic puzzle!")
        return None

    def _format_error(self, reason: str) -> ta.Invalid:
        # This game parses in apply() instead of setting action_pattern, so it appends the hint itself.
        return self.invalid(f"{reason} Expected {self.action_format}.")

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        return self.outcome({0: pct_complete}, reason=f"The turn limit has been reached. You correctly marked {round(pct_complete * 100)}% of the puzzle.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_percentage_completion(self) -> float:
        """
        Compute the percentage of correctly filled cells across all subgrids.
        Every cell (O or X) in the solution counts toward total.
        Only exact matches between player mark and solution mark count as correct.
        """
        correct = 0
        total = 0
        for grid_name, solution_data in self.game_board_solution.items():
            grid_data = self.game_board.get(grid_name)
            if grid_data is None:
                continue

            for row_name, solution_row in solution_data.items():
                player_row = grid_data.get(row_name)
                if player_row is None:
                    continue

                for col_name, solution_mark in solution_row.items():
                    player_mark = player_row.get(col_name)
                    if solution_mark in ("O", "X"):
                        total += 1
                        if player_mark == solution_mark:
                            correct += 1

        return correct / total if total > 0 else 0.0

    def _is_within_bounds(self, row: str, col: str) -> bool:
        """ Check if the specified item is within the bounds of the game board """
        for grid_name, grid_data in self.game_board.items():
            if row in grid_data:
                if col in grid_data[row]:
                    return True
        return False

    def _is_repeated_mark(self, row: str, col: str, mark: str) -> bool:
        """ Check if the specified item in the game board is already marked with the same value """
        for grid_name, grid_data in self.game_board.items():
            if row in grid_data:
                if col in grid_data[row]:
                    if grid_data[row][col] == mark:
                        return True
        return False

    def _get_mark(self, row: str, col: str) -> Optional[str]:
        """Return the current mark for a valid row/column pair."""
        for grid_data in self.game_board.values():
            if row in grid_data and col in grid_data[row]:
                return grid_data[row][col]
        return None

    def _mark_item(self, row: str, col: str, mark: str):
        """ Mark the specified item in the game board """
        for grid_name, grid_data in self.game_board.items():
            if row in grid_data:
                if col in grid_data[row]:
                    grid_data[row][col] = mark

    def _is_solved(self) -> bool:
        """ Compares grids with grids_solution to check if they are the same """
        for grid_name, grid_data in self.game_board.items():
            solution_data = self.game_board_solution.get(grid_name)
            if solution_data is None:
                return False

            for name, items in grid_data.items():
                solution_items = solution_data.get(name)
                if solution_items is None:
                    return False

                for item, value in items.items():
                    solution_value = solution_items.get(item)
                    if solution_value is None:
                        return False
                    if value != solution_value:
                        return False

        return True
