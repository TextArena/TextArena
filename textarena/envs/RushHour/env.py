import re
import random
from typing import Dict, List, Optional, Tuple, Any, Set
from collections import deque

import textarena as ta

class _Vehicle:
    __slots__ = ("vid", "row", "col", "length", "horizontal")

    def __init__(self, vid: str, row: int, col: int, length: int, horizontal: bool):
        self.vid = vid  # single‑letter identifier ("A"–"Z", "X" = target car)
        self.row = row
        self.col = col
        self.length = length
        self.horizontal = horizontal

    def cells(self) -> List[Tuple[int, int]]:
        return [(self.row + (i if not self.horizontal else 0), self.col + (i if self.horizontal else 0)) for i in range(self.length)]

    def front(self, forward: bool) -> Tuple[int, int]:
        """ Return the cell coordinate immediately *in front* of the vehicle if it moved by `+1` in the given direction (True = forward). """
        if self.horizontal:
            if forward:  return (self.row, self.col + self.length) # →
            else:        return (self.row, self.col - 1) # ←
        else:
            if forward:  return (self.row + self.length, self.col) # ↓
            else:        return (self.row - 1, self.col) # ↑

    def move(self, forward: bool):
        if self.horizontal: self.col += 1 if forward else -1
        else:               self.row += 1 if forward else -1

    def copy(self) -> '_Vehicle':
        return _Vehicle(self.vid, self.row, self.col, self.length, self.horizontal)

    def __eq__(self, other):
        return (self.vid == other.vid and self.row == other.row and 
                self.col == other.col and self.length == other.length and 
                self.horizontal == other.horizontal)

    def __hash__(self):
        return hash((self.vid, self.row, self.col, self.length, self.horizontal))


