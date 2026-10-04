import re, copy, string
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import textarena as ta
from textarena.envs.WordSearch.renderer import create_board_str
from textarena.utils.word_lists import get_common_words, get_headwords


class WordSearchEnv(ta.GameEnv):
    """ Word Search environment """

    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    snapshot_excluded_attributes = ("word_list",)
    MAX_INCORRECT_TRIES = 20
    MAX_COORDINATE_DIGITS = 6
    _ACTION_RE = re.compile(r"(?P<start_row>\d+)\s+(?P<start_col>\d+)\s+(?P<end_row>\d+)\s+(?P<end_col>\d+)")

    def __init__(self, hardcore: Optional[bool] = False, max_turns: Optional[int] = None):
        """
        Initialize the Word Search environment.

        Args:
            hardcore: Draw the words from every dictionary headword instead of the common words.
            max_turns: Optional cap on the total number of guesses, correct or not. The default,
                num_words + MAX_INCORRECT_TRIES, is never reached: the game ends at the last word
                or the last incorrect attempt first.
        """
        if not isinstance(hardcore, bool):
            raise ValueError("hardcore must be a boolean")
        if max_turns is not None and (not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1):
            raise ValueError("max_turns must be a positive integer or None")
        self.hardcore = hardcore
        self.num_words = 5
        self.max_turns = self.num_words + self.MAX_INCORRECT_TRIES if max_turns is None else max_turns

        self.word_list = [word.upper() for word in sorted(get_headwords() if self.hardcore else get_common_words())]

    # Convenience accessors kept for renderers/tests; game data lives in game_state.
    @property
    def placed_words(self) -> Dict[str, Tuple[int, int, str]]:
        return self.game_state["placed_words"]

    @property
    def correct_words(self) -> Set[str]:
        return self.game_state["correct_words"]

    @property
    def incorrect_attempts(self) -> List[Tuple[int, int, int, int]]:
        return self.game_state["incorrect_attempts"]

    @property
    def highlighted_positions(self) -> Set[Tuple[int, int]]:
        return self.game_state["highlighted_positions"]

    @property
    def num_incorrect_tries(self) -> int:
        return self.game_state["num_incorrect_tries"]

    @property
    def attempted_coordinates(self) -> Set[Tuple[int, int, int, int]]:
        return self.game_state["attempted_coordinates"]

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def setup(self) -> Dict[str, Any]:
        board, placed_words = self._generate_word_search()
        game_state = {
            "board": copy.deepcopy(board),
            "placed_words": placed_words,
            "correct_words": set(),
            "incorrect_attempts": [],
            "highlighted_positions": set(),
            "attempted_coordinates": set(),
            "num_incorrect_tries": self.MAX_INCORRECT_TRIES,
        }
        game_state["rendered_board"] = self._render_board(board, highlighted_positions=game_state["highlighted_positions"])
        return game_state

    def prompt(self, player_id: int) -> str:
        """ Generate the player prompt """
        prompt = (
            f"You are Player {player_id}, and you are participating in a Word Search challenge "
            f"modeled as {'Hardcore' if self.hardcore else 'Basic'}. The objective is to find and highlight hidden words "
            f"on the grid below. The rows and columns are numbered for your reference.\n\n"
            "Here is the current state of the Word Search board:\n"
            "----------------------------------------\n"
            "Words you have already found are marked in square brackets [ ]. Each row and column is numbered for clarity.\n"
        )
        prompt += (
            "\n\nTo locate a word, specify the row and column of its start and end letters. Note that words are either across or down.\n"
            "You may only submit one guess at a time. For your submissions, use the format 'start_row start_col end_row end_col'.\n"
            "For instance, if you want to find the word 'HELLO' starting at row 1, column 1 and ending at row 1, column 5, enter '1 1 1 5'.\n"
            "\nGuidelines:\n"
            "- Each guess must be unique; you cannot repeat the same guess.\n"
            f"- You have a total of {self.MAX_INCORRECT_TRIES} incorrect attempts. Correct guesses do not use them up; "
            "the game ends when you have found every word or used all incorrect attempts.\n"
        )
        if self.max_turns < self.num_words + self.MAX_INCORRECT_TRIES:
            prompt += f"- The game also ends after {self.max_turns} guesses in total, correct or incorrect.\n"
        prompt += (
            "- The history of your attempts will be recorded below.\n\n"
            f"Make your guesses carefully and strategically. Good luck, Player {player_id}! Let's see how many words you can find!\n"
        )
        return prompt

    def render(self, player_id: int) -> str:
        return (
            f"Current Board:\n\n{self._render_board(self.game_state['board'], show_words=True)}\n"
            f"Placed Words: {', '.join(self.placed_words.keys())}\n"
            f"Incorrect Attempts Remaining: {self.num_incorrect_tries}"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        match = self._ACTION_RE.fullmatch(action)
        if not match:
            return self.invalid(f"Invalid move format. Player {player_id} did not respond with valid 'start_row start_col end_row end_col'.")

        coordinate_values = (
            match.group("start_row"),
            match.group("start_col"),
            match.group("end_row"),
            match.group("end_col"),
        )
        if any(len(value) > self.MAX_COORDINATE_DIGITS for value in coordinate_values):
            return self.invalid("Invalid move. One or more coordinates are out of bounds.")

        coords = [
            (
                int(coordinate_values[0]),
                int(coordinate_values[1]),
                int(coordinate_values[2]),
                int(coordinate_values[3]),
            )
        ]

        # Validate everything up-front so no state is mutated before an invalid return.
        for start_row, start_col, end_row, end_col in coords:
            if not (0 <= start_row < len(gs["board"])
                    and 0 <= start_col < len(gs["board"][0])
                    and 0 <= end_row < len(gs["board"])
                    and 0 <= end_col < len(gs["board"][0])):
                return self.invalid(f"Invalid move format. Player {player_id} did not respond with valid 'start_row start_col end_row end_col'.")
            coordinate = (start_row, start_col, end_row, end_col)
            reverse = (end_row, end_col, start_row, start_col)
            if coordinate in gs["attempted_coordinates"] or reverse in gs["attempted_coordinates"]:
                return self.invalid("Invalid move. The action has already been attempted.")

        for start_row, start_col, end_row, end_col in coords:
            coordinate = (start_row, start_col, end_row, end_col)
            gs["attempted_coordinates"].add(coordinate)
            word_found = self._map_coordinate_to_word(start_row, start_col, end_row, end_col)
            if word_found is None:
                ## action is incorrect
                gs["incorrect_attempts"].append(coordinate)
                gs["num_incorrect_tries"] -= 1
                message = f"'{start_row} {start_col} {end_row} {end_col}' is an incorrect attempt. {gs['num_incorrect_tries']} incorrect tries remaining."
                self.message(player_id, message, ta.ObservationType.GAME_MESSAGE)
                if gs["num_incorrect_tries"] == 0:
                    gs["rendered_board"] = self._render_board(gs["board"], show_words=True)
                    reward = round(len(gs["correct_words"]) / len(gs["placed_words"]), 3)
                    reason = f"No more incorrect tries remaining. You found {len(gs['correct_words'])} out of {len(gs['placed_words'])} words ({round(reward * 100)}%)."
                    return self.outcome({0: reward}, reason=reason)
                break
            else:
                ## action is correct
                gs["correct_words"].add(word_found)
                self._highlight_word(start_row, start_col, end_row, end_col)
                message = f"'{start_row} {start_col} {end_row} {end_col}' is a correct attempt. You found the word '{word_found}'."
                self.message(player_id, message, ta.ObservationType.GAME_MESSAGE)

        ## update the game board
        gs["rendered_board"] = self._render_board(gs["board"], show_words=True)

        if len(gs["correct_words"]) == len(gs["placed_words"]):
            return self.outcome({0: 1.0}, reason="Congratulations! You completed the Word Search puzzle.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        reason = f"The limit of {self.state.max_turns} guesses has been reached. You found {len(self.correct_words)} out of {len(self.placed_words)} words ({round(pct_complete * 100)}%)."
        return self.outcome({0: pct_complete}, reason=reason)

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _generate_word_search(self):
        """
        Generate a word search grid with the given words and their directions.

        Returns:
            List[List[str]]: The generated word search grid.
            Dict[str, Tuple[int, int, str]]: The placed words and their positions and directions.
        """
        ## sample the words
        sampled = self.rng.sample(self.word_list, self.num_words)
        sampled = sorted(sampled, key=lambda w: len(w), reverse=True)
        directions = {word: self.rng.choice(["across", "down"]) for word in sampled}

        grid_size = self._determine_initial_grid_size(sampled)
        grid = self._create_empty_grid(grid_size)

        placed_words = {}  # word: (row, col, direction), where 0 is the starting index

        for word in sampled:
            placed = False
            if not placed_words:  # First word
                # Place the first word in the center of the grid
                if directions[word] == "across":
                    row = grid_size // 2
                    col = (grid_size - len(word)) // 2
                else:
                    row = (grid_size - len(word)) // 2
                    col = grid_size // 2

                if self._can_place_word(grid, word, directions[word], row, col):
                    self._place_word_on_grid(grid, word, directions[word], row, col)
                    placed_words[word] = (row, col, directions[word])
                    placed = True

            else:
                # Attempt to find overlaps
                possible_positions = self._find_overlaps(word, grid, directions, placed_words)
                self.rng.shuffle(possible_positions)  # Randomize to add variability
                for pos in possible_positions:
                    row, col, direction = pos
                    if self._can_place_word(grid, word, direction, row, col):
                        self._place_word_on_grid(grid, word, direction, row, col)
                        placed_words[word] = (row, col, direction)
                        placed = True
                        break

            if not placed:
                # If no overlap placement is possible, try placing the word in any free position
                for row in range(grid_size):
                    for col in range(grid_size):
                        if self._can_place_word(grid, word, directions[word], row, col):
                            self._place_word_on_grid(grid, word, directions[word], row, col)
                            placed_words[word] = (row, col, directions[word])
                            placed = True
                            break
                    if placed:
                        break

        if len(placed_words) != len(sampled):
            raise RuntimeError("failed to place every sampled word-search word")

        # Fill the remaining grid with random letters
        self._fill_empty_cells(grid)
        return grid, placed_words

    def _determine_initial_grid_size(self, words):
        """Determine the initial size of the grid based on the length of the longest word."""
        max_length = max(len(word) for word in words)
        # Reserve enough untouched rows/columns for every sampled word. This
        # makes fallback placement total rather than seed-dependent when short
        # words have no compatible overlaps.
        return max(round(max_length * 1.5), max_length + len(words))

    def _create_empty_grid(self, size):
        """Create an empty grid of the specified size."""
        return [["." for _ in range(size)] for _ in range(size)]

    def _can_place_word(self, grid, word, direction, row, col):
        """Check if a word can be placed on the grid at the specified position."""
        if (
            direction not in {"across", "down"}
            or not grid
            or not grid[0]
            or row < 0
            or col < 0
            or row >= len(grid)
            or col >= len(grid[0])
        ):
            return False
        if direction == "across":
            if col + len(word) > len(grid[0]):
                return False
            for i, letter in enumerate(word):
                current_cell = grid[row][col + i]
                if current_cell != "." and current_cell != letter:
                    return False
        else:  # "down"
            if row + len(word) > len(grid):
                return False
            for i, letter in enumerate(word):
                current_cell = grid[row + i][col]
                if current_cell != "." and current_cell != letter:
                    return False

        return True

    def _place_word_on_grid(self, grid, word, direction, row, col):
        """Place a word on the grid at the specified position."""
        if direction == "across":
            for i, letter in enumerate(word):
                grid[row][col + i] = letter
        else:  # "down"
            for i, letter in enumerate(word):
                grid[row + i][col] = letter

    def _find_overlaps(self, word, grid, directions, placed_words):
        """
        Find all possible valid overlaps for the word with already placed words.

        Returns:
            List[Tuple[int, int, str]]: The list of possible overlaps (row, col, direction).
        """
        overlaps = []
        for placed_word, (p_row, p_col, p_direction) in placed_words.items():
            for i, letter in enumerate(word):
                for j, placed_letter in enumerate(placed_word):
                    if letter == placed_letter:
                        # Determine the possible position based on the direction of the placed word
                        if p_direction == 'across':
                            row = p_row - i
                            col = p_col + j
                            if directions[word] == 'down' and 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                                if self._can_place_word(grid, word, 'down', row, col):
                                    overlaps.append((row, col, 'down'))
                        elif p_direction == 'down':
                            row = p_row + j
                            col = p_col - i
                            if directions[word] == 'across' and 0 <= row < len(grid) and 0 <= col < len(grid[0]):
                                if self._can_place_word(grid, word, 'across', row, col):
                                    overlaps.append((row, col, 'across'))
        return overlaps

    def _fill_empty_cells(self, grid):
        """Fill empty cells with random letters."""
        for row in range(len(grid)):
            for col in range(len(grid[0])):
                if grid[row][col] == ".":
                    grid[row][col] = self.rng.choice(string.ascii_uppercase)

    def _render_board(self, grid, show_words=True, highlighted_positions: Optional[Set[Tuple[int, int]]] = None):
        """
        Print the grid with the words highlighted based on the stored highlighted positions.

        Returns:
            str: The rendered board as a string.
        """
        if highlighted_positions is None:
            highlighted_positions = self.highlighted_positions
        header = "   " + " ".join(f"C{i:02}" for i in range(len(grid)))
        lines = [header]
        for i, row in enumerate(grid):
            row_str = f"R{i:02} "
            for j, val in enumerate(row):
                if (i, j) in highlighted_positions:
                    row_str += f"[{val}] " if show_words else f" {val}  "
                else:
                    row_str += f" {val}  "
            lines.append(row_str)

        return "\n".join(lines)

    def _check_word(self, grid, start_row, start_col, end_row, end_col):
        """
        Check if the selected coordinates exactly match a placed word.

        Returns:
            bool: True if the word is correct, False otherwise.
        """
        return self._map_coordinate_to_word(start_row, start_col, end_row, end_col) is not None

    def _highlight_word(self, start_row, start_col, end_row, end_col):
        """Highlight a word's positions based on the start and end coordinates."""
        if start_row == end_row:  # Horizontal word
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                self.highlighted_positions.add((start_row, col))
        elif start_col == end_col:  # Vertical word
            for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
                self.highlighted_positions.add((row, start_col))

    def _extract_word(self, grid, start_row, start_col, end_row, end_col):
        """Extracts the word from the grid based on start and end coordinates."""
        if start_row == end_row:  # Horizontal word
            return "".join(grid[start_row][col] for col in range(min(start_col, end_col), max(start_col, end_col) + 1))
        elif start_col == end_col:  # Vertical word
            return "".join(grid[row][start_col] for row in range(min(start_row, end_row), max(start_row, end_row) + 1))
        else:
            return ""

    def _matches_position(self, word, row, col, direction, start_row, start_col, end_row, end_col):
        """Check if the provided start and end positions match a placed word's position."""
        expected_start = (row, col)
        if direction == "across":
            expected_end = (row, col + len(word) - 1)
        elif direction == "down":
            expected_end = (row + len(word) - 1, col)
        else:
            return False
        actual_start = (start_row, start_col)
        actual_end = (end_row, end_col)
        return (actual_start, actual_end) in {
            (expected_start, expected_end),
            (expected_end, expected_start),
        }

    def _map_coordinate_to_word(self, start_row: int, start_col: int, end_row: int, end_col: int) -> Union[str, None]:
        """Map the coordinates to the corresponding word if it exists."""
        for word, (row, col, direction) in self.placed_words.items():
            if self._matches_position(word, row, col, direction, start_row, start_col, end_row, end_col):
                return word
        return None

    def _get_percentage_completion(self) -> float:
        """Calculate the percentage of words found compared to the total number of words."""
        if not self.placed_words:
            return 0.0
        return len(self.correct_words) / len(self.placed_words)
