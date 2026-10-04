import re
from typing import Any, Dict, List, Union

import textarena as ta
from textarena.envs.LightsOut.renderer import create_board_str


class LightsOutEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    MAX_SIZE = 20
    MAX_COORDINATE_DIGITS = 6

    # Action format: 'row col' where row and col are 0-indexed
    action_space = re.compile(r"(?P<row>\d+)(?:\s*,\s*|\s+)(?P<col>\d+)")

    size = ta.Param(5, "The width and height of the grid.", min=1, max=MAX_SIZE)
    max_turns = ta.Param(
        50, "The number of valid presses allowed. It also caps the number of scrambling presses at reset, so the "
            "puzzle stays solvable within the limit.", min=1,
    )

    def setup(self) -> Dict[str, Any]:
        grid = [[False for _ in range(self.size)] for _ in range(self.size)]
        num_scramble_moves = self.rng.randint(1, min(15, self.max_turns))
        for _ in range(num_scramble_moves):
            row = self.rng.randint(0, self.size - 1)
            col = self.rng.randint(0, self.size - 1)
            self._toggle_lights(grid, row, col)
        if self._is_solved(grid):
            # Avoid an already-terminal reset state. One additional press keeps
            # the generated puzzle solvable in a single move.
            self._toggle_lights(grid, self.rng.randrange(self.size), self.rng.randrange(self.size))
        initial_on = sum(light for row in grid for light in row)
        return dict(grid=grid, moves_made=0, solved=False, initial_on=initial_on)

    def prompt(self, player_id: int) -> str:
        return (
            f"Welcome to Lights Out! You have a {self.size}x{self.size} grid of lights.\n"
            "Your goal is to turn ALL lights OFF (represented by '.')\n"
            "When you press a light, it toggles itself AND its adjacent neighbors (up/down/left/right).\n"
            f"Reply with 'row col' to press a light (0-indexed, so valid range is 0-{self.size-1}), "
            f"e.g. '{min(2, self.size - 1)} {min(3, self.size - 1)}'.\n"
            f"You have up to {self.max_turns} moves to solve the puzzle.\n"
            "Legend: 'O' = light ON, '.' = light OFF"
        )

    def get_board_str(self) -> str:
        return create_board_str(game_state=self.game_state)

    def render(self, player_id: int) -> str:
        moves_made = self.game_state["moves_made"]
        moves_left = self.max_turns - moves_made
        completion = self._get_percentage_completion()
        return (
            f"Current grid state (Move {moves_made}, {moves_left} moves remaining, "
            f"{completion:.1%} complete):\n{self._grid_to_string(self.game_state['grid'])}"
        )

    def _toggle_lights(self, grid: List[List[bool]], row: int, col: int):
        """Toggle the light at (row, col) and its orthogonal neighbors"""
        directions = [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]  # self, up, down, left, right
        for dr, dc in directions:
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < self.size and 0 <= new_col < self.size:
                grid[new_row][new_col] = not grid[new_row][new_col]

    def _grid_to_string(self, grid: List[List[bool]]) -> str:
        """Convert grid to a readable string representation"""
        result = []
        label_width = len(str(self.size - 1))
        result.append(
            " " * (label_width + 2)
            + " ".join(f"{i:>{label_width}}" for i in range(self.size))
        )
        for i, row in enumerate(grid):
            row_str = f"{i:>{label_width}}: " + " ".join(
                f"{'O' if light else '.':>{label_width}}" for light in row
            )
            result.append(row_str)
        return "\n".join(result)

    def _is_solved(self, grid: List[List[bool]]) -> bool:
        """Check if all lights are off (solved state)"""
        return all(not light for row in grid for light in row)

    def _get_percentage_completion(self) -> float:
        """Calculate completion percentage based on lights turned off"""
        grid = self.game_state['grid']
        on_now = sum(light for row in grid for light in row)
        raw_progress = (self.game_state['initial_on'] - on_now) / self.game_state['initial_on']
        return float(max(0.0, min(1.0, raw_progress)))

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        m = self.action_space.fullmatch(move.strip())
        if m is None:
            return self.invalid(f"Action must be in format 'row col' where row and col are integers from 0 to {self.size-1}.")

        row_text, col_text = m.group("row"), m.group("col")
        if len(row_text) > self.MAX_COORDINATE_DIGITS or len(col_text) > self.MAX_COORDINATE_DIGITS:
            return self.invalid(f"Coordinates must be between 0 and {self.size-1}.")
        row, col = int(row_text), int(col_text)
        if not (0 <= row < self.size and 0 <= col < self.size):
            return self.invalid(f"Coordinates must be between 0 and {self.size-1}. You entered '{row} {col}'.")

        self._toggle_lights(self.game_state['grid'], row, col)
        self.game_state['moves_made'] += 1

        if self._is_solved(self.game_state['grid']):
            self.game_state["solved"] = True
            return self.outcome({0: 1.0}, reason=f"Congratulations! You solved the puzzle in {self.game_state['moves_made']} moves!")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        completion = self._get_percentage_completion()
        message = f"Game over! You used all {self.max_turns} moves without solving the puzzle. Final completion: {completion:.1%}"
        final_grid = self._grid_to_string(self.game_state['grid'])
        return self.outcome({0: completion}, reason=f"{message}\nFinal state:\n{final_grid}")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")
