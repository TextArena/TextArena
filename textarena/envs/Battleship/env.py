import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Battleship.renderer import create_board_str

class BattleshipEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False
    action_pattern = r"^([A-Za-z])\s*(\d+)$"

    def __init__(self, grid_size: Optional[int] = 10):
        """
        Args:
            grid_size (int): Grid size
        """
        self.ships = {"Aircraft Carrier": 5, "Battleship": 4, "Submarine": 3, "Destroyer": 3, "Patrol Boat": 2}
        if (
            not isinstance(grid_size, int)
            or isinstance(grid_size, bool)
            or grid_size < max(self.ships.values())
            or grid_size > 26
        ):
            raise ValueError("grid_size must be an integer from 5 through 26")
        self.grid_size = grid_size

    @property
    def action_format(self) -> str:
        last_row = chr(ord('A') + self.grid_size - 1)
        return (
            f"a row letter from A to {last_row} followed by a column number from 0 to {self.grid_size - 1}, "
            "for example 'C4'"
        )

    def setup(self) -> Dict[str, Any]:
        board, tracking_board, ship_placements = self._generate_board()
        return {"board": board, "tracking_board": tracking_board, "ship_placements": ship_placements}

    def prompt(self, player_id: int) -> str:
        last_row = chr(ord('A') + self.grid_size - 1)
        fleet = ", ".join(f"{name} ({name[0]}, {length} cells)" for name, length in self.ships.items())
        return (
            f"You are Player {player_id}. You are playing the Battleship game.\nYour goal is to sink all of your opponent's ships before they sink yours.\n"
            f"Each player has a hidden {self.grid_size}x{self.grid_size} grid with five ships placed horizontally or vertically without overlapping: {fleet}.\n"
            f"Players take turns firing one shot each. On your turn, reply with the coordinate to fire at: a row letter (A-{last_row}) followed by a column number (0-{self.grid_size - 1}), e.g. 'C4'.\n"
            "After every shot, both players learn whether it hit or missed, and when a ship is sunk, which ship it was. You cannot fire at the same coordinate twice.\n"
            "The game ends when all of one player's ships have been sunk.\n"
            "Before each of your turns you will see your own grid (your ships by initial, '~' for water, 'X' where your opponent hit and 'O' where they missed) "
            "and your shots at the opponent ('X' for a hit, 'O' for a miss, '~' for coordinates not yet fired at). Your opponent's ships stay hidden."
        )

    def render(self, player_id: int) -> str:
        return self._render_player_view(player_id)

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        row = ord(move.group(1).upper()) - ord('A')
        try:
            col = int(move.group(2))
        except ValueError:
            return self.invalid("The column number is too large.")
        coord = f"{move.group(1).upper()}{col}"

        opponent_id = 1 - player_id
        opponent_board = self.game_state['board'][opponent_id]
        tracking_board = self.game_state['tracking_board'][player_id]

        if row < 0 or row >= self.grid_size or col < 0 or col >= self.grid_size:
            return self.invalid(f"The coordinate {coord} is outside the board.")
        if tracking_board[row][col] != '~':
            return self.invalid(f"The coordinate {coord} has already been fired upon.")

        if opponent_board[row][col] != '~':
            tracking_board[row][col] = 'X'
            ship_initial = opponent_board[row][col]
            opponent_board[row][col] = 'X'
            if not any(ship_initial in board_row for board_row in opponent_board):
                ship_name = next(name for name in self.ships if name[0] == ship_initial)
                self.message(player_id, f"Sunk! You hit a ship at {coord} and sank the opponent's {ship_name}!", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self.message(opponent_id, f"Opponent hit your ship at {coord} and sank your {ship_name}!", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            else:
                self.message(player_id, f"Hit! You hit a ship at {coord}!", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self.message(opponent_id, f"Opponent hit your ship at {coord}!", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        else:
            tracking_board[row][col] = 'O'; opponent_board[row][col] = 'O'
            self.message(player_id, f"Miss! Your shot at {coord} hit only water.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.message(opponent_id, f"Opponent fired at {coord} and missed.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        if self._check_win(player_id):
            return self.winner(player_id, reason=f"Player {player_id} has sunk all of their opponent's ships!")
        return None

    def get_board_str(self, player_id: Optional[int] = None, reveal_all: bool = False):
        if not reveal_all:
            player_id = self.current_player_id if player_id is None else player_id
            if player_id not in (0, 1):
                raise ValueError("player_id must be 0 or 1")
            return self._render_player_view(player_id)
        return create_board_str(game_state=self.game_state)

    def _generate_board(self):
        """ Generate a new grid, tracking grid, and place ships on the grid for both players, where each entity is a dictionary with the player_ids as the keys """
        board = {0: [['~'] * self.grid_size for _ in range(self.grid_size)], 1: [['~'] * self.grid_size for _ in range(self.grid_size)]}
        tracking_board = {0: [['~'] * self.grid_size for _ in range(self.grid_size)], 1: [['~'] * self.grid_size for _ in range(self.grid_size)]}
        ship_placements = {0: {}, 1: {}}
        for player_id in range(2):
            ship_placements[player_id] = self._place_fleet(board[player_id])
        return board, tracking_board, ship_placements

    def _candidate_placements(self, grid: List[List[str]], length: int) -> List[List[Tuple[int, int]]]:
        candidates: List[List[Tuple[int, int]]] = []
        for row in range(self.grid_size):
            for col in range(self.grid_size):
                for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                    cells = [(row + dr * i, col + dc * i) for i in range(length)]
                    if all(
                        0 <= r < self.grid_size
                        and 0 <= c < self.grid_size
                        and grid[r][c] == '~'
                        for r, c in cells
                    ):
                        candidates.append(cells)
        return candidates

    def _place_fleet(self, grid: List[List[str]]) -> Dict[str, List[Tuple[int, int]]]:
        ships = list(self.ships.items())
        placements: Dict[str, List[Tuple[int, int]]] = {}

        def place(index: int) -> bool:
            if index == len(ships):
                return True
            ship_name, length = ships[index]
            candidates = self._candidate_placements(grid, length)
            self.rng.shuffle(candidates)
            initial = ship_name[0]
            for cells in candidates:
                for row, col in cells:
                    grid[row][col] = initial
                placements[ship_name] = [cells[0], cells[-1]]
                if place(index + 1):
                    return True
                for row, col in cells:
                    grid[row][col] = '~'
                placements.pop(ship_name, None)
            return False

        if not place(0):
            raise ValueError(f"Fleet cannot be placed on a {self.grid_size}x{self.grid_size} board")
        return placements

    def _render_player_view(self, player_id: int) -> str:
        """ Render the player's private view of the game. """
        own_grid = self.game_state['board'][player_id]
        tracking_grid = self.game_state['tracking_board'][player_id]
        player_label = f"Player {player_id}"

        view = []
        view.append(f"{player_label}'s View".center(self.grid_size * 6 + 11).rstrip())
        view.append("   " + "Your Ships".center(self.grid_size * 3) + "        " + "Your Hits on Opponent".center(self.grid_size * 3))
        view.append("   " + " ".join([f"{i:2}" for i in range(self.grid_size)]) + "      " + "   " + " ".join([f"{i:2}" for i in range(self.grid_size)]))

        for i in range(self.grid_size):
            row_label = chr(i + ord('A'))
            row_own_grid = " ".join(f"{cell:2}" for cell in own_grid[i])
            row_tracking_grid = " ".join(f"{cell:2}" for cell in tracking_grid[i])
            view.append(f"{row_label}   {row_own_grid}     {row_label}   {row_tracking_grid}")

        return "\n".join(view)

    def _check_win(self, player_id: int) -> bool:
        """ Check if the game is over """
        opponent_board = self.game_state['board'][1 - player_id]
        abbreviations = {name[0] for name in self.ships.keys()}
        return not any(any(cell in abbreviations for cell in row) for row in opponent_board)
