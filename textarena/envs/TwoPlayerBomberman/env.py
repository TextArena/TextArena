import re, random
from typing import Any, Dict, Optional, Tuple, List
import numpy as np

import textarena as ta


class TwoPlayerBombermanEnv(ta.Env):
    """Environment for playing a turn-based adaptation of Bomberman for two players."""

    def __init__(self, 
                 grid_size: int = 10, 
                 max_turns: int = 100, 
                 bomb_timer: int = 6, 
                 bomb_radius: int = 2,
                 wall_density: float = 0.3):
        """
        Initialize the Two-Player Bomberman environment.
        Args:
            grid_size (int): Size of the square grid arena.
            max_turns (int): Maximum number of turns before the game ends.
            bomb_timer (int): Number of turns before a bomb explodes.
            bomb_radius (int): Radius of bomb explosions.
            wall_density (float): Density of destructible walls (0.0 to 1.0).
        """
        self.grid_size = grid_size
        self.bomb_timer = bomb_timer
        self.bomb_radius = bomb_radius
        self.wall_density = wall_density

        # Initialize game state variables
        self.state = ta.State(
            num_players=2,
            max_turns=max_turns,
            role_mapping={0: "Player 1", 1: "Player 2"}
        )
        
        # Track the first turn ourselves
        self.is_first_turn = True
        # Track current turn number
        self.current_turn = 0
        # Track max turns from parameters
        self.max_turns = max_turns
        
        # Grid elements
        self.EMPTY = " "
        self.INDESTRUCTIBLE_WALL = "#"
        self.DESTRUCTIBLE_WALL = "+"
        self.PLAYER_SYMBOLS = ["1", "2"]
        self.BOMB = "B"
        self.EXPLOSION = "*"
        
        # Game state
        self.grid = None
        self.player_positions = None
        self.bombs = []  # List of [x, y, timer] for each bomb
        self.explosions = []  # List of [x, y, timer] for each explosion cell
        
        # Regex patterns for actions
        self.move_pattern = re.compile(r"\[(up|down|left|right|stay|bomb)\]", re.IGNORECASE)

    @property
    def offline_renderer(self):
        # This would be implemented in a separate file
        from textarena.envs.two_player.Bomberman.render.renderer import BombermanRenderer
        return BombermanRenderer

    @property
    def terminal_render_keys(self):
        return ["current_board"]

    def reset(self, seed: Optional[int] = None):
        """
        Reset the game to its initial state.
        Args:
            seed (Optional[int]): Seed for random number generator to ensure reproducibility.
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        # Reset turn counters
        self.is_first_turn = True
        self.current_turn = 0
            
        # Initialize the grid
        self._initialize_grid()
        
        # Place players in opposite corners
        self.player_positions = [
            [1, 1],  # Player 1 starts at top-left (with buffer)
            [self.grid_size - 2, self.grid_size - 2]  # Player 2 starts at bottom-right (with buffer)
        ]
        
        # Clear area around starting positions
        for player_pos in self.player_positions:
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    x, y = player_pos[0] + dx, player_pos[1] + dy
                    if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                        if self.grid[y][x] == self.DESTRUCTIBLE_WALL:
                            self.grid[y][x] = self.EMPTY
        
        # Clear bomb and explosion lists
        self.bombs = []
        self.explosions = []
        
        # Generate the current board string
        board_str = self._generate_board_string()
        
        # Reset game state
        self.state.reset(
            game_state={
                "current_board": board_str,
                "valid_moves": "Valid moves: [up], [down], [left], [right], [stay], [bomb]",
                "turn_info": f"Turn: 0/{self.max_turns}"
            },
            player_prompt_function=self._generate_player_prompt
        )

    def _initialize_grid(self):
        """Initialize the grid with walls and empty spaces."""
        # Create empty grid
        self.grid = [[self.EMPTY for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        
        # Add indestructible walls in a pattern (every other cell on the edges and in a grid pattern)
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if (i == 0 or i == self.grid_size - 1 or j == 0 or j == self.grid_size - 1 or
                    (i % 2 == 0 and j % 2 == 0)):
                    self.grid[i][j] = self.INDESTRUCTIBLE_WALL
        
        # Add destructible walls randomly
        for i in range(1, self.grid_size - 1):
            for j in range(1, self.grid_size - 1):
                if self.grid[i][j] == self.EMPTY and random.random() < self.wall_density:
                    self.grid[i][j] = self.DESTRUCTIBLE_WALL

    def _generate_board_string(self) -> str:
        """Generate a string representation of the current board state."""
        # Create a copy of the grid for rendering
        render_grid = [row[:] for row in self.grid]
        
        # Remove any player symbols that might be on the grid from previous states
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if render_grid[i][j] in self.PLAYER_SYMBOLS:
                    render_grid[i][j] = self.EMPTY
        
        # Add bombs to the rendering grid
        for bomb in self.bombs:
            x, y, _ = bomb
            render_grid[y][x] = self.BOMB
        
        # Add explosions to the rendering grid
        for expl in self.explosions:
            x, y, _ = expl
            render_grid[y][x] = self.EXPLOSION
        
        # Add players to the rendering grid AFTER bombs and explosions
        # so players are always visible on top
        for i, pos in enumerate(self.player_positions):
            if pos is not None:  # Player is still alive
                render_grid[pos[1]][pos[0]] = self.PLAYER_SYMBOLS[i]
        
        # Convert grid to string with pixel-art style
        # Using a simple box-drawing approach for clarity
        board_str = "╔" + "═" * self.grid_size * 2 + "╗\n"
        
        for row in render_grid:
            board_str += "║"
            for cell in row:
                board_str += cell + " "
            board_str += "║\n"
        
        board_str += "╚" + "═" * self.grid_size * 2 + "╝"
        
        return board_str

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        """
        Generate the initial prompt for a player.
        Args:
            player_id (int): ID of the player (0 for Player 1, 1 for Player 2).
            game_state (Dict[str, Any]): Current game state.
        Returns:
            str: The initial prompt for the player.
        """
        player_name = "Player 1" if player_id == 0 else "Player 2"
        prompt = (
            f"You are {player_name} in a turn-based Bomberman game.\n"
            "Make your move by using one of these commands enclosed in square brackets:\n"
            "[up] - Move up one space\n"
            "[down] - Move down one space\n"
            "[left] - Move left one space\n"
            "[right] - Move right one space\n"
            "[stay] - Stay in place\n"
            "Tip: Bombs explode after 6 total turns, so 3 turns for each player!\n"
            "[bomb] - Place a bomb at your current position\n\n"
            "You can include additional text in your messages.\n\n"
        )
        
        prompt += f"Current board state:\n{game_state['current_board']}\n\n"
        
        # Display turn information
        prompt += f"{game_state['turn_info']}\n\n"
        
        legend = (
            "Legend:\n"
            f"{self.PLAYER_SYMBOLS[0]} - Player 1\n"
            f"{self.PLAYER_SYMBOLS[1]} - Player 2\n"
            f"{self.INDESTRUCTIBLE_WALL} - Indestructible Wall\n"
            f"{self.DESTRUCTIBLE_WALL} - Destructible Wall\n"
            f"{self.BOMB} - Bomb (explodes after {self.bomb_timer} turns)\n"
            f"{self.EXPLOSION} - Explosion\n"
            f"{self.EMPTY} - Empty Space\n\n"
        )
        
        prompt += legend
        
        # Show bomb information
        if self.bombs:
            prompt += "Active bombs:\n"
            for i, bomb in enumerate(self.bombs):
                x, y, timer = bomb
                prompt += f"Bomb {i+1}: Position ({x}, {y}), explodes in {timer} turn(s)\n"
            prompt += "\n"
        
        # Show player positions
        prompt += "Player positions:\n"
        for i, pos in enumerate(self.player_positions):
            if pos is not None:
                prompt += f"Player {i+1}: Position ({pos[0]}, {pos[1]})\n"
            else:
                prompt += f"Player {i+1}: Eliminated\n"
        prompt += "\n"
        
        # Check if this is the first turn for Player 1 using our class variable
        if player_id == 0 and self.is_first_turn:
            prompt += "Please make the first move.\n\n"
        
        prompt += f"{game_state['valid_moves']}"
        
        return prompt

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """
        Process the player's move.
        Args:
            action (str): The move enclosed in square brackets (e.g., [up], [bomb]).
        Returns:
            tuple: (done, info)
        """
        # Update the log
        self.state.add_observation(
            from_id=self.state.current_player_id,
            to_id=-1,  # Broadcast
            message=action,
            for_logging=True
        )

        # Execute player move
        self._execute_player_move(
            player_id=self.state.current_player_id, 
            action=action
        )
        
        # Update bomb timers and handle explosions
        self._update_bombs_and_explosions()
        
        # After both players have moved, increment turn counter
        if self.state.current_player_id == 1:  # After Player 2's turn
            self.current_turn += 1
            # Update turn information in game state
            self.state.game_state["turn_info"] = f"Turn: {self.current_turn}/{self.max_turns}"
            
            # Check for max turns reached
            if self.current_turn >= self.max_turns:
                # Game ends in a draw due to reaching max turns
                alive_players = [i for i, pos in enumerate(self.player_positions) if pos is not None]
                if len(alive_players) > 1:
                    self.state.set_draw(
                        reason=f"Maximum turns ({self.max_turns}) reached. The game ends in a draw."
                    )
        
        # Check for game over conditions
        self._check_gameover()
        
        # Update board state string
        board_str = self._generate_board_string()
        self.state.game_state["current_board"] = board_str
        
        # Add observations
        self._augment_observations()
        
        # After the first player's move, set first_turn to False
        if self.is_first_turn and self.state.current_player_id == 0:
            self.is_first_turn = False

        return self.state.step()

    def _execute_player_move(self, player_id: int, action: str):
        """Execute the player's move based on the action string."""
        match = self.move_pattern.search(action.strip())
        
        # Check if a move was provided
        if match is None:
            self.state.set_invalid_move(
                player_ids=[player_id],
                reasons=[f"Player {player_id + 1} did not provide a valid move."]
            )
            return
        
        # Extract the move from within the brackets
        move = match.group(1).lower()
        
        # Current player position
        if self.player_positions[player_id] is None:
            self.state.set_invalid_move(
                player_ids=[player_id],
                reasons=[f"Player {player_id + 1} has been eliminated and cannot move."]
            )
            return
            
        x, y = self.player_positions[player_id]
        
        # Process the move
        new_x, new_y = x, y
        message = ""
        
        if move == "bomb":
            # Place a bomb at the current position
            self.bombs.append([x, y, self.bomb_timer])
            message = f"Player {player_id + 1} placed a bomb at position ({x}, {y})."
            
            # Add the observation for the bomb placement
            self.state.add_observation(
                from_id=ta.GAME_ID,
                to_id=-1,  # Broadcast to all
                message=message
            )
            return  # Exit the method early since we've handled the bomb placement
            
        # Handle movement
        if move == "up":
            new_y = max(0, y - 1)
            direction = "up"
        elif move == "down":
            new_y = min(self.grid_size - 1, y + 1)
            direction = "down"
        elif move == "left":
            new_x = max(0, x - 1)
            direction = "left"
        elif move == "right":
            new_x = min(self.grid_size - 1, x + 1)
            direction = "right"
        elif move == "stay":
            direction = "in place"
        else:
            self.state.set_invalid_move(
                player_ids=[player_id],
                reasons=[f"Player {player_id + 1} provided an invalid move: {move}"]
            )
            return
        
        # Check if the new position is valid
        if new_x == x and new_y == y and move != "stay":
            message = f"Player {player_id + 1} tried to move {direction} but hit a boundary."
        elif (self.grid[new_y][new_x] == self.INDESTRUCTIBLE_WALL or 
                self.grid[new_y][new_x] == self.DESTRUCTIBLE_WALL):
            message = f"Player {player_id + 1} tried to move {direction} but hit a wall."
        elif any(b[0] == new_x and b[1] == new_y for b in self.bombs):
            message = f"Player {player_id + 1} tried to move {direction} but hit a bomb."
        elif any(p is not None and p[0] == new_x and p[1] == new_y for i, p in enumerate(self.player_positions) if i != player_id):
            message = f"Player {player_id + 1} tried to move {direction} but another player is there."
        else:
            # Valid move, update player position
            self.player_positions[player_id] = [new_x, new_y]
            if move == "stay":
                message = f"Player {player_id + 1} stayed in place."
            else:
                message = f"Player {player_id + 1} moved {direction} to position ({new_x}, {new_y})."
        
        # Add message to observations
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,  # Broadcast to all
            message=message
        )

    def _update_bombs_and_explosions(self):
        """Update bomb timers, handle explosions, and clear old explosions."""
        # Update explosion timers and remove expired explosions
        new_explosions = []
        for x, y, timer in self.explosions:
            if timer > 1:
                new_explosions.append([x, y, timer - 1])
        self.explosions = new_explosions
        
        # Update bomb timers and handle explosions
        new_bombs = []
        for x, y, timer in self.bombs:
            if timer > 1:
                new_bombs.append([x, y, timer - 1])
            else:
                # Bomb explodes
                self._create_explosion(x, y)
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=f"Bomb at position ({x}, {y}) exploded!"
                )
        self.bombs = new_bombs

    def _create_explosion(self, bomb_x: int, bomb_y: int):
        """Create an explosion at the bomb's position and in the four cardinal directions."""
        # Add center of explosion
        self._add_explosion_cell(bomb_x, bomb_y)
        
        # Explosion in four directions
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:  # up, right, down, left
            for r in range(1, self.bomb_radius + 1):
                x, y = bomb_x + dx * r, bomb_y + dy * r
                
                # Check bounds
                if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
                    break
                
                # Check for indestructible wall
                if self.grid[y][x] == self.INDESTRUCTIBLE_WALL:
                    break
                
                # Add explosion cell
                self._add_explosion_cell(x, y)
                
                # Stop explosion in this direction if it hit a destructible wall
                if self.grid[y][x] == self.DESTRUCTIBLE_WALL:
                    self.grid[y][x] = self.EMPTY  # Destroy the wall
                    break

    def _add_explosion_cell(self, x: int, y: int):
        """Add an explosion cell and check for player hits."""
        # Add to explosions with a timer (how long the explosion stays visible)
        self.explosions.append([x, y, 2])  # Explosion lasts for 2 turns
        
        # Check if any player is hit
        for player_id, pos in enumerate(self.player_positions):
            if pos is not None and pos[0] == x and pos[1] == y:
                # Player is hit by explosion
                self.player_positions[player_id] = None  # Remove player
                self.state.add_observation(
                    from_id=ta.GAME_ID,
                    to_id=-1,
                    message=f"Player {player_id + 1} was hit by an explosion and eliminated!"
                )

    def _check_gameover(self):
        """Check if the game has ended and set the appropriate state."""
        # Count alive players
        alive_players = [i for i, pos in enumerate(self.player_positions) if pos is not None]
        
        if len(alive_players) == 0:
            # Both players eliminated - it's a draw
            self.state.set_draw(
                reason="Both players have been eliminated. The game ends in a draw."
            )
        elif len(alive_players) == 1:
            # One player remains - they win
            winner_id = alive_players[0]
            self.state.set_winners(
                player_ids=[winner_id],
                reason=f"Player {winner_id + 1} wins! The other player has been eliminated."
            )
        # Game continues if both players are alive and max turns not reached

    def _augment_observations(self):
        """Add current board state and valid moves to observations."""
        # Display the board state
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,  # Broadcast to all
            message=self.state.game_state["current_board"],
            for_logging=False  # Already displayed in Game State section
        )
        
        # Display turn information
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,  # Broadcast to all
            message=self.state.game_state["turn_info"],
            for_logging=True
        )
        
        # Show the valid moves
        self.state.add_observation(
            from_id=ta.GAME_ID,
            to_id=-1,  # Broadcast to all
            message="Valid moves: [up], [down], [left], [right], [stay], [bomb]",
            for_logging=False  # Already displayed in Game State section
        )
