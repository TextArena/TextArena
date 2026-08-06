import re, random, copy, string
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta
from textarena.envs.WordSearch.renderer import create_board_str

import nltk
from nltk.corpus import words
nltk.download('words')

class WordSearchEnv(ta.Env):
    """ Word Search environment """

    def __init__(self, hardcore: Optional[bool] = False, max_turns: int = 20):
        """
        Initialize the Word Search environment.

        Args:
            hardcore: Whether to play in hardcore mode.
        """
        super().__init__()
        self.hardcore = hardcore
        self.max_turns = max_turns
        self.num_words = 5
        self.num_incorrect_tries = 20

        ## load the word list
        self.word_list = words.words("en") if self.hardcore else words.words("en-basic")

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int] = None):
        """ Reset the environment """
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns) ## initialise the game state
        self.game_board, self.placed_words = self._generate_word_search() ## load the game board
        ## reset the state
        game_state = {"board": copy.deepcopy(self.game_board), "rendered_board": self._render_board(self.game_board),}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
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
            "You may type your response and thoughts in any manner. But you may only submit one submission at a time. For your submissions, use the format '[start_row start_col end_row end_col]'.\n"
            "For instance, if you want to find the word 'HELLO' starting at row 1, column 1 and ending at row 1, column 5, enter '[1 1 1 5]'.\n"
            "\nGuidelines:\n"
            "- Each guess must be unique; you cannot repeat the same guess.\n"
            "- You have a total of 20 incorrect attempts remaining.\n"
            "- The history of your attempts will be recorded below.\n\n"
            "Make your guesses carefully and strategically. Good luck, Player {player_id}! Let's see how many words you can find!\n"
        )
        return prompt
    
    def _observe_current_state(self) -> None:
        """
        Observe the current state of the game and update the observations.
        This includes the current board, placed words, and any incorrect attempts.
        """
        self.state.add_observation(
            message=f"Current Board:\n\n{self._render_board(self.state.game_state['board'], show_words=True)}\n"
                    f"Placed Words: {', '.join(self.placed_words.keys())}\n"
                    f"Incorrect Attempts Remaining: {self.num_incorrect_tries}",
            observation_type=ta.ObservationType.GAME_BOARD
        )
    
    def _generate_word_search(self):
        """
        Generate a word search grid with the given words and their directions.

        Returns:
            List[List[str]]: The generated word search grid.
            Dict[str, Tuple[int, int, str]]: The placed words and their positions and directions.

        """
        ## sample the words
        self.words = random.sample(self.word_list, self.num_words)
        self.words = [word.upper() for word in self.words]
        self.words = sorted(self.words, key=lambda w: len(w), reverse=True)
        self.directions = {word: random.choice(["across", "down"]) for word in self.words}

        self.highlighted_positions = set()
        self.correct_words = set()
        self.incorrect_attempts = []

        grid_size = self._determine_initial_grid_size(self.words)
        grid = self._create_empty_grid(grid_size)

        self.placed_words = {}  # word: (row, col), where 0 is the starting index

        for word in self.words:
            placed = False
            if not self.placed_words:  # First word
                # Place the first word in the center of the grid
                if self.directions[word] == "across":
                    row = grid_size // 2
                    col = (grid_size - len(word)) // 2
                else:
                    row = (grid_size - len(word)) // 2
                    col = grid_size // 2

                if self._can_place_word(grid, word, self.directions[word], row, col):
                    self._place_word_on_grid(grid, word, self.directions[word], row, col)
                    self.placed_words[word] = (row, col, self.directions[word])
                    placed = True
            
            else:
                # Attempt to find overlaps
                possible_positions = self._find_overlaps(word, grid, self.directions)
                random.shuffle(possible_positions)  # Randomize to add variability
                for pos in possible_positions:
                    row, col, direction = pos
                    if self._can_place_word(grid, word, direction, row, col):
                        self._place_word_on_grid(grid, word, direction, row, col)
                        self.placed_words[word] = (row, col, direction)
                        placed = True
                        break

            if not placed:
                # If no overlap placement is possible, try placing the word in any free position
                for row in range(grid_size):
                    for col in range(grid_size):
                        if self._can_place_word(grid, word, self.directions[word], row, col):
                            self._place_word_on_grid(grid, word, self.directions[word], row, col)
                            self.placed_words[word] = (row, col, self.directions[word])
                            placed = True
                            break
                    if placed:
                        break

        # Fill the remaining grid with random letters
        self._fill_empty_cells(grid)
        return grid, self.placed_words

    def _determine_initial_grid_size(self, words):
        """
        Determine the initial size of the grid based on the length of the longest word.

        Args:
            words (List[str]): The list of words to place on the grid.

        Returns:
            int: The initial size of the grid.

        """
        max_length = max(len(word) for word in words)
        return round(max_length * 1.5)  # Ensures that the grid size is larger than the longest word to allow placement

    def _create_empty_grid(self, size):
        """
        Create an empty grid of the specified size.

        Args:
            size (int): The size of the grid.

        Returns:
            List[List[str]]: The empty grid.

        """
        return [["." for _ in range(size)] for _ in range(size)]

    def _can_place_word(self, grid, word, direction, row, col):
        """
        Check if a word can be placed on the grid at the specified position.

        Args:
            grid (List[List[str]]): The current grid.
            word (str): The word to place.
            direction (str): The direction of the word ("across" or "down").
            row (int): The starting row index.
            col (int): The starting column index.

        Returns:
            bool: True if the word can be placed, False otherwise.

        """
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
            grid (List[List[str]]): The current grid.
            word (str): The word to place.
            direction (str): The direction of the word ("across" or "down").
            row (int): The starting row index.
            col (int): The starting column index.

        """
        if direction == "across":
            for i, letter in enumerate(word):
                grid[row][col + i] = letter
        else:  # "down"
            for i, letter in enumerate(word):
                grid[row + i][col] = letter

    def _find_overlaps(self, word, grid, directions):
        """
        Find all possible valid overlaps for the word with already placed words.
        
        Args:
            word (str): The word to place.
            grid (List[List[str]]): The current grid.
            directions (Dict[str, str]): The directions of the words.
            
        Returns:
            List[Tuple[int, int, str]]: The list of possible overlaps (row, col, direction).
            
        """
        overlaps = []
        for placed_word, (p_row, p_col, p_direction) in self.placed_words.items():
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
        """
        Fill empty cells with random letters.
        
        Args:
            grid (List[List[str]]): The current grid.
            
        """
        for row in range(len(grid)):
            for col in range(len(grid[0])):
                if grid[row][col] == ".":
                    grid[row][col] = random.choice(string.ascii_uppercase)

    def _validate_and_replace_unintended_words(self, grid, words):
        """
        Validate the grid and replace unintended words with random letters in a single pass
        
        Args:
            grid (List[List[str]]): The current grid.
            words (List[str]): The list of words to place on the grid.
            
        """
        grid_size = len(grid)
        word_set = set(words)

        # Check each row for unintended words
        for row_index, row in enumerate(grid):
            row_str = "".join(row)
            self._find_and_replace_unintended_words(grid, row_str, word_set, row_index, is_row=True)

        # Check each column for unintended words
        for col_index in range(grid_size):
            col_str = "".join(grid[row][col_index] for row in range(grid_size))
            self._find_and_replace_unintended_words(grid, col_str, word_set, col_index, is_row=False)

    def _find_and_replace_unintended_words(self, grid, string, word_set, index, is_row):
        """
        Helper function to find and replace unintended words in a string, avoiding placed word positions.
        
        Args:
            grid (List[List[str]]): The current grid.
            string (str): The string to check for unintended words.
            word_set (Set[str]): The set of words to avoid.
            index (int): The row or column index.
            is_row (bool): Whether the string is a row or column.
            
        """
        min_word_length = 3  # Only consider words of length 3 or greater
        placed_positions = self._get_positions()

        for start in range(len(string)):
            for end in range(start + min_word_length, len(string) + 1):
                substring = string[start:end]
                
                # Map the substring positions to (row, col) based on whether it's a row or column
                if is_row:
                    substring_positions = {(index, start + i) for i in range(len(substring))}
                else:
                    substring_positions = {(start + i, index) for i in range(len(substring))}
                
                # Check if any part of the substring overlaps with placed word positions
                if substring_positions & placed_positions:
                    continue  # Skip if any part of the substring overlaps with placed words

                if substring in word_set:
                    continue  # This is an intended word, skip it
                
                # Check if the substring is a valid English word
                if self._is_valid_word(substring):
                    print(f"Unintended word found: {substring}")
                    self._replace_unintended_word(grid, substring_positions)

    def _replace_unintended_word(self, grid, positions):
        """
        Replace unintended word positions in the grid with random uppercase letters.
        
        Args:
            grid (List[List[str]]): The current grid.
            positions (Set[Tuple[int, int]]): The positions to replace.
            
        """
        for row, col in positions:
            grid[row][col] = random.choice(string.ascii_uppercase)

    def _is_valid_word(self, word):
        """
        Check if the word is valid (could use a dictionary or predefined list).
        
        Args:
            word (str): The word to check.
            
        Returns:
            bool: True if the word is valid, False otherwise.
            """
        return word.lower() in words.words("en")
    
    def _get_positions(self):
        """
        Get the positions of the placed words.

        Returns:
            Set[Tuple[int, int]]: The positions of the placed words.

        """
        positions = set()
        for word, (row, col, direction) in self.placed_words.items():
            if direction == "across":
                for position in [(row, col + i) for i in range(len(word))]:
                    positions.add(position)
            else:  # "down"
                for position in [(row + i, col) for i in range(len(word))]:
                    positions.add(position)
        return positions
    

    def _render_board(self, grid, show_words=True):
        """
        Print the grid with the words highlighted based on the stored highlighted positions.
        
        Args:
            grid (List[List[str]]): The current grid.
            show_words (bool): Whether to show the words in square brackets.
            
        Returns:
            str: The rendered board as a string.
            
        """
        header = "   " + " ".join(f"C{i:02}" for i in range(len(grid)))
        lines = [header]
        for i, row in enumerate(grid):
            row_str = f"R{i:02} "
            for j, val in enumerate(row):
                if (i, j) in self.highlighted_positions:
                    row_str += f"[{val}] " if show_words else f" {val}  "
                else:
                    row_str += f" {val}  "
            lines.append(row_str)

        return "\n".join(lines)

    def _check_word(self, grid, start_row, start_col, end_row, end_col):
        """
        Check if the selected word exactly matches a placed word and update game state.

        Args:
            grid (List[List[str]]): The current grid.
            start_row (int): The starting row index.
            start_col (int): The starting column index.
            end_row (int): The ending row index.
            end_col (int): The ending column index.

        Returns:
            bool: True if the word is correct, False otherwise.
        """
        for placed_word, (row, col, direction) in self.placed_words.items():
            expected_start = (row, col)
            if direction == "across":
                expected_end = (row, col + len(placed_word) - 1)
            else:  # "down"
                expected_end = (row + len(placed_word) - 1, col)

            actual_start = (start_row, start_col)
            actual_end = (end_row, end_col)

            if (actual_start == expected_start and actual_end == expected_end) or \
            (actual_start == expected_end and actual_end == expected_start):
                self.correct_words.add(placed_word)
                self._highlight_word(start_row, start_col, end_row, end_col)
                print(f"Correct! The word '{placed_word}' was found.")
                return True

        # If no match, record as an incorrect attempt
        self.incorrect_attempts.append((start_row, start_col, end_row, end_col))
        print("Incorrect attempt.")
        return False

        
    def _highlight_word(self, start_row, start_col, end_row, end_col):
        """
        Highlight a word's positions based on the start and end coordinates.

        Args:
            start_row (int): The starting row index.
            start_col (int): The starting column index.
            end_row (int): The ending row index.
            end_col (int): The ending column index.

        """
        if start_row == end_row:  # Horizontal word
            for col in range(min(start_col, end_col), max(start_col, end_col) + 1):
                self.highlighted_positions.add((start_row, col))
        elif start_col == end_col:  # Vertical word
            for row in range(min(start_row, end_row), max(start_row, end_row) + 1):
                self.highlighted_positions.add((row, start_col))
        else:
            print("Invalid input: Words can only be horizontal or vertical.")

    def _extract_word(self, grid, start_row, start_col, end_row, end_col):
        """
        Extracts the word from the grid based on start and end coordinates.

        Args:
            grid (List[List[str]]): The current grid.
            start_row (int): The starting row index.
            start_col (int): The starting column index.
            end_row (int): The ending row index.
            end_col (int): The ending column index.

        Returns:
            str: The extracted word

        """
        if start_row == end_row:  # Horizontal word
            return "".join(grid[start_row][col] for col in range(min(start_col, end_col), max(start_col, end_col) + 1))
        elif start_col == end_col:  # Vertical word
            return "".join(grid[row][start_col] for row in range(min(start_row, end_row), max(start_row, end_row) + 1))
        else:
            print("Invalid input: Words can only be horizontal or vertical.")
            return ""

    def _matches_position(self, word, row, col, direction, start_row, start_col, end_row, end_col):
        """
        Check if the provided start and end positions match a placed word's position.

        Args:
            word (str): The word to check.
            row (int): The row index of the placed word.
            col (int): The column index of the placed word.
            direction (str): The direction of the placed word.
            start_row (int): The starting row index.
            start_col (int): The starting column index.
            end_row (int): The ending row index.
            end_col (int): The ending column index.

        Returns:
            bool: True if the positions match, False otherwise.

        """
        if direction == "across" and row == start_row and col == min(start_col, end_col):
            return len(word) == abs(end_col - start_col) + 1
        elif direction == "down" and col == start_col and row == min(start_row, end_row):
            return len(word) == abs(end_row - start_row) + 1
        return False
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """ Take a step in the environment """
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) ## Update the observations that was provided by the player
        ## validate the action
        action_search_pattern = re.compile(r"\[(\d+)\s(\d+)\s(\d+)\s(\d+)\]")
        matches = action_search_pattern.findall(action)
        matches = set(matches)

        if not matches:
            ## invalid action
            reason=f"Invalid move format. Player {player_id} did not respond with valid 'start_row, start_col, end_row, end_col'."
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=reason)
        else:
            for match in matches:
                print("Checking match:", match)
                start_row, start_col, end_row, end_col = [int(x) for x in match]
                if not (0 <= start_row < len(self.state.game_state["board"]) 
                        and 0 <= start_col < len(self.state.game_state["board"][0]) 
                        and 0 <= end_row < len(self.state.game_state["board"]) 
                        and 0 <= end_col < len(self.state.game_state["board"][0])):
                    ## action out of bounds
                    reason=f"Invalid move format. Player {player_id} did not respond with valid 'start_row, start_col, end_row, end_col'."
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=reason)
                    break
                elif (start_row, start_col, end_row, end_col) in self.incorrect_attempts:
                    ## action already attempted
                    reason=f"Invalid move. The action has already been attempted."
                    self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=reason)
                    break
                elif not self._check_word(self.state.game_state["board"], start_row, start_col, end_row, end_col):
                    ## action is incorrect
                    self.num_incorrect_tries -= 1
                    message=f"[{start_row} {start_col} {end_row} {end_col}] is an incorrect attempt. {self.num_incorrect_tries} incorrect tries remaining."
                    self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
                    if self.num_incorrect_tries == 0:
                        reward = round(len(self.correct_words) / len(self.placed_words), 3)
                        reason = f"No more incorrect tries remaining. You found {len(self.correct_words)} out of {len(self.placed_words)} words ({round(reward * 100)}%)."
                        self.state.set_outcome(reward=reward, reason=reason)
                    break
                else:
                    ## action is correct
                    word_found = self._map_coordinate_to_word(start_row, start_col, end_row, end_col)
                    if word_found:
                        self.correct_words.add(word_found)
                        self._highlight_word(start_row, start_col, end_row, end_col)
                        message = f"[{start_row} {start_col} {end_row} {end_col}] is a correct attempt. You found the word '{word_found}'."
                    else:
                        message = f"[{start_row} {start_col} {end_row} {end_col}] is a correct attempt, but the word was not found in the placed words."
                    self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=message, observation_type=ta.ObservationType.GAME_MESSAGE)
            
            ## update the game board
            self.state.game_state["rendered_board"] = self._render_board(self.state.game_state["board"], show_words=True)

        if len(self.correct_words) == len(self.placed_words):
            reason = f"Congratulations! You completed the Word Search puzzle."
            self.state.set_outcome(reward=1.0, reason=reason)

        self._observe_current_state()  # Update the current state observation
        return self.state.step()

    def _map_coordinate_to_word(self, start_row: int, start_col: int, end_row: int, end_col: int) -> Union[str, None]:
        """
        Map the coordinates to the corresponding word if it exists.

        Args:
            start_row (int): The starting row index.
            start_col (int): The starting column index.
            end_row (int): The ending row index.
            end_col (int): The ending column index.

        Returns:
            str or None: The word if found, otherwise None.
        """
        for word, (row, col, direction) in self.placed_words.items():
            if self._matches_position(word, row, col, direction, start_row, start_col, end_row, end_col):
                return word
        return None
    

    def _get_percentage_completion(self) -> float:
        """
        Calculate the percentage of words found compared to the total number of words.

        Returns:
            float: The percentage of words found.
        """
        if not self.placed_words:
            return 0.0
        return len(self.correct_words) / len(self.placed_words)