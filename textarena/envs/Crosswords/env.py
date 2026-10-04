import os
import copy
import importlib.resources
import json
import re
from typing import Any, Dict, Optional, Union

import textarena as ta
from textarena.envs.Crosswords.renderer import create_board_str


class CrosswordsEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    MAX_COORDINATE_DIGITS = 6
    _ACTION_RE = re.compile(
        r"(?P<wrapped>\[)?\s*(?P<row>\d+)\s+(?P<col>\d+)"
        r"\s+(?P<letter>[A-Za-z])\s*(?(wrapped)\])"
    )

    def __init__(self, hardcore: Optional[bool] = False, max_turns: Optional[int] = 100, num_words: Optional[int] = 5):
        """
        Args:
            hardcore (Optional[bool]): Whether to use hardcore mode.
            max_turns (Optional[int]): Maximum total length of the sampled words, i.e. the most turns a game can take.
            num_words (Optional[int]): Number of words to use in the game.
        """
        if not isinstance(hardcore, bool):
            raise ValueError("hardcore must be a boolean")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        if not isinstance(num_words, int) or isinstance(num_words, bool) or num_words < 1:
            raise ValueError("num_words must be a positive integer")
        self.hardcore = hardcore
        # `max_turns` caps the puzzle size. Every accepted guess fills one letter cell, so a game can
        # never outlast it, and it is intentionally NOT assigned to self.max_turns (no engine turn limit).
        self.max_letters = max_turns
        self.num_words = num_words
        self._load_words(hardcore=hardcore)
        if self.num_words > len(self.word_data):
            raise ValueError("num_words exceeds the available word data")
        minimum_cells = sum(sorted(len(entry["word"]) for entry in self.word_data)[: self.num_words])
        if minimum_cells > self.max_letters:
            raise ValueError("max_turns is too small for the requested number of words")

    def get_board_str(self): return create_board_str(game_state=self.state.game_state)

    def _load_words(self, words_path: Optional[str] = None, hardcore: bool = False):
        try:
            if words_path is not None:
                if not os.path.exists(words_path): # Use provided path
                    raise FileNotFoundError(f"Words data file not found at: {words_path}")
                with open(words_path, "r", encoding="utf-8") as file:
                    word_data = file.readlines()
            else: # Use package resource
                with importlib.resources.files('textarena.envs.Crosswords').joinpath('words_clues.jsonl').open('r') as file:
                    word_data = file.readlines()
            parsed = [json.loads(line) for line in word_data]
            self.word_data = []
            seen_words = set()
            for entry in parsed:
                word = entry["word"].upper()
                if entry["hardcore"] != hardcore or not word.isalpha() or word in seen_words:
                    continue
                seen_words.add(word)
                self.word_data.append({**entry, "word": word})
            if not self.word_data:
                raise ValueError(f"No words found matching hardcore={hardcore} criteria.")
        except Exception as e:
            raise FileNotFoundError(f"Failed to load words data: {str(e)}")

    def setup(self) -> Dict[str, Any]:
        game_board, placed_words, clues = self._generate_board() ## generate the game board and the placed words for the clues
        return {"solution": copy.deepcopy(game_board), "board": self._hide_letters(game_board), "clues": clues, "placed_words": placed_words}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing Crosswords.\nHere is the current state of the Crosswords grid. Each row and column are numbered.\n"
            "The cells that need to be populated with letters are represented by '_', and those that do not need words are represented by '.'.\n\n"
            "You can only provide one guess per turn. Hence, plan your approach and risk appetite. Submit your guess in the format 'row column letter', e.g. '0 0 d' or '1 2 G'.\n"
            "As you play, the history of your choices will be appended below. Use the information to complete the game.\n"
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n{self._render_board()}\nHere are the clues for the words you need to find:\n{self._clue_generator()}"

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        ## validate the action; one 'row column letter' guess per turn (stray brackets tolerated)
        match = self._ACTION_RE.fullmatch(action.strip())
        if not match:
            return self.invalid("The Player did not respond with valid 'row column letter'.")
        matches = [(match.group("row"), match.group("col"), match.group("letter"))]
        if any(
            len(value) > self.MAX_COORDINATE_DIGITS
            for row, col, _ in matches
            for value in (row, col)
        ):
            return self.invalid("The specified coordinate is out of bounds.")

        # Validate every guess against a simulated board first, so no state is
        # mutated when any guess in the batch is invalid.
        board = [row[:] for row in gs["board"]]
        for match in matches:
            row, col, letter = int(match[0]), int(match[1]), str(match[2])
            if row < 0 or row >= len(board) or col < 0 or col >= len(board[0]):
                return self.invalid("The specified coordinate is out of bounds.")
            if board[row][col] == ".":
                return self.invalid("The specified coordinate is a black cell.")
            if not gs["solution"][row][col].upper() == letter.upper():
                return self.invalid("Invalid move. The specified letter is incorrect.")
            if board[row][col] != "_":
                return self.invalid(f"The specified cell already contains a letter: {board[row][col]}.")
            board[row][col] = letter.upper()

        gs["board"] = board
        if self._is_game_over():
            return self.outcome({0: 1}, reason="Congratulations! You completed the Crosswords puzzle.")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _generate_board(self):
        ## init the sampled words, their directions and their clues
        sampled_word_data = None
        for _ in range(1000):
            candidate = self.rng.sample(self.word_data, self.num_words)
            if sum(len(entry["word"]) for entry in candidate) <= self.max_letters:
                sampled_word_data = candidate
                break
        if sampled_word_data is None:
            candidates = list(self.word_data)
            self.rng.shuffle(candidates)
            sampled_word_data = sorted(candidates, key=lambda entry: len(entry["word"]))[: self.num_words]
        sampled_word_data_sorted = sorted(sampled_word_data, key=lambda x: len(x["word"]), reverse=True)
        words = [x["word"] for x in sampled_word_data_sorted]
        directions = {x["word"]: self.rng.choice(["across", "down"]) for x in sampled_word_data_sorted}
        clues = {x["word"]: self.rng.choice(list(x["clues"].values())) for x in sampled_word_data_sorted}

        ## generate the crossword grid
        grid_size = self._determine_initial_grid_size(words)
        grid = self._create_empty_grid(grid_size)

        placed_words = {}  # word: (row, col), where 0 is the starting index

        for word in words:
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
                possible_positions = self._find_overlaps(word, grid, placed_words, directions)
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

        if len(placed_words) != len(words):
            raise RuntimeError("failed to place every sampled crossword word")
        return grid, placed_words, {word: clues[word] for word in placed_words}

    def _determine_initial_grid_size(self, words):
        """ Determine the initial size of the grid based on the length of the longest word """
        max_length = max(len(word) for word in words)
        # The extra lane per word guarantees that the fallback placement can
        # always find an untouched row or column, even when words do not share
        # any letters and their randomly selected directions are mixed.
        return max(round(max_length * 1.5), max_length + len(words))

    def _create_empty_grid(self, size):
        """ Create an empty grid of the specified size """
        return [["." for _ in range(size)] for _ in range(size)]

    def _can_place_word(self, grid, word, direction, row, col):
        """
        Check if a word can be placed on the grid at the specified position.

        Args:
            grid (List[List[str]]): The crossword grid.
            word (str): The word to be placed.
            direction (str): The direction in which the word is to be placed ("across" or "down").
            row (int): The row in which the word is to be placed.
            col (int): The column in which the word is to be placed.
        """
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
        """
        Place a word on the grid at the specified position.

        Args:
            grid (List[List[str]]): The crossword grid.
            word (str): The word to be placed.
            direction (str): The direction in which the word is to be placed ("across" or "down").
            row (int): The row in which the word is to be placed.
            col (int): The column in which the word is to be placed.
        """
        if direction == "across":
            for i, letter in enumerate(word):
                grid[row][col + i] = letter
        else:  # "down"
            for i, letter in enumerate(word):
                grid[row + i][col] = letter

    def _find_overlaps(self, word, grid, placed_words, directions):
        """
        Find all possible valid overlaps for the word with already placed words.

        Args:
            word (str): The word to be placed.
            grid (List[List[str]]): The crossword grid.
            placed_words (Dict[str, Tuple[int, int, str]]): A dictionary of placed words and their positions.
            directions (Dict[str, str]): A dictionary of words and their directions.

        Returns:
            List[Tuple[int, int, str]]: A list of possible overlaps in the format (row, col, direction
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

    def _render_board(self):
        """ Print the grid for text display """
        ## should be C01, C03, ... C10, C11, ...
        header = "   " + " ".join(f"C{i:02}" for i in range(len(self.game_state['board'])))
        lines = [header]
        for i, row in enumerate(self.game_state['board']):
            ## should be R01, R02, ... R10, R11, ...
            row_str = f"R{i:02} "
            for j, val in enumerate(row): row_str += f" {val}  "
            lines.append(row_str)

        return "\n".join(lines)

    def _hide_letters(self, grid):
        """ Hide the letters in the grid """
        return [['_' if cell != "." else cell for cell in row] for row in grid]

    def _get_percentage_completion(self) -> float:
        """ Compute the percentage of the crossword that has been solved so far """
        total_letter_cells = 0 # Count every cell that should eventually contain a letter
        filled_letter_cells = 0
        for row in self.game_state["board"]:
            for cell in row:
                if cell != ".": # not a black square
                    total_letter_cells += 1
                    if cell != "_" and cell.isalpha(): # already revealed / guessed
                        filled_letter_cells += 1
        if total_letter_cells == 0: # safety guard
            return 0.0
        return filled_letter_cells / total_letter_cells

    def _is_game_over(self) -> bool:
        """ Check if the game is over; Returns: (bool) True if the game is over, False otherwise """
        return all("_" not in row for row in self.game_state["board"])

    def _clue_generator(self, string_format=True):
        """ Generate a clue for a word; Returns: (str) The clue for the word. """
        res = []
        for i, (word, position) in enumerate(self.game_state["placed_words"].items()):
            res.append(f"{i+1}. {self.game_state['clues'][word]}: {position}")
        return "\n".join(res) if string_format else res
