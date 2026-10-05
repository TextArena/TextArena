import re
from collections import deque
from typing import Any, Dict, List, Tuple, Union

import textarena as ta


class FrozenLakeEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_action_chars = 4096

    size = ta.Param(4, "The width and height of the grid.", min=2, max=100)
    num_holes = ta.Param(
        3, "The exact number of holes. At most `(size - 1)²`, which fills every cell off the safe route.", min=0,
    )
    randomize_start_goal = ta.Param(
        False, "Start in a random corner instead of the top-left one, with the goal in the opposite corner.",
    )
    max_turns = ta.Param(
        100, "The number of valid moves allowed. It must be at least `2 × (size - 1)`, the length of the shortest "
             "route, so grids larger than 51 × 51 need a higher limit.", min=1,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        max_holes = (self.size - 1) ** 2
        if self.num_holes > max_holes:
            raise ValueError(
                f"num_holes must be at most {max_holes} for a solvable {self.size}x{self.size} grid"
            )
        if self.max_turns < 2 * (self.size - 1):
            raise ValueError(
                f"max_turns must be at least {2 * (self.size - 1)}, the length of the shortest path to the goal"
            )
        # Action mappings
        self.actions = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}

    def setup(self) -> Dict[str, Any]:
        grid, player_pos, goal_pos = self._generate_grid(randomize_start_goal=self.randomize_start_goal)
        return {"grid": grid, "player_pos": player_pos, "goal_pos": goal_pos, "start_pos": player_pos}

    def _generate_grid(self, randomize_start_goal: bool = False) -> Tuple[List[List[str]], Tuple[int, int], Tuple[int, int]]:
        """Generate an exact-hole grid around a guaranteed random safe path."""
        if randomize_start_goal:
            player_pos = self.rng.choice([(0, 0), (0, self.size-1), (self.size-1, 0), (self.size-1, self.size-1)])  # Choose a random corner for the player start
            goal_pos = (self.size - 1 - player_pos[0], self.size - 1 - player_pos[1])  # Set goal to be diagonally opposite
        else:
            # Default positions (top-left start, bottom-right goal)
            player_pos = (0, 0)
            goal_pos = (self.size - 1, self.size - 1)

        row_step = 1 if goal_pos[0] > player_pos[0] else -1
        col_step = 1 if goal_pos[1] > player_pos[1] else -1
        steps = (
            [(row_step, 0)] * abs(goal_pos[0] - player_pos[0])
            + [(0, col_step)] * abs(goal_pos[1] - player_pos[1])
        )
        self.rng.shuffle(steps)

        safe_path = {player_pos}
        row, col = player_pos
        for dr, dc in steps:
            row, col = row + dr, col + dc
            safe_path.add((row, col))

        available_positions = [
            (row, col)
            for row in range(self.size)
            for col in range(self.size)
            if (row, col) not in safe_path
        ]
        grid = [[' ' for _ in range(self.size)] for _ in range(self.size)]
        for row, col in self.rng.sample(available_positions, self.num_holes):
            grid[row][col] = 'H'
        grid[goal_pos[0]][goal_pos[1]] = 'G'
        return grid, player_pos, goal_pos

    def prompt(self, player_id: int) -> str:
        start = self.game_state["start_pos"]
        goal = self.game_state["goal_pos"]
        return (
            f"Welcome to Frozen Lake!\n\n"
            f"You are represented by 'P' on the grid.\n"
            f"Grid symbols:\n"
            f"  ' ' = Frozen surface (safe to walk on)\n"
            f"  'H' = Hole (fall in and lose!)\n"
            f"  'G' = Goal (reach this to win!)\n"
            f"  'P' = Your current position\n\n"
            f"Available actions: up, down, left, right (or w, a, s, d)\n"
            f"Reply with your action, e.g. 'up' or 'w'. Each action moves you one cell; moving off the grid is an invalid move.\n\n"
            f"Objective: Navigate from {start} to the goal at {goal} (row, column) "
            f"without falling into any holes! You have {self.max_turns} moves.\n"
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n\n{self._render_board()}\n\nAvailable Actions: " + ", ".join(["'up'", "'down'", "'left'", "'right'", "'w'", "'a'", "'s'", "'d'"])

    def _render_board(self) -> str:
        grid = self.game_state["grid"]
        player_pos = self.game_state["player_pos"]

        # Create a copy of the grid to display with player position
        display_grid = [row[:] for row in grid]  # Deep copy
        pr, pc = player_pos

        # If player is on goal, show both P and G
        if display_grid[pr][pc] == 'G':
            display_grid[pr][pc] = 'P/G'
        elif display_grid[pr][pc] == 'H':
            display_grid[pr][pc] = 'P/H'
        else:
            display_grid[pr][pc] = 'P'

        # Build the visual representation
        cell_width = 3  # Width for each cell
        def build_hline() -> str:
            line_parts = ["-" * (cell_width + 2) for _ in range(self.size)]
            return "+" + "+".join(line_parts) + "+"
        lines = []
        lines.append(build_hline())

        for r in range(self.size):
            row_cells = []
            for c in range(self.size):
                cell_content = display_grid[r][c]
                cell_str = f" {cell_content:^{cell_width}} "
                row_cells.append(cell_str)
            row_line = "|" + "|".join(row_cells) + "|"
            lines.append(row_line)
            lines.append(build_hline())
        return "\n".join(lines)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        action_text = move.strip()
        match = re.fullmatch(
            r"(up|down|left|right|w|a|s|d)",
            action_text,
            re.IGNORECASE,
        )
        if match is None:
            return self.invalid("Invalid action format. Use 'up', 'down', 'left', 'right' or 'w', 'a', 's', 'd'.")

        raw_action = match.group(1).lower()
        wasd_mapping = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}  # Map WASD to directional words
        action_name = wasd_mapping.get(raw_action, raw_action)
        if action_name not in self.actions:
            return self.invalid(f"Unknown action '{raw_action}'. Use up, down, left, right, or w, a, s, d.")

        dr, dc = self.actions[action_name]
        current_pos = self.game_state["player_pos"]
        new_r = current_pos[0] + dr
        new_c = current_pos[1] + dc

        # Check bounds
        if not (0 <= new_r < self.size and 0 <= new_c < self.size):
            return self.invalid(f"You tried to move {action_name} but hit a wall!")

        # Move to new position
        self.game_state["player_pos"] = (new_r, new_c)

        # Check what's at the new position
        cell_type = self.game_state["grid"][new_r][new_c]

        self.broadcast(f"You moved {action_name} to position ({new_r}, {new_c}).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        if cell_type == 'H':
            # Fell into a hole - game over with completion percentage
            return self.outcome({0: self._get_percentage_completion()}, reason=f"You fell into a hole! Game over. You completed {round(self._get_percentage_completion() * 100)}% of the journey to the goal.")
        elif cell_type == 'G':
            return self.outcome({0: 1.0}, reason="Congratulations! You reached the goal!")  # Reached the goal - win!
        else:
            self.broadcast("You're on safe ice. Keep going!", ta.ObservationType.GAME_MESSAGE)  # Safe move, continue playing
        return None

    def on_turn_limit(self) -> ta.Outcome:
        completion_pct = self._get_percentage_completion()
        return self.outcome({0: completion_pct}, reason=f"You reached the turn limit! Game over. You completed {round(completion_pct * 100)}% of the journey to the goal.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_percentage_completion(self) -> float:
        """
        Return the percentage of completion based on progress toward the goal.
        Uses BFS to calculate the shortest path distances and measures progress.
        """
        start_pos = self.game_state["start_pos"]  # Dynamic starting position
        goal_pos = self.game_state["goal_pos"]  # Goal position
        current_pos = self.game_state["player_pos"]  # Where the player is/fell
        grid = self.game_state["grid"]
        max_distance = self._bfs_distance_ignoring_holes(start_pos, goal_pos, grid)
        distance_remaining = self._bfs_distance_ignoring_holes(current_pos, goal_pos, grid)

        # If we couldn't find a path or distances are invalid, fall back to Manhattan distance
        if max_distance == -1 or distance_remaining == -1:
            max_distance = abs(goal_pos[0] - start_pos[0]) + abs(goal_pos[1] - start_pos[1])
            distance_remaining = abs(current_pos[0] - goal_pos[0]) + abs(current_pos[1] - goal_pos[1])

        if max_distance <= 0:
            return 0.0
        progress = (max_distance - distance_remaining) / max_distance
        return min(max(progress, 0.0), 0.95)

    def _bfs_distance_ignoring_holes(self, start: tuple, target: tuple, grid: list) -> int:
        """
        Calculate the shortest path distance between two points, ignoring holes.
        This gives us the theoretical shortest path if holes weren't there.
        Returns -1 if no path exists.
        """
        if start == target: return 0

        queue = deque([(start, 0)])  # (position, distance)
        visited = {start}
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # up, down, left, right

        while queue:
            (r, c), dist = queue.popleft()
            for dr, dc in directions:
                nr, nc = r + dr, c + dc
                if not (0 <= nr < self.size and 0 <= nc < self.size): continue  # Check bounds
                if (nr, nc) in visited: continue  # Skip if already visited
                visited.add((nr, nc))  # For distance calculation, we ignore holes to get theoretical shortest path
                if (nr, nc) == target: return dist + 1
                queue.append(((nr, nc), dist + 1))
        return -1  # No path found
