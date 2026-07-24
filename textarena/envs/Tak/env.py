import re, ast, random
from typing import Dict, Optional, List, Tuple

import textarena as ta

class TakEnv(ta.Env):
    """
    Tak environment.
    """
    def __init__(self, board_size, stones, capstones):
        """
        Initialize the Tak game environment
        
        Args:
            difficulty: Difficulty of the game. Can be "easy", "medium", "hard".
        """

        self.board_size = board_size
        self.stones = stones
        self.capstones = capstones
        
        self.players = None
        self.board = None

    @property 
    def terminal_render_keys(self):
        return ["rendered_board"]

    def reset(self, num_players: int = 2, seed: Optional[int]=None):
        """
        Reset the environment to set a new game.
        
        Args:
            seed: Seed for the random number generator.
        """
        ## initialize the game state
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)

        ## initialize the board
        self.board = self._generate_board()
        self.players = {
            0: {"stones": self.stones, "capstones": self.capstones},
            1: {"stones": self.stones, "capstones": self.capstones}
        }

        ## reset the game state
        game_state={"board": self.board, "rendered_board": self._render_board()}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()
    
    def _generate_board(self):
        """
        Generate the initial board state.
        """
        board = [[[] for _ in range(self.board_size)] for _ in range(self.board_size)]
        return board

    def _render_board(self):
        """
        Renders the board as a string and returns it.
        """
        # Calculate the maximum cell width across the board
        max_cell_width = max(
            len(self._format_stack(cell)) for row in self.board for cell in row
        )
        cell_width = max(max_cell_width, 5)  # Ensure minimum cell width for readability

        # Create the column headers
        header = "      " + "   ".join(f"{i:^{cell_width}}" for i in range(self.board_size))

        # Create the separator line
        separator = "     " + "-" * (self.board_size * (cell_width + 3) - 1)

        # Create rows
        rows = []
        for row_idx, row in enumerate(self.board):
            # Format each cell and align it
            row_display = [self._pad_cell(self._format_stack(cell), cell_width) for cell in row]
            rows.append(f"{row_idx:>3} | " + " | ".join(row_display) + " |")
            rows.append(separator)

        # Combine header, separator, and rows into a single string
        board_string = "\n".join([header, separator] + rows)
        return board_string


    def _format_stack(self, stack):
        """
        Helper function to format stacks in each cell,
        """
        if not stack:
            return ""  # Empty cell
        return f"({len(stack)}) {'/'.join(stack)}"  # Full stack representation
    
    ## Helper function to pad cells for uniform display
    def _pad_cell(self, content, cell_width):
        return content.center(cell_width)

    ## Helper function to generate the player prompt
    def _generate_player_prompt(self, player_id, game_state):
        """
        Generate the player prompt.
        """
        prompt = (
            f"You are Player {player_id} in Tak.\n"
            "Your goal is to connect two opposite edges of the board with your pieces to form a road while blocking your opponent from doing the same.\n"
            "You can perform the following actions on your turn:\n"
            "- Place a piece on an empty square.\n"
            "- Move a stack of pieces from one square to one or more squares. You can stack your pieces on top of other pieces on the target square. The topmost piece determines ownership of the stack.\n"
            "- Split a stack of pieces into two or more stacks and distribute them to adjacent squares.\n"
            "- Flatten a wall stone into a flat stone using your capstone.\n"
            "- Place a Capstone on an empty square.\n"
            "- Move a Capstone from one square to one or more squares. A capstone can also flatten a wall stone during its move.\n"
            "\n"
            "For each move, submit your action using the format:\n"
            "[ACTION SOURCE ALLOCATION]\n"
            "- ACTION: The type of move you are making ('place' or 'move').\n"
            "- SOURCE: The grid coordinates where the stones originate. Use () for 'place'.\n"
            "- ALLOCATION: A dictionary where keys are target grid coordinates and values are the stones or pieces being moved or placed.\n"
            "\n"
            "Stone Types and Their Abilities:\n"
            "- Flat Stone ('F'):\n"
            "  - Forms part of a road (used to connect edges of the board).\n"
            "  - Can be stacked on top of other pieces or have other pieces stacked on it.\n"
            "  - Can be moved as part of a stack or individually.\n"
            "\n"
            "- Wall Stone ('W'):\n"
            "  - Blocks roads and prevents opponents from completing their connections.\n"
            "  - Cannot be part of a road.\n"
            "  - Can be flattened into a flat stone by a capstone.\n"
            "\n"
            "- Capstone ('C'):\n"
            "  - Acts as a flat stone and can form part of a road.\n"
            "  - Can flatten wall stones, removing their blocking effect.\n"
            "  - Cannot be covered by other pieces, always remains on top of the stack.\n"
            "  - Is a powerful tool for both road-building and disrupting your opponent's plans.\n"
            "\n"
            "The stones will be identified by the player as follows:\n"
            "- Flat Stone for Player 0: 'F0'\n"
            "- Wall Stone for Player 1: 'W1'\n"
            "- Capstone for Player 1: 'C1'\n"
            "\n"
            "Examples:\n"
            "- To place a capstone on (3,2):\n"
            "  [place () {(3,2): [C0]}]\n"
            "- To move all pieces from (2,2) to (2,3):\n"
            "  [move (2,2) {(2,3): [F0]}]\n"
            "- To split a stack of 5 pieces from (2,2) into two squares:\n"
            "  [move (2,2) {(2,3): [F0, F0], (2,4): [W0, F0, C0]}]\n"
            "- To move and stack one piece from (2,2) onto an existing stack at (2,3):\n"
            "  [move (2,2) {(2,3): [F0]}]\n"
            "\n"
            "When submitting your move, think strategically about your road-building goals and your opponent's potential moves.\n"
        )

        return prompt
    
    def _observe_current_state(self) -> None:
        """
        Observe the current state of the game and update the game state with the current board.
        """
        board_str = self._render_board()
        # Calculate the available flat stones and capstones for the current player
        available_flat_stones = self.players[self.state.current_player_id]["stones"]
        available_capstones = self.players[self.state.current_player_id]["capstones"]
        self.state.add_observation(
            message=f"Current Board:\n\n{board_str}\nAvailable Flat Stones: {available_flat_stones}, Available Capstones: {available_capstones}\n",
            observation_type=ta.ObservationType.GAME_BOARD
        )


    def step(self, action: str) -> Tuple[bool, Optional[ta.Info]]:
        """
        Execute the action for the player.
        
        Args:
            action: Action taken by the player.
            
        Returns:
            Done: Whether the game is over.
            Info: Additional information.
        """
        ## Update the observation
        self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        ## action search pattern
        action_search_pattern = re.compile(
            r"\[(place|move)\s"                # Match action: "place" or "move"
            r"\((\d+,\d+|\s*)\)\s"            # Match source: "(row,col)" or "()"
            r"({.*?})\]"                      # Match allocation dictionary
        )  # Example: [move (2,2) {'(2,3)': ['F0', 'W0'], '(2,4)': ['C1']}]
        match = action_search_pattern.search(action)

        if not match:
            ## no matching action
            reason=f"Invalid move format. Player {self.state.current_player_id} did not respond with a valid move in square brackets."
            self.state.set_invalid_move(reason=reason)
        
        else:
            ## found the matching action
            action, source, allocation = self.extract_values(match.groups())

            if action == "place":
                ## place a piece on an empty square
                if not self._is_valid_placement(allocation):
                    ## invalid placement
                    reason=f"Invalid placement. Player {self.state.current_player_id} tried to place a piece on an invalid square."
                    self.state.set_invalid_move(reason=reason)
                else:
                    self._apply_placement(allocation, self.state.current_player_id)
                    message=f"Player {self.state.current_player_id} placed a piece on ({list(allocation.keys())})."
                    self.state.add_observation(from_id=-1, to_id=-1, message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

            elif action == "move":
                ## move a stack of pieces from one square to another
                if not self._is_valid_movement(source, allocation):
                    ## invalid movement
                    reason=f"Invalid movement. Player {self.state.current_player_id} tried to move pieces in an invalid way."
                    self.state.set_invalid_move(reason=reason)
                else:
                    ## valid movement
                    self._apply_movement(source, allocation)
                    message=f"Player {self.state.current_player_id} moved pieces from {source} to {list(allocation.keys())}.",
                    self.state.add_observation(from_id=-1, to_id=-1, message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

            else:
                ## invalid action
                reason=f"Invalid action. Player {self.state.current_player_id} tried to perform an unknown action."
                self.state.set_invalid_move(reason=reason)

            
            self.state.game_state["rendered_board"] = self._render_board() ## update the rendered board

        
        if self._check_win(self.state.current_player_id): ## check if the game is over
            ## game is over
            reason=f"Player {self.state.current_player_id} has connected two opposite edges of the board."
            self.state.set_winner(player_id=self.state.current_player_id, reason=reason)

        result = self.state.step()
        self._observe_current_state()
        return result

    def _check_win(self, player_id):
        """
        Check if the specified player has won by forming a continuous road
        connecting two opposite edges of the board.

        Args:
            player_id: The ID of the player to check.
            board: The 2D grid representing the game board.
            board_size: The size of the square board (e.g., 4 for a 4x4 board).

        Returns:
            bool: True if the player has won, False otherwise.
        """
        visited = set()
        directions = [(0, 1), (1, 0), (0, -1), (-1, 0)]  # Right, Down, Left, Up

        def is_valid_cell(row, col):
            """Check if the cell is valid for the player."""
            if 0 <= row < self.board_size and 0 <= col < self.board_size:
                stack = self.board[row][col]
                return stack and stack[-1].endswith(str(player_id)) and stack[-1][0] in ["F", "C"]
            return False

        def dfs(row, col, edges_reached):
            """
            Depth-first search to explore all valid paths and update edges reached.

            Args:
                row, col: Current cell position.
                edges_reached: A set of edges the current path has connected to.

            Returns:
                bool: True if the player has connected two opposite edges, False otherwise.
            """
            # If already visited, return False
            if (row, col) in visited:
                return False

            # Mark the current cell as visited
            visited.add((row, col))

            # Update edges reached based on the current cell's position
            if row == 0:
                edges_reached.add("top")
            if row == self.board_size - 1:
                edges_reached.add("bottom")
            if col == 0:
                edges_reached.add("left")
            if col == self.board_size - 1:
                edges_reached.add("right")

            # Check if two opposite edges have been connected
            if ("top" in edges_reached and "bottom" in edges_reached) or \
            ("left" in edges_reached and "right" in edges_reached):
                return True

            # Explore neighboring cells
            for dr, dc in directions:
                new_row, new_col = row + dr, col + dc
                if is_valid_cell(new_row, new_col):
                    # Pass a copy of edges_reached to avoid shared mutation
                    if dfs(new_row, new_col, edges_reached.copy()):
                        return True

            return False

        # Start DFS from all cells on the top edge (for top-to-bottom path)
        for col in range(self.board_size):
            if is_valid_cell(0, col):  # Valid starting point on the top edge
                if dfs(0, col, {"top"}):
                    return True

        # Start DFS from all cells on the left edge (for left-to-right path)
        for row in range(self.board_size):
            if is_valid_cell(row, 0):  # Valid starting point on the left edge
                if dfs(row, 0, {"left"}):
                    return True

        return False

    def _update_pieces(self, player_id, piece):
        """
        Update the player's piece count if a new piece is placed.
        """
        if piece[0][0] == "F" or piece[0][0] == "W":
            self.players[player_id]["stones"] -= 1
        else:
            self.players[player_id]["capstones"] -= 1
    
    def extract_values(self, matched_groups):
        """
        Extract and process the matched groups from the action string.
        
        Args:
            matched_groups: Tuple of matched groups from the action string.
            
        Returns:
            Tuple: Processed action, source, and allocation values.
        """
        action, source, allocation = matched_groups
    
        # Process source: Convert to a tuple of integers or None
        if source.strip():
            source = tuple(map(int, source.split(',')))  # Convert "row,col" to (row, col)
        else:
            source = None  # For place actions with no source

        try:
            allocation_dict = self._convert_to_dict(allocation)
        except:
            return None, None, None

        # Return processed values
        return action, source, allocation_dict


    def _is_valid_placement(self, allocation):
        """ Check if the placement is valid """
        if len(allocation.items()) != 1:
            ## needs to be a single allocation
            return False
        row, col = list(allocation.keys())[0]
        piece = list(allocation.values())[0]

        if piece[0][0] == "C" and self.players[self.state.current_player_id]["capstones"] == 0:
            ## no capstones left
            return False
        elif piece[0][0] in ["F", "W"] and self.players[self.state.current_player_id]["stones"] == 0:
            ## no stones left
            return False

        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            ## needs to be within the board
            return False
        
        if len(piece) != 1:
            ## needs to be a single piece
            return False
        
        if self.board[row][col]:
            ## needs to be an empty square
            return False
        
        if piece[0][0] not in ["F", "W", "C"]:
            ## unacceptable piece
            return False
        
        if piece[0][-1] != str(self.state.current_player_id):
            ## piece does not belong to the current player
            return False
        
        return True
    
    def _apply_placement(self, allocation, player_id):
        ## valid placement
        row, col = list(allocation.keys())[0]
        piece = list(allocation.values())[0]
        # piece = [p.upper() + f"{player_id}" for p in piece]
        self.board[row][col].extend(piece)
        self._update_pieces(player_id, piece)

    
    def _is_valid_movement(self, source, allocation):
        """ check if the movement is valid """
        if source is None: ## source must be provided
            return False
        
        source_row, source_col = source

        if source_col >= self.board_size or source_row >= self.board_size: ## source must be within the board
            return False
        
        if not self.board[source_row][source_col]: ## source must have pieces
            return False
        
        source_type, source_player_id = self.board[source_row][source_col][-1][0], self.board[source_row][source_col][-1][-1]

        if source_player_id != str(self.state.current_player_id): ## source must have the current player's stone on top
            return False
        
        source_stack = self.board[source_row][source_col]
        pieces_to_move = [value for values in allocation.values() for value in values]

        if pieces_to_move != source_stack[-len(pieces_to_move):]: ## pieces to move must match the top of the stack in order
            return False
        
        top_piece_type = source_stack[-1][0]

        if len(pieces_to_move) == 1: ## single pieces retain the power of the capstone - to flatten wall stones.
            target_row, target_col = list(allocation.keys())[0]

            if (abs(target_row - source_row) + abs(target_col - source_col)) != 1: ## target must be adjacent to the source
                return False
            
            if target_row >= self.board_size or target_col >= self.board_size: ## target must be within the board
                return False
            
            if top_piece_type == "C" and self.board[target_row][target_col] and self.board[target_row][target_col][-1][0] == "C": ## capstone cannot be moved over another capstone
                return False
            elif top_piece_type == "W" and self.board[target_row][target_col] and self.board[target_row][target_col][-1][0] in ["W", "C"]: ## wall stone cannot be moved over capstone
                return False
            elif top_piece_type == "F" and self.board[target_row][target_col] and self.board[target_row][target_col][-1][0] in ["W", "C"]: ## flat stone cannot be moved over wall stone or capstone
                return False

        else:
            for i, (target, pieces) in enumerate(allocation.items()):
                target_row, target_col = target
                if (abs(target_row - source_row) + abs(target_col - source_col)) != i + 1: ## target must be adjacent to the source
                    return False
                
                if target_row >= self.board_size or target_col >= self.board_size: ## target must be within the board
                    return False
                
                if self.board[target_row][target_col]:
                    if self.board[target_row][target_col][-1][0] == "C": ## nothing can be moved over another capstone
                        return False
                    elif self.board[target_row][target_col][-1][0] == "W": ## nothing can be moved over a wall stone
                        return False
                
        return True
    
    def _apply_movement(self, source, allocation):
        """ Apply the movement to the board """
        source_row, source_col = source
        source_stack = self.board[source_row][source_col]
        pieces_to_move = [value for values in allocation.values() for value in values]
        top_piece_type = source_stack[-1][0]

        if len(pieces_to_move) == 1:
            target_row, target_col = list(allocation.keys())[0]
            if self.board[target_row][target_col]:
                if top_piece_type == "C" and self.board[target_row][target_col][-1][0] == "W": ## capstone can flatten wall stone
                    self.board[target_row][target_col][-1] = "F" + self.board[target_row][target_col][-1][1]
            self.board[target_row][target_col].extend(pieces_to_move)
        else:
            for target, pieces in allocation.items():
                target_row, target_col = target
                self.board[target_row][target_col].extend(pieces)
        self.board[source_row][source_col] = source_stack[:-len(pieces_to_move)]            
    
    def _convert_to_dict(self, input_str):
        """
        Converts a string representation of a dictionary with tuple keys and list-like values
        into a valid Python dictionary, ensuring:
        - Tuple keys retain their integer types.
        - List elements are converted to strings.
        """
        # Preprocess the string to wrap unquoted words with quotes
        def add_quotes(match):
            return f"'{match.group(0)}'"
        
        # Use regex to find unquoted words in the list-like values
        input_str = re.sub(r'\b([A-Za-z0-9_]+)\b', add_quotes, input_str)
        
        # Safely evaluate the corrected string
        try:
            parsed_dict = ast.literal_eval(input_str)
            # Convert keys back to tuples with integers, and ensure list elements are strings
            result_dict = {tuple(int(k) if k.isdigit() else k for k in key): [str(item) for item in value] for key, value in parsed_dict.items()}
            return result_dict
        except Exception as e:
            raise ValueError(f"Invalid input string: {input_str}") from e
