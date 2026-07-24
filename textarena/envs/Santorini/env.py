import re
from typing import Any, Dict, Optional, Tuple
import textarena as ta
from textarena.envs.Santorini.renderer import create_board_str

class SantoriniBaseFixedWorkerEnv(ta.Env):
    """Environment for playing the base version of Santorini with fixed worker positions.
    
    This version supports 2-3 players with pre-set optimal worker positions:
    
    2 Players:
    - Player 0 (Navy): C2, B3
    - Player 1 (White): D3, C4
    
    3 Players:
    - Player 0 (Navy): C3, B3
    - Player 1 (White): D3, B4
    - Player 2 (Grey): D2, D4
    """

    # Initial worker positions for different player counts
    INITIAL_POSITIONS = {
        2: [
            [(2,1), (1,2)],  # Player 0 (Navy): C2, B3
            [(3,2), (2,3)]   # Player 1 (White): D3, C4
        ],
        3: [
            [(2,2), (1,2)],  # Player 0 (Navy): C3, B3
            [(3,2), (1,3)],  # Player 1 (White): D3, B4
            [(3,1), (3,3)]   # Player 2 (Grey): D2, D4
        ]
    }

    # Player colors
    PLAYER_COLORS = ["Navy", "White", "Grey"]

    def __init__(self, is_open: bool=True, show_valid: bool=True, error_allowance: int=10):
        """Initialize the Santorini game environment.
        
        Args:
            is_open (bool): If True, all players can see the current board state.
            show_valid (bool): If True, players can see a list of valid moves.
            error_allowance (int): Number of invalid moves allowed before a player loses.
        """
        self.is_open = is_open
        self.show_valid = show_valid
        self.error_allowance = error_allowance

        # Regex pattern for moves: [worker(N1|N2|W1|W2|G1|G2)source(A-E)(1-5)dest(A-E)(1-5)build(A-E)(1-5)]
        # Pattern can appear anywhere in the text, allowing additional content around it
        self.move_pattern = re.compile(r"\[(N[12]|W[12]|G[12])([A-E][1-5])([A-E][1-5])([A-E][1-5])\]", re.IGNORECASE)

        # Board dimensions
        self.rows = 5
        self.cols = 5

    def reset(self, num_players: int, seed: Optional[int]=None):
        """Reset the game to its initial state."""
        if num_players not in [2, 3]:
            raise ValueError("Number of players must be 2 or 3")
            
        self.state = ta.FFAMultiPlayerState(
            seed=seed,
            num_players=num_players,
            max_turns=None,  # No turn limit in Santorini
            error_allowance=self.error_allowance  # Set error allowance for invalid moves
        )

        # Initialize the board
        # Each cell contains (height, worker)
        # height: 0-3 for levels, 4 for dome
        # worker: None or (player_id, worker_num)
        self.board = [[(0, None) for _ in range(self.cols)] for _ in range(self.rows)]

        # Set initial worker positions based on number of players
        for player_id, positions in enumerate(self.INITIAL_POSITIONS[num_players]):
            for worker_num, (row, col) in enumerate(positions, 1):
                self.board[row][col] = (0, (player_id, worker_num))

        game_state = {
            "board": self.board,
            "valid_moves": self._get_valid_moves(0)  # Initial valid moves for first player
        }

        self.state.reset(game_state=game_state, 
                         player_prompt_function=self._generate_player_prompt,
                         role_mapping={i: self.PLAYER_COLORS[i] for i in range(num_players)},
                         )

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        """Generate the initial prompt for a player."""
        color = self.PLAYER_COLORS[player_id]
        prompt = (
            f"You are playing {color} in a game of Santorini.\n\n"
            "Game Rules:\n"
            "1. Movement:\n"
            "   - Workers can only move to adjacent squares (including diagonals)\n"
            "   - Cannot move to squares occupied by other workers or domes\n"
            "   - Can move up maximum one level, but can move down any number of levels\n\n"
            "2. Building:\n"
            "   - Must build in a square adjacent to where your worker moved to\n"
            "   - Cannot build where any worker is standing\n"
            "   - Cannot build on top of a dome (level 4)\n"
            "   - Building adds one level (or creates a dome on level 3)\n\n"
            "3. Win Conditions:\n"
            "   - Win by moving a worker to level 3\n"
            "   - Win if opponent has no valid moves\n\n"
            "Make your move in the format [worker_id source dest build]\n"
            f"Example: [{color[0]}1C1C2B2] means move {color} worker 1 from C1 to C2 and build at B2\n"
            "You can include additional text in your messages, but you must only mention the valid move pattern once.\n"
        )

        if self.is_open:
            prompt += f"\nCurrent board state:\n{create_board_str(self.board)}\n"

        if self.show_valid:
            prompt += f"\nValid moves: {game_state['valid_moves']}"

        return prompt

    def _get_valid_moves(self, player_id: int) -> str:
        """Get all valid moves for the current player."""
        valid_moves = []
        
        # Find worker positions
        worker_positions = []
        for row in range(self.rows):
            for col in range(self.cols):
                if self.board[row][col][1] is not None:
                    if self.board[row][col][1][0] == player_id:
                        worker_positions.append((row, col, self.board[row][col][1][1]))

        # For each worker
        for worker_row, worker_col, worker_num in worker_positions:
            # Check each adjacent square for movement
            for move_row in range(max(0, worker_row - 1), min(self.rows, worker_row + 2)):
                for move_col in range(max(0, worker_col - 1), min(self.cols, worker_col + 2)):
                    if self._is_valid_move(worker_row, worker_col, move_row, move_col):
                        # Create a temporary board state with the worker moved
                        temp_board = [row[:] for row in self.board]
                        worker_height = temp_board[worker_row][worker_col][0]
                        temp_board[worker_row][worker_col] = (worker_height, None)
                        temp_board[move_row][move_col] = (temp_board[move_row][move_col][0], (player_id, worker_num))
                        
                        # After moving, check each adjacent square for building
                        for build_row in range(max(0, move_row - 1), min(self.rows, move_row + 2)):
                            for build_col in range(max(0, move_col - 1), min(self.cols, move_col + 2)):
                                # Check if build location is valid on temporary board
                                if self._is_valid_build(temp_board, 
                                                        move_row, move_col,
                                                        build_row, build_col):
                                    # Get worker identifier based on player color
                                    color_prefix = self.PLAYER_COLORS[player_id][0]
                                    move = f"[{color_prefix}{worker_num}{chr(65+worker_row)}{worker_col+1}" \
                                          f"{chr(65+move_row)}{move_col+1}" \
                                          f"{chr(65+build_row)}{build_col+1}]"
                                    valid_moves.append(move)

        return ", ".join(valid_moves)

    def _is_valid_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Check if a move is valid.
        
        A move is valid if:
        1. The destination is adjacent to the current position
        2. The destination is not occupied by another worker
        3. The destination does not have a dome
        4. The height difference between current and destination is not more than 1 level
        
        Args:
            from_row: Current row position (0-4 corresponding to A-E)
            from_col: Current column position (0-4 corresponding to 1-5)
            to_row: Destination row position
            to_col: Destination column position
            
        Returns:
            bool: True if the move is valid, False otherwise
        """
        # Can't move to same position
        if from_row == to_row and from_col == to_col:
            return False
            
        # Check if destination is adjacent
        if abs(to_row - from_row) > 1 or abs(to_col - from_col) > 1:
            return False

        # Check if destination is occupied
        if self.board[to_row][to_col][1] is not None:
            return False

        # Check if destination has a dome
        if self.board[to_row][to_col][0] == 4:
            return False

        # Check height difference
        height_diff = self.board[to_row][to_col][0] - self.board[from_row][from_col][0]
        if height_diff > 1:
            return False

        return True

    def _is_valid_build(self, 
                        board, 
                        worker_row: int, 
                        worker_col: int, 
                        build_row: int, 
                        build_col: int) -> bool:
        """Check if building at the specified location is valid.
        
        A build is valid if:
        1. The build location is adjacent to the worker's position
        2. The build location is not occupied by any worker
        3. The build location does not have a dome (level 4)
        
        Args:
            board: Current board state
            worker_row: Worker's row position (0-4 corresponding to A-E)
            worker_col: Worker's column position (0-4 corresponding to 1-5)
            build_row: Build location row position
            build_col: Build location column position
            
        Returns:
            bool: True if the build is valid, False otherwise
        """
        # Check if build location is adjacent to worker
        if abs(build_row - worker_row) > 1 or abs(build_col - worker_col) > 1:
            return False

        # Can't build where worker is
        if build_row == worker_row and build_col == worker_col:
            return False
            
        # Can't build where another worker is
        if board[build_row][build_col][1] is not None:
            return False
            
        # Can't build on a dome
        if board[build_row][build_col][0] >= 4:
            return False
            
        return True

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Process the player's move."""
        # Update the log
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        # Execute move
        if not self._execute_player_move(action=action):
            return self.state.step()  # Return early if move was invalid
        
        # Update valid moves for next player
        next_player = (player_id + 1) % self.state.num_players
        next_moves = self._get_valid_moves(next_player)
        self.state.game_state["valid_moves"] = next_moves
        
        # Check if game is over
        self._check_gameover()

        # Add board state to observations if game is open
        if self.is_open:
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,
                message=create_board_str(self.board),
                observation_type = ta.ObservationType.GAME_BOARD
            )

        return self.state.step()

    def _execute_player_move(self, action: str):
        """Execute the player's move based on the action string."""
        player_id = self.state.current_player_id
        match = self.move_pattern.search(action.strip())

        # Check if a move was provided
        if match is None:
            self.state.set_invalid_move(
                reason=f"Invalid move format. Expected format: [worker_id source dest build], e.g. [N1C1C2B2]"
            )
            return False
        

        # Extract move components
        worker_id = match.group(1)  # Now contains N1/N2/W1/W2/G1/G2
        worker_num = int(worker_id[1])  # Extract number from worker ID
        
        # Map worker prefix to player ID
        prefix_to_player = {'N': 0, 'W': 1, 'G': 2}
        expected_player = prefix_to_player[worker_id[0].upper()]
        
        # Validate player is moving their own worker
        if player_id != expected_player:
            self.state.set_invalid_move(
                reason=f"Cannot move {self.PLAYER_COLORS[expected_player]} worker (you are {self.PLAYER_COLORS[player_id]})"
            )
            return False
        source = match.group(2).upper()
        dest = match.group(3).upper()
        build = match.group(4).upper()

        # Convert coordinates
        source_row = ord(source[0]) - 65
        source_col = int(source[1]) - 1
        dest_row = ord(dest[0]) - 65
        dest_col = int(dest[1]) - 1
        build_row = ord(build[0]) - 65
        build_col = int(build[1]) - 1

        # Validate worker ownership
        if self.board[source_row][source_col][1] != (player_id, worker_num):
            self.state.set_invalid_move(
                reason=f"No worker {worker_num} at position {source}"
            )
            return False

        # Validate move
        # print(f"Validating move from ({source_row},{source_col}) to ({dest_row},{dest_col})")
        # print(f"Source height: {self.board[source_row][source_col][0]}")
        # print(f"Dest height: {self.board[dest_row][dest_col][0]}")
        if not self._is_valid_move(source_row, source_col, dest_row, dest_col):
            # print("Move validation failed")
            self.state.set_invalid_move(
                reason=f"Invalid move from {source} to {dest}"
            )
            return False

        # Create temporary board state to validate build
        temp_board = [row[:] for row in self.board]
        worker_height = temp_board[source_row][source_col][0]
        temp_board[source_row][source_col] = (worker_height, None)
        temp_board[dest_row][dest_col] = (temp_board[dest_row][dest_col][0], (player_id, worker_num))

        # Validate build with updated worker position
        # print(f"Validating build at ({build_row},{build_col})")
        # print(f"Build location height: {temp_board[build_row][build_col][0]}")
        # print(f"Build location worker: {temp_board[build_row][build_col][1]}")
        if not self._is_valid_build(temp_board,
                                    dest_row, dest_col,
                                    build_row, build_col):
            # print("Build validation failed")
            self.state.set_invalid_move(
                reason=f"Invalid build at {build}"
            )
            return False

        # Get heights
        source_height = self.board[source_row][source_col][0]
        dest_height = self.board[dest_row][dest_col][0]
        
        # Execute move: clear source cell and move worker to destination
        self.board[source_row][source_col] = (source_height, None)  # Keep source height
        self.board[dest_row][dest_col] = (dest_height, (player_id, worker_num))  # Keep dest height
        
        # Execute build
        build_height = self.board[build_row][build_col][0]
        if build_height == 3:
            self.board[build_row][build_col] = (4, None)  # Place dome
        else:
            self.board[build_row][build_col] = (build_height + 1, None)

        # Log the move
        message = f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) moved worker {worker_num} from {source} to {dest} and built at {build}"
        self.state.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message, observation_type = ta.ObservationType.GAME_ACTION_DESCRIPTION)
        
        return True

    def _check_gameover(self):
        """Check if the game has ended and set the appropriate state.
        
        A player wins if:
        1. They have a worker on level 3 (can only happen by moving there)
        2. The next player has no valid moves
        """
        player_id = self.state.current_player_id

        # Check if any player has a worker on level 3
        for row in range(self.rows):
            for col in range(self.cols):
                if (self.board[row][col][1] is not None and 
                    self.board[row][col][0] == 3):  # Found a worker on level 3
                    winner_id = self.board[row][col][1][0]  # Get player_id of the worker
                    self.state.set_winners(
                        player_ids=[winner_id],
                        reason=f"Player {winner_id} ({self.PLAYER_COLORS[winner_id]}) won by moving a worker to level 3!"
                    )
                    return

        # Check if current player has any valid moves
        current_moves = self._get_valid_moves(player_id)
        # print(f"Current player {player_id} valid moves: {current_moves}")
        if not current_moves:
            # Current player has no moves, next player wins
            next_player = (player_id + 1) % self.state.num_players
            self.state.set_winners(
                player_ids=[next_player],
                reason=f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) has no valid moves. " \
                       f"Player {next_player} ({self.PLAYER_COLORS[next_player]}) wins!"
            )
            return

        # Check if next player has any valid moves
        next_player = (player_id + 1) % self.state.num_players
        next_moves = self._get_valid_moves(next_player)
        # print(f"Next player {next_player} valid moves: {next_moves}")
        if not next_moves:
            # Next player has no moves, current player wins
            self.state.set_winners(
                player_ids=[player_id],
                reason=f"Player {next_player} ({self.PLAYER_COLORS[next_player]}) has no valid moves. " \
                       f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) wins!"
            )
            return