class RushHourEnv(ta.Env):
    BOARD_SIZE = 6
    ACTION_RE = re.compile(r"\[(?P<id>[A-Z])(?P<dir>[+-])\]", re.I)

    def __init__(self, difficulty: str = "medium"):
        super().__init__()
        self.difficulty = difficulty  # "easy", "medium", "hard"
        self.initial_layout = self._generate_random_puzzle()

    def _generate_random_puzzle(self) -> List[_Vehicle]:
        """Generate a random solvable puzzle by working backwards from solution."""
        
        # Start with a NON-solved state - red car not at exit but in exit row
        # We'll place it somewhere that can reach the exit
        red_start_col = random.randint(0, 2)  # Can be at columns 0, 1, or 2 (not 3, which is too close to exit at 4)
        initial_vehicles = [
            _Vehicle("X", 2, red_start_col, 2, True),  # Red car in exit row but not at exit
        ]
        
        # Generate random vehicles around the board
        vehicle_configs = [
            ("A", 2, False, [(0, 0), (0, 1), (1, 0), (1, 1)]),  # Vertical cars
            ("B", 3, False, [(0, 2), (0, 3), (0, 4)]),          # Long vertical trucks
            ("C", 2, False, [(0, 5), (1, 5), (3, 5), (4, 5)]),  # Vertical cars
            ("D", 2, True, [(0, 0), (1, 0), (3, 0), (4, 0)]),   # Horizontal cars
            ("F", 2, True, [(1, 3), (3, 1), (4, 1), (5, 1)]),   # Horizontal cars
            ("G", 3, False, [(3, 0), (4, 0)]),                  # Long vertical trucks
            ("H", 2, True, [(3, 3), (4, 3), (5, 3)]),           # Horizontal cars
            ("I", 2, False, [(3, 4), (4, 4)]),                  # Vertical cars
            ("J", 2, True, [(5, 0), (5, 2)]),                   # Horizontal cars
        ]
        
        # Randomly place vehicles
        used_letters = {"X"}
        for vid, length, horizontal, positions in vehicle_configs:
            if len(used_letters) >= 8:  # Limit number of vehicles
                break
                
            # Try random positions for this vehicle type
            random.shuffle(positions)
            for row, col in positions:
                if vid not in used_letters:
                    vehicle = _Vehicle(vid, row, col, length, horizontal)
                    # Check if this vehicle would be valid
                    if self._is_vehicle_valid(vehicle, initial_vehicles):
                        initial_vehicles.append(vehicle)
                        used_letters.add(vid)
                        break
        
        # Apply backward scrambling to create the puzzle
        scramble_moves = {"easy": 12, "medium": 20, "hard": 35}[self.difficulty]
        puzzle_vehicles = self._scramble_puzzle(initial_vehicles, scramble_moves)
        
        return puzzle_vehicles

    def _is_vehicle_valid(self, vehicle: _Vehicle, existing_vehicles: List[_Vehicle]) -> bool:
        """Check if a vehicle placement is valid (no overlaps, in bounds)."""
        cells = vehicle.cells()
        
        # Check bounds
        for r, c in cells:
            if not (0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE):
                return False
        
        # Check for overlaps with existing vehicles
        existing_cells = set()
        for v in existing_vehicles:
            for r, c in v.cells():
                existing_cells.add((r, c))
        
        for r, c in cells:
            if (r, c) in existing_cells:
                return False
                
        return True

    def _remove_overlapping_vehicles(self, vehicles: List[_Vehicle]) -> List[_Vehicle]:
        """Remove vehicles that overlap or are out of bounds."""
        grid = [[None] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        valid_vehicles = []
        
        for vehicle in vehicles:
            cells = vehicle.cells()
            # Check if all cells are in bounds and free
            valid = True
            for r, c in cells:
                if not (0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE):
                    valid = False
                    break
                if grid[r][c] is not None:
                    valid = False
                    break
            
            if valid:
                # Mark cells as occupied
                for r, c in cells:
                    grid[r][c] = vehicle.vid
                valid_vehicles.append(vehicle)
        
        return valid_vehicles

    def _scramble_puzzle(self, vehicles: List[_Vehicle], num_moves: int) -> List[_Vehicle]:
        """Apply random moves to create puzzle. Ensures red car is not at exit."""
        current_vehicles = {v.vid: v.copy() for v in vehicles}
        
        # Make sure we start with red car NOT at the exit
        red_car = current_vehicles["X"]
        if red_car.col + red_car.length >= self.BOARD_SIZE:
            # Move red car away from exit
            red_car.col = max(0, self.BOARD_SIZE - red_car.length - 1)
        
        moves_applied = 0
        attempts = 0
        max_attempts = num_moves * 3  # Prevent infinite loops
        
        while moves_applied < num_moves and attempts < max_attempts:
            attempts += 1
            
            # Get all possible moves
            possible_moves = []
            for vid, vehicle in current_vehicles.items():
                if self._can_move(current_vehicles, vehicle, True):
                    possible_moves.append((vid, True))
                if self._can_move(current_vehicles, vehicle, False):
                    possible_moves.append((vid, False))
            
            if not possible_moves:
                break
            
            # Try to make a move that doesn't solve the puzzle
            move_made = False
            random.shuffle(possible_moves)
            
            for vid, forward in possible_moves:
                # Make a temporary copy to test the move
                test_vehicles = {v.vid: v.copy() for v in current_vehicles.values()}
                test_vehicles[vid].move(forward)
                
                # Only apply the move if it doesn't solve the puzzle
                if not self._is_solved_state(test_vehicles):
                    current_vehicles[vid].move(forward)
                    moves_applied += 1
                    move_made = True
                    break
            
            # If no valid moves found, just make any move
            if not move_made and possible_moves:
                vid, forward = random.choice(possible_moves)
                current_vehicles[vid].move(forward)
                moves_applied += 1
        
        return list(current_vehicles.values())

    def _can_move(self, vehicles: Dict[str, _Vehicle], vehicle: _Vehicle, forward: bool) -> bool:
        """Check if a vehicle can move in the given direction."""
        # Create occupancy grid
        grid = [[None] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        for v in vehicles.values():
            for r, c in v.cells():
                if 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE:
                    grid[r][c] = v.vid
        
        # Check target cell
        rr, cc = vehicle.front(forward)
        
        # Special case: red car can exit to the right
        if (vehicle.vid == "X" and vehicle.horizontal and forward and 
            rr == vehicle.row and cc == self.BOARD_SIZE and
            vehicle.col == self.BOARD_SIZE - vehicle.length):
            return True
            
        # Check bounds and occupancy
        if not (0 <= rr < self.BOARD_SIZE and 0 <= cc < self.BOARD_SIZE):
            return False
        
        return grid[rr][cc] is None

    def _get_state_hash(self, vehicles: Dict[str, _Vehicle]) -> str:
        """Get a unique hash for the current state."""
        positions = []
        for vid in sorted(vehicles.keys()):
            v = vehicles[vid]
            positions.append(f"{vid}:{v.row},{v.col}")
        return "|".join(positions)

    def _is_solvable(self, vehicles: List[_Vehicle]) -> bool:
        """Use BFS to check if puzzle is solvable."""
        initial_vehicles = {v.vid: v.copy() for v in vehicles}
        
        # If already solved, return True
        if self._is_solved_state(initial_vehicles):
            return True
        
        visited = set()
        queue = deque([initial_vehicles])
        visited.add(self._get_state_hash(initial_vehicles))
        
        max_iterations = 1000  # Prevent infinite loops
        iterations = 0
        
        while queue and iterations < max_iterations:
            iterations += 1
            current_vehicles = queue.popleft()
            
            # Try all possible moves
            for vid, vehicle in current_vehicles.items():
                for forward in [True, False]:
                    if self._can_move(current_vehicles, vehicle, forward):
                        # Make move
                        new_vehicles = {v.vid: v.copy() for v in current_vehicles.values()}
                        new_vehicles[vid].move(forward)
                        
                        # Check if solved
                        if self._is_solved_state(new_vehicles):
                            return True
                        
                        # Add to queue if not visited
                        state_hash = self._get_state_hash(new_vehicles)
                        if state_hash not in visited:
                            visited.add(state_hash)
                            queue.append(new_vehicles)
        
        return False

    def _is_solved_state(self, vehicles: Dict[str, _Vehicle]) -> bool:
        """Check if the puzzle is in solved state."""
        x = vehicles["X"]
        return (x.horizontal and x.row == 2 and 
                x.col >= self.BOARD_SIZE - x.length)

    def reset(self, num_players: int, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        
        # Generate puzzle until we get a solvable one that's not already solved
        max_attempts = 20
        for attempt in range(max_attempts):
            self.initial_layout = self._generate_random_puzzle()
            vehicles_dict = {v.vid: v.copy() for v in self.initial_layout}
            
            # Make sure puzzle is solvable but not already solved
            if (self._is_solvable(self.initial_layout) and 
                not self._is_solved_state(vehicles_dict)):
                break
        else:
            print("Warning: Using potentially invalid puzzle after max attempts")
        
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        vehicles = {v.vid: v.copy() for v in self.initial_layout}
        self.state.reset(game_state={"vehicles": vehicles}, player_prompt_function=self._prompt)
        self._observe_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", difficulty=self.difficulty)

    def _render_board(self) -> str:
        board = [["."] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        for v in self.state.game_state["vehicles"].values():
            for (r, c) in v.cells():
                if 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE:
                    if board[r][c] != ".":
                        print(f"WARNING: Cell ({r},{c}) already occupied by {board[r][c]}, trying to place {v.vid}")
                    board[r][c] = v.vid
        # Mark exit
        board[2].append(">")  # row 2 (zero‑indexed) is exit row
        lines = [" ".join(row) for row in board]
        return "\n" + "\n".join(lines)

    def _observe_state(self):
        self.state.add_observation(message=self._render_board(), observation_type=ta.ObservationType.GAME_BOARD)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        match = self.ACTION_RE.fullmatch(action.strip())
        if not match:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "wrong_format"))
            return self.state.step()

        car_id = match.group("id").upper()
        forward = match.group("dir") == "+"

        vehicles: Dict[str, _Vehicle] = self.state.game_state["vehicles"]
        if car_id not in vehicles:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "no_car", car_id=car_id))
            return self.state.step()

        moved = self._try_move(vehicles[car_id], forward)
        if not moved:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "blocked"))
            return self.state.step()

        # Check win condition
        if self._is_solved():
            self.state.add_observation(message=self.m("game_message", "solved"), observation_type=ta.ObservationType.GAME_MESSAGE)
            self.state.set_outcome(reward=1.0, reason=self.m("outcome", "win"))
        else:
            self._observe_state()

        return self.state.step()

    def _occupied(self) -> List[List[Optional[str]]]:
        grid: List[List[Optional[str]]] = [[None] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        for v in self.state.game_state["vehicles"].values():
            for r, c in v.cells():
                if 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE:
                    grid[r][c] = v.vid
        return grid

    def _try_move(self, car: _Vehicle, forward: bool) -> bool:
        grid = self._occupied()
        rr, cc = car.front(forward)
        # Check target cell in‑bounds and free
        if not (0 <= rr < self.BOARD_SIZE and 0 <= cc < self.BOARD_SIZE):
            # Special case: red car exiting to the right is allowed
            # Only allow exit if the car is at the rightmost position (col 4 for length 2)
            if (car.vid == "X" and car.horizontal and forward and 
                rr == car.row and cc == self.BOARD_SIZE and 
                car.col == self.BOARD_SIZE - car.length):
                car.move(forward)
                return True
            return False
        if grid[rr][cc] is not None:
            return False
        # Move car one step
        car.move(forward)
        return True

    def _is_solved(self) -> bool:
        x = self.state.game_state["vehicles"]["X"]
        # Red car must be horizontal, in exit row (2), and at the rightmost position
        # For a length-2 car on a 6-column board, it must be at column 4 to exit
        return (x.horizontal and x.row == 2 and 
                x.col >= self.BOARD_SIZE - x.length)

    def _get_percentage_completion(self) -> float:
        """Heuristic: how close is the red car to the exit?"""
        x = self.state.game_state["vehicles"]["X"]
        if not x.horizontal or x.row != 2:
            return 0.0  # Red car not in exit row
        
        # Calculate distance to exit
        exit_position = self.BOARD_SIZE - x.length
        current_position = x.col
        max_distance = exit_position
        
        if current_position >= exit_position:
            return 1.0
        
        return current_position / max_distance if max_distance > 0 else 1.0