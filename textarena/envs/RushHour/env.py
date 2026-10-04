import re
from typing import Any, Dict, List, Optional, Tuple, Union

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
            if forward:  return (self.row, self.col + self.length)  # →
            else:        return (self.row, self.col - 1)  # ←
        else:
            if forward:  return (self.row + self.length, self.col)  # ↓
            else:        return (self.row - 1, self.col)  # ↑

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


class RushHourEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False

    BOARD_SIZE = 6
    MAX_ACTION_CHARS = 4096
    MAX_SEARCH_STATES = 50000  # Bound malformed/custom layouts without cutting off searches on generated puzzles.
    ACTION_RE = re.compile(r"(?P<id>[A-Z])\s*(?P<dir>[+-])", re.I)

    def __init__(self, difficulty: str = "medium", max_turns: int = 100):
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("difficulty must be 'easy', 'medium', or 'hard'")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        self.difficulty = difficulty  # "easy", "medium", "hard"
        self.max_turns = max_turns
        self.initial_layout: List[_Vehicle] = []

    def setup(self) -> Dict[str, Any]:
        # Generation starts from a state with a clear exit and applies only
        # reversible legal moves, so every candidate is solvable by construction.
        max_attempts = 100
        for _ in range(max_attempts):
            candidate = self._generate_random_puzzle(self.rng)
            vehicles_dict = {v.vid: v.copy() for v in candidate}

            if not self._is_solved_state(vehicles_dict):
                self.initial_layout = candidate
                break
        else:
            raise RuntimeError(
                f"Could not generate a solvable {self.difficulty} puzzle "
                f"after {max_attempts} attempts"
            )

        return {"vehicles": {v.vid: v.copy() for v in self.initial_layout}}

    def _generate_random_puzzle(self, rng) -> List[_Vehicle]:
        """Generate a random solvable puzzle by working backwards from solution."""

        # Start with a NON-solved state - red car not at exit but in exit row
        # We'll place it somewhere that can reach the exit
        red_start_col = rng.randint(0, 2)  # Can be at columns 0, 1, or 2 (not 3, which is too close to exit at 4)
        initial_vehicles = [
            _Vehicle("X", 2, red_start_col, 2, True),  # Red car in exit row but not at exit
        ]
        clear_exit_cells = {
            (2, col)
            for col in range(red_start_col + initial_vehicles[0].length, self.BOARD_SIZE)
        }

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
            rng.shuffle(positions)
            for row, col in positions:
                if vid not in used_letters:
                    vehicle = _Vehicle(vid, row, col, length, horizontal)
                    # Check if this vehicle would be valid
                    if (
                        self._is_vehicle_valid(vehicle, initial_vehicles)
                        and clear_exit_cells.isdisjoint(vehicle.cells())
                    ):
                        initial_vehicles.append(vehicle)
                        used_letters.add(vid)
                        break

        # Apply backward scrambling to create the puzzle
        scramble_moves = {"easy": 12, "medium": 20, "hard": 35}[self.difficulty]
        puzzle_vehicles = self._scramble_puzzle(initial_vehicles, scramble_moves, rng)

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

    def _scramble_puzzle(self, vehicles: List[_Vehicle], num_moves: int, rng) -> List[_Vehicle]:
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
            rng.shuffle(possible_moves)

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
                vid, forward = rng.choice(possible_moves)
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
        return self._moves_to_solve({v.vid: v for v in vehicles}) is not None

    def _moves_to_solve(self, vehicles: Dict[str, _Vehicle], max_moves: Optional[int] = None) -> Optional[int]:
        """Fewest moves (including the final 'X+' through the exit) that solve the layout, found by breadth-first search.

        Returns None if that takes more than `max_moves` moves or the search exceeds MAX_SEARCH_STATES positions.
        """
        frontier = [{vid: v.copy() for vid, v in vehicles.items()}]
        if self._is_solved_state(frontier[0]):
            return 0
        seen = {self._get_state_hash(frontier[0])}
        moves = 0
        while frontier and (max_moves is None or moves < max_moves) and len(seen) <= self.MAX_SEARCH_STATES:
            moves += 1
            next_frontier = []
            for current_vehicles in frontier:
                for vid, vehicle in current_vehicles.items():
                    for forward in (True, False):
                        if not self._can_move(current_vehicles, vehicle, forward):
                            continue
                        new_vehicles = {v.vid: v.copy() for v in current_vehicles.values()}
                        new_vehicles[vid].move(forward)
                        if self._is_solved_state(new_vehicles):
                            return moves
                        state_hash = self._get_state_hash(new_vehicles)
                        if state_hash not in seen:
                            seen.add(state_hash)
                            next_frontier.append(new_vehicles)
            frontier = next_frontier
        return None

    def _is_solved_state(self, vehicles: Dict[str, _Vehicle]) -> bool:
        """Check if the puzzle is in solved state."""
        x = vehicles["X"]
        return (x.horizontal and x.row == 2 and
                x.col > self.BOARD_SIZE - x.length)

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing a {self.difficulty} RushHour puzzle. Slide cars to free the red car 'X' and drive it out the right edge.\n"
            "On the board each letter is one vehicle and '.' is an empty square; the exit '>' is at the right end of X's row (the third row).\n"
            "Actions: a vehicle letter followed by '+' or '-', e.g. 'X+' or 'X-'. Each action slides one vehicle by one square:\n"
            "'+' moves a horizontal vehicle right or a vertical vehicle down; '-' moves it left or up.\n"
            "Vehicles cannot pass through each other or leave the board, except X through the exit: once X touches the exit, "
            "one more 'X+' drives it out and solves the puzzle.\n"
            f"You have {self.max_turns} moves."
        )

    def render(self, player_id: int) -> str:
        return self._render_board()

    def _render_board(self) -> str:
        board = [["."] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        for v in self.game_state["vehicles"].values():
            for (r, c) in v.cells():
                if 0 <= r < self.BOARD_SIZE and 0 <= c < self.BOARD_SIZE:
                    if board[r][c] != ".":
                        raise ValueError(
                            f"Vehicles {board[r][c]} and {v.vid} overlap at ({r}, {c})"
                        )
                    board[r][c] = v.vid
        # Mark exit
        board[2].append(">")  # row 2 (zero‑indexed) is exit row
        lines = [" ".join(row) for row in board]
        return "\n" + "\n".join(lines)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.MAX_ACTION_CHARS:
            return self.invalid(
                f"Action is too long (maximum {self.MAX_ACTION_CHARS} characters)."
            )
        action_text = move.strip()
        match = self.ACTION_RE.fullmatch(action_text)
        if not match:
            return self.invalid("Invalid action. Use format 'A+' / 'B-'.")

        car_id = match.group("id").upper()
        forward = match.group("dir") == "+"

        vehicles: Dict[str, _Vehicle] = self.game_state["vehicles"]
        if car_id not in vehicles:
            return self.invalid(f"No car '{car_id}' on the board.")

        moved = self._try_move(vehicles[car_id], forward)
        if not moved:
            return self.invalid("Move blocked.")

        # Check win condition
        if self._is_solved():
            self.broadcast("The red car zooms out! You solved the puzzle.", ta.ObservationType.GAME_MESSAGE)
            return self.outcome({0: 1.0}, reason="Puzzle solved!")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome(
            {0: self._get_percentage_completion()},
            reason="Move limit reached. Puzzle unfinished.",
        )

    def _occupied(self) -> List[List[Optional[str]]]:
        grid: List[List[Optional[str]]] = [[None] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE)]
        for v in self.game_state["vehicles"].values():
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
        x = self.game_state["vehicles"]["X"]
        # The red car must actually cross the right edge, not merely reach it.
        return (x.horizontal and x.row == 2 and
                x.col > self.BOARD_SIZE - x.length)

    def _get_percentage_completion(self) -> float:
        """Share of the starting layout's solution length (in moves) that the current layout has cut: 0.0 to below 1.0."""
        start_moves = self._moves_to_solve({v.vid: v for v in self.initial_layout})
        if not start_moves:
            return 0.0
        # Layouts at least as far from a solution as the start score 0, so the search can stop one move short of it.
        moves_left = self._moves_to_solve(self.game_state["vehicles"], max_moves=start_moves - 1)
        if moves_left is None:
            return 0.0
        return (start_moves - moves_left) / start_moves
