import re
from typing import Any, Dict, Optional, Union
import textarena as ta
from textarena.envs.Santorini.renderer import create_board_str

class SantoriniBaseFixedWorkerEnv(ta.GameEnv):
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

    min_players = 2
    max_players = 3

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

    is_open = ta.Param(True, "Whether the acting player is shown the board.")
    show_valid = ta.Param(True, "Whether the acting player is shown the list of their legal moves.")
    error_allowance = ta.Param(
        10, "The number of consecutive invalid moves a player may make; the next one counts as the escalation above.",
        min=0,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # The build coordinate is optional only for a winning move onto level 3.
        self.move_pattern = re.compile(
            r"^(N[12]|W[12]|G[12])\s*([A-E][1-5])\s*"
            r"([A-E][1-5])(?:\s*([A-E][1-5]))?$",
            re.IGNORECASE,
        )

        # Board dimensions
        self.rows = 5
        self.cols = 5

    @property
    def board(self):
        return self.game_state["board"]

    @board.setter
    def board(self, value):
        self.game_state["board"] = value

    def setup(self) -> Dict[str, Any]:
        # Each cell contains (height, worker)
        # height: 0-3 for levels, 4 for dome
        # worker: None or (player_id, worker_num)
        board = [[(0, None) for _ in range(self.cols)] for _ in range(self.rows)]

        # Set initial worker positions based on number of players
        for player_id, positions in enumerate(self.INITIAL_POSITIONS[self.state.num_players]):
            for worker_num, (row, col) in enumerate(positions, 1):
                board[row][col] = (0, (player_id, worker_num))

        game_state = {"board": board}
        self.state.game_state = game_state  # so _get_valid_moves can read the board
        game_state["valid_moves"] = self._get_valid_moves(0)  # Initial valid moves for first player
        return game_state

    def roles(self) -> Dict[int, str]:
        return {i: self.PLAYER_COLORS[i] for i in range(self.state.num_players)}

    def prompt(self, player_id: int) -> str:
        """Generate the initial prompt for a player."""
        color = self.PLAYER_COLORS[player_id]
        num_players = self.state.num_players
        example = self._get_valid_moves(player_id).split(", ")[0]
        if num_players == 2:
            blocked_rule = "   - Win if your opponent cannot make a legal turn (a move followed by a build)\n\n"
        else:
            blocked_rule = (
                "   - A player who cannot make a legal turn (a move followed by a build), or who makes too many invalid moves in a row, "
                "is eliminated and their workers are removed; the last player remaining wins\n\n"
            )
        prompt = (
            f"You are playing {color} in a game of Santorini with {num_players} players. "
            f"Turn order: {', '.join(self.PLAYER_COLORS[:num_players])}.\n\n"
            "The board is a 5x5 grid: rows are lettered A-E from top to bottom and columns are numbered 1-5 from left to right. "
            "Each player has two workers, written as the first letter of their color plus 1 or 2 (Navy N1/N2, White W1/W2, Grey G1/G2).\n\n"
            "Game Rules:\n"
            "1. Movement:\n"
            "   - On your turn, move one of your workers to an adjacent square (including diagonals)\n"
            "   - Cannot move to squares occupied by other workers or domes\n"
            "   - Can move up maximum one level, but can move down any number of levels\n\n"
            "2. Building:\n"
            "   - Then build with the worker you moved, on a square adjacent to its new position (the square it just left counts)\n"
            "   - Cannot build where any worker is standing\n"
            "   - Cannot build on top of a dome (level 4)\n"
            "   - Building adds one level (or creates a dome on level 3)\n\n"
            "3. Win Conditions:\n"
            "   - Win by moving up from level 2 to level 3; the turn ends before building, so the build square may be left out\n"
            f"{blocked_rule}"
            "Make your move in the format 'worker_id source dest build', written as one token.\n"
            f"Example: {example} means move {color} worker {example[1]} from {example[2:4]} to {example[4:6]} and build at {example[6:8]}\n"
            f"After more than {self.error_allowance} invalid moves in a row you lose{'' if num_players == 2 else ' (you are eliminated)'}.\n"
        )
        if not self.is_open:
            prompt += "The board is not shown in this game: keep track of it from the announced moves.\n"
        return prompt

    def render(self, player_id: int) -> Optional[str]:
        parts = []
        if self.is_open:
            parts.append(create_board_str(self.board))
        if self.show_valid and not self.state.done:
            parts.append(f"Valid moves: {self._get_valid_moves(player_id)}")
        return "\n".join(parts) if parts else None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        if len(self.state.alive_players) <= 2:
            self.game_state["valid_moves"] = ""
            return super().on_invalid_limit(player_id, reason)
        self.eliminate(player_id)
        self._remove_workers(player_id)
        self.broadcast(
            f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) was eliminated for repeated invalid moves, and their workers were removed.",
            ta.ObservationType.GAME_ADMIN,
        )
        return self._advance_or_eliminate_blocked(player_id)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = self.move_pattern.search(action.strip())

        # Check if a move was provided
        if match is None:
            return self.invalid("Invalid move format. Expected format: 'worker_id source dest build' as one token, e.g. 'N1C1C2B2'")

        # Extract move components
        worker_id = match.group(1)  # Now contains N1/N2/W1/W2/G1/G2
        worker_num = int(worker_id[1])  # Extract number from worker ID

        # Map worker prefix to player ID
        prefix_to_player = {'N': 0, 'W': 1, 'G': 2}
        expected_player = prefix_to_player[worker_id[0].upper()]

        # Validate player is moving their own worker
        if player_id != expected_player:
            return self.invalid(f"Cannot move {self.PLAYER_COLORS[expected_player]} worker (you are {self.PLAYER_COLORS[player_id]})")

        source = match.group(2).upper()
        dest = match.group(3).upper()
        build = match.group(4).upper() if match.group(4) else None

        # Convert coordinates
        source_row = ord(source[0]) - 65
        source_col = int(source[1]) - 1
        dest_row = ord(dest[0]) - 65
        dest_col = int(dest[1]) - 1
        build_row = ord(build[0]) - 65 if build else None
        build_col = int(build[1]) - 1 if build else None

        # Validate worker ownership
        if self.board[source_row][source_col][1] != (player_id, worker_num):
            return self.invalid(f"No worker {worker_num} at position {source}")

        # Validate move
        if not self._is_valid_move(source_row, source_col, dest_row, dest_col):
            return self.invalid(f"Invalid move from {source} to {dest}")

        source_height = self.board[source_row][source_col][0]
        dest_height = self.board[dest_row][dest_col][0]
        winning_move = source_height == 2 and dest_height == 3

        if not winning_move and build is None:
            return self.invalid("A non-winning move must include a build coordinate")

        # Create temporary board state to validate build
        temp_board = [row[:] for row in self.board]
        temp_board[source_row][source_col] = (source_height, None)
        temp_board[dest_row][dest_col] = (temp_board[dest_row][dest_col][0], (player_id, worker_num))

        # Validate build with updated worker position
        if not winning_move and not self._is_valid_build(temp_board, dest_row, dest_col, build_row, build_col):
            return self.invalid(f"Invalid build at {build}")

        # Execute move: clear source cell and move worker to destination
        self.board[source_row][source_col] = (source_height, None)  # Keep source height
        self.board[dest_row][dest_col] = (dest_height, (player_id, worker_num))  # Keep dest height

        if winning_move:
            self.game_state["valid_moves"] = ""
            self.broadcast(
                f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) moved worker "
                f"{worker_num} from {source} to {dest}.",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            return self.winner(
                player_id,
                reason=f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) won by moving up to level 3!",
            )

        # Execute build
        build_height = self.board[build_row][build_col][0]
        if build_height == 3:
            self.board[build_row][build_col] = (4, None)  # Place dome
        else:
            self.board[build_row][build_col] = (build_height + 1, None)

        # Log the move
        message = f"Player {player_id} ({self.PLAYER_COLORS[player_id]}) moved worker {worker_num} from {source} to {dest} and built at {build}"
        self.broadcast(message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

        return self._advance_or_eliminate_blocked(player_id)

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
                        source_height = self.board[worker_row][worker_col][0]
                        dest_height = self.board[move_row][move_col][0]
                        prefix = self.PLAYER_COLORS[player_id][0]
                        move_prefix = (
                            f"{prefix}{worker_num}{chr(65+worker_row)}{worker_col+1}"
                            f"{chr(65+move_row)}{move_col+1}"
                        )
                        if source_height == 2 and dest_height == 3:
                            valid_moves.append(move_prefix)
                            continue

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
                                    move = move_prefix + f"{chr(65+build_row)}{build_col+1}"
                                    valid_moves.append(move)

        return ", ".join(valid_moves)

    def _is_valid_move(self, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
        """Check if a move is valid.

        A move is valid if:
        1. The destination is adjacent to the current position
        2. The destination is not occupied by another worker
        3. The destination does not have a dome
        4. The height difference between current and destination is not more than 1 level
        """
        if not (
            0 <= from_row < self.rows and 0 <= from_col < self.cols
            and 0 <= to_row < self.rows and 0 <= to_col < self.cols
        ):
            return False

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

    def _is_valid_build(self, board, worker_row: int, worker_col: int, build_row: int, build_col: int) -> bool:
        """Check if building at the specified location is valid.

        A build is valid if:
        1. The build location is adjacent to the worker's position
        2. The build location is not occupied by any worker
        3. The build location does not have a dome (level 4)
        """
        if not (
            0 <= worker_row < self.rows and 0 <= worker_col < self.cols
            and 0 <= build_row < self.rows and 0 <= build_col < self.cols
        ):
            return False

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

    def _remove_workers(self, player_id: int):
        for row in range(self.rows):
            for col in range(self.cols):
                height, worker = self.board[row][col]
                if worker is not None and worker[0] == player_id:
                    self.board[row][col] = (height, None)

    def _advance_or_eliminate_blocked(self, player_id: int) -> Optional[ta.Outcome]:
        """Eliminate blocked players in turn order, then select the next actor."""
        candidate = self.state.next_alive_player(after=player_id)
        while candidate is not None:
            moves = self._get_valid_moves(candidate)
            if moves:
                self.game_state["valid_moves"] = moves
                self.set_next_player(candidate)
                return None
            self.eliminate(candidate)
            self._remove_workers(candidate)
            self.broadcast(
                f"Player {candidate} ({self.PLAYER_COLORS[candidate]}) was eliminated because they had no valid moves.",
                ta.ObservationType.GAME_ADMIN,
            )
            alive = self.state.alive_players
            if len(alive) == 1:
                self.game_state["valid_moves"] = ""
                return self.winner(alive[0], reason=f"Player {alive[0]} is the last player remaining.")
            candidate = self.state.next_alive_player(after=candidate)
        return self.draw(reason="No players remain.")
