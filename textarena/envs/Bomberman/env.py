import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import textarena as ta

EMPTY = "."
INDESTRUCTIBLE_WALL = "#"
DESTRUCTIBLE_WALL = "+"
BOMB = "B"
BLAST = "*"
PLAYER_SYMBOLS = ("0", "1")
BLAST_MARKER_MOVES = 2  # a blast stays visible for two moves, so both players see it once

_MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
_ACTION_RE = re.compile(r"^(up|down|left|right|stay|bomb)$", re.IGNORECASE)


def _format_grid(canvas: List[List[str]]) -> str:
    """Grid with column numbers (x) on top and row numbers (y) on the left."""
    width = len(str(max(len(canvas), len(canvas[0])) - 1))
    header = " " * (width + 1) + " ".join(str(x).rjust(width) for x in range(len(canvas[0])))
    rows = [str(y).rjust(width) + " " + " ".join(cell.rjust(width) for cell in row) for y, row in enumerate(canvas)]
    return "\n".join([header] + rows)


class TwoPlayerBombermanEnv(ta.GameEnv):
    """Turn-based two-player Bomberman: players alternate single moves and bombs tick after every move."""
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    grid_size = ta.Param(10, "The side length of the square arena, including its outer wall.", min=5)
    max_turns = ta.Param(100, "The number of rounds (one move by each player) before the game ends in a draw.", min=1)
    bomb_timer = ta.Param(
        6, "The fuse length in moves, counting the move that drops the bomb; both players' moves count.", min=1,
    )
    bomb_radius = ta.Param(2, "The number of cells a blast reaches in each of the four directions.", min=1)
    wall_density = ta.Param(0.3, "The probability that a free cell starts as a destructible wall.", min=0, max=1)

    # ------------------------------------------------------------------ setup
    def setup(self) -> Dict[str, Any]:
        # max_turns counts rounds, while the engine counts individual moves.
        # Players strictly alternate, so a round is exactly two engine turns.
        self.state.max_turns = 2 * self.max_turns
        return {
            "grid": self._generate_grid(),
            "positions": list(self._spawns()),
            "alive": [True, True],
            "bombs": [],   # {"x", "y", "timer", "owner"}; timer = moves until it explodes, counting the next move
            "blasts": [],  # [x, y, remaining moves the blast marker stays visible]
        }

    def _spawns(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        return (1, 1), (self.grid_size - 2, self.grid_size - 2)

    def _is_indestructible(self, x: int, y: int) -> bool:
        """Outer wall plus pillars wherever both distances to the nearest outer wall are even.

        For odd sizes this is the classic lattice of pillars on every second
        cell. Measuring from the nearest wall keeps the arena point-symmetric
        for even sizes too, so neither spawn sits on or beside a different
        pillar arrangement.
        """
        n = self.grid_size
        if x in (0, n - 1) or y in (0, n - 1):
            return True
        return min(x, n - 1 - x) % 2 == 0 and min(y, n - 1 - y) % 2 == 0

    def _generate_grid(self) -> List[List[str]]:
        n = self.grid_size
        grid = [[INDESTRUCTIBLE_WALL if self._is_indestructible(x, y) else EMPTY for x in range(n)] for y in range(n)]
        # Destructible walls are mirrored through the centre so both players get the same arena.
        for y in range(1, n - 1):
            for x in range(1, n - 1):
                mirror_x, mirror_y = n - 1 - x, n - 1 - y
                if (y, x) > (mirror_y, mirror_x) or grid[y][x] != EMPTY:
                    continue
                if self.rng.random() < self.wall_density:
                    grid[y][x] = grid[mirror_y][mirror_x] = DESTRUCTIBLE_WALL
        # Clear a pocket around each spawn so both players can stand and move.
        for sx, sy in self._spawns():
            for y in range(sy - 1, sy + 2):
                for x in range(sx - 1, sx + 2):
                    if grid[y][x] == DESTRUCTIBLE_WALL:
                        grid[y][x] = EMPTY
        return grid

    # ----------------------------------------------------------------- prompts
    def prompt(self, player_id: int) -> str:
        n, fuse = self.grid_size, self.bomb_timer
        return (
            f"You are Player {player_id} in a turn-based two-player Bomberman game on a {n}x{n} grid.\n"
            f"You are shown as '{PLAYER_SYMBOLS[player_id]}' and your opponent as '{PLAYER_SYMBOLS[1 - player_id]}'. "
            "Players alternate moves and Player 0 moves first; a round is one move by each player.\n\n"
            "On your move, reply with exactly one command:\n"
            "  up / down / left / right - move one cell\n"
            "  stay - stay where you are\n"
            "  bomb - drop a bomb on your current cell\n"
            "For example: 'left' or 'bomb'.\n\n"
            "Rules:\n"
            "- You cannot move into a wall, a bomb or the other player. You can walk off a bomb you are standing on.\n"
            f"- Bombs have a {fuse}-move fuse: counting the move that drops a bomb as move 1, it explodes at the end of "
            f"move {fuse} (both players' moves count). After dropping a bomb you get {(fuse - 1) // 2} more move(s) to "
            f"get clear of it; your opponent gets {fuse // 2}.\n"
            f"- A blast covers the bomb's cell and up to {self.bomb_radius} cells up, down, left and right. "
            "Indestructible walls (#) stop it; a destructible wall (+) in its path is destroyed and also stops it. "
            "Blasts pass over other bombs without setting them off.\n"
            "- Anyone standing on a cell covered by a blast when it goes off is eliminated.\n"
            f"- The last player standing wins. If both players are caught in the same explosion, or both survive "
            f"{self.max_turns} rounds, the game is a draw.\n\n"
            "Board legend: '0' and '1' players, '#' indestructible wall, '+' destructible wall, 'B' bomb, "
            "'*' cell hit by an explosion during the last two moves (already resolved, safe to enter), '.' empty floor.\n"
            "Positions are (x, y): x is the column number and y the row number printed around the board, so 'up' "
            "decreases y. Each bomb is listed as 'explodes after N more move(s)': it goes off at the end of the N-th "
            "move from now, counting the move about to be made."
        )

    def render(self, player_id: int) -> str:
        if self.state.done:
            header = "Final board:"
        else:
            header = f"Round {self.state.turn // 2 + 1}/{self.max_turns}: Player {player_id} to move."
        return f"{header}\n{self.get_board_str()}"

    def get_board_str(self) -> str:
        gs = self.game_state
        canvas = [row[:] for row in gs["grid"]]
        for x, y, _ in gs["blasts"]:
            canvas[y][x] = BLAST
        for bomb in gs["bombs"]:
            canvas[bomb["y"]][bomb["x"]] = BOMB
        for pid, (x, y) in enumerate(gs["positions"]):
            if gs["alive"][pid]:
                canvas[y][x] = PLAYER_SYMBOLS[pid]
        players = "; ".join(
            f"Player {pid} at ({x}, {y})" + ("" if gs["alive"][pid] else " (eliminated)")
            for pid, (x, y) in enumerate(gs["positions"])
        )
        bombs = "; ".join(
            f"({b['x']}, {b['y']}) explodes after {b['timer']} more move{'' if b['timer'] == 1 else 's'}"
            for b in gs["bombs"]
        )
        return f"{_format_grid(canvas)}\nPlayers: {players}\nBombs: {bombs or 'none'}"

    # ------------------------------------------------------------------- moves
    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = _ACTION_RE.match(action)
        if match is None:
            return self.invalid("Reply with exactly one command: up, down, left, right, stay or bomb.")
        command = match.group(1).lower()
        gs = self.game_state
        x, y = gs["positions"][player_id]

        if command == "bomb":
            if self._bomb_at(x, y):
                return self.invalid(f"There is already a bomb on your cell ({x}, {y}).")
            gs["bombs"].append({"x": x, "y": y, "timer": self.bomb_timer, "owner": player_id})
            description = f"Player {player_id} dropped a bomb at ({x}, {y})."
        elif command == "stay":
            description = f"Player {player_id} stayed at ({x}, {y})."
        else:
            dx, dy = _MOVES[command]
            nx, ny = x + dx, y + dy
            blocker = self._blocker(nx, ny, player_id)
            if blocker is not None:
                return self.invalid(f"You cannot move {command} from ({x}, {y}): ({nx}, {ny}) is blocked by {blocker}.")
            gs["positions"][player_id] = (nx, ny)
            description = f"Player {player_id} moved {command} to ({nx}, {ny})."

        self.broadcast(description, ta.ObservationType.GAME_ACTION_DESCRIPTION)
        return self._tick()

    def on_turn_limit(self) -> ta.Outcome:
        return self.draw(reason=f"The round limit ({self.max_turns}) was reached with both players alive. The game is a draw.")

    def _bomb_at(self, x: int, y: int) -> bool:
        return any(bomb["x"] == x and bomb["y"] == y for bomb in self.game_state["bombs"])

    def _blocker(self, x: int, y: int, player_id: int) -> Optional[str]:
        gs = self.game_state
        if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
            return "the edge of the arena"
        cell = gs["grid"][y][x]
        if cell == INDESTRUCTIBLE_WALL:
            return "an indestructible wall"
        if cell == DESTRUCTIBLE_WALL:
            return "a destructible wall"
        if self._bomb_at(x, y):
            return "a bomb"
        other = 1 - player_id
        if gs["alive"][other] and gs["positions"][other] == (x, y):
            return f"Player {other}"
        return None

    # -------------------------------------------------------------- explosions
    def _tick(self) -> Optional[ta.Outcome]:
        """End-of-move update: age blast markers, count bombs down and resolve explosions."""
        gs = self.game_state
        gs["blasts"] = [[x, y, moves - 1] for x, y, moves in gs["blasts"] if moves > 1]
        exploding = [bomb for bomb in gs["bombs"] if bomb["timer"] <= 1]
        gs["bombs"] = [dict(bomb, timer=bomb["timer"] - 1) for bomb in gs["bombs"] if bomb["timer"] > 1]
        if not exploding:
            return None

        # Bombs going off together are resolved against the walls as they stood
        # before this tick, so the result does not depend on bomb order.
        hit: Set[Tuple[int, int]] = set()
        broken: Set[Tuple[int, int]] = set()
        for bomb in exploding:
            cells, walls = self._blast_area(bomb["x"], bomb["y"])
            hit |= cells
            broken |= walls
            self.broadcast(f"Player {bomb['owner']}'s bomb at ({bomb['x']}, {bomb['y']}) exploded!", ta.ObservationType.GAME_MESSAGE)
        for x, y in broken:
            gs["grid"][y][x] = EMPTY
        gs["blasts"] = [marker for marker in gs["blasts"] if (marker[0], marker[1]) not in hit]
        gs["blasts"] += [[x, y, BLAST_MARKER_MOVES] for x, y in sorted(hit)]

        caught = [pid for pid in range(2) if gs["alive"][pid] and gs["positions"][pid] in hit]
        for pid in caught:
            gs["alive"][pid] = False
            self.broadcast(f"Player {pid} was caught in the explosion and eliminated!", ta.ObservationType.GAME_MESSAGE)
        if len(caught) == 2:
            return self.draw(reason="Both players were caught in the same explosion. The game is a draw.")
        if caught:
            loser = caught[0]
            return self.winner(1 - loser, reason=f"Player {1 - loser} wins - Player {loser} was caught in an explosion.")
        return None

    def _blast_area(self, bomb_x: int, bomb_y: int) -> Tuple[Set[Tuple[int, int]], Set[Tuple[int, int]]]:
        """Cells covered by a bomb's blast, and the destructible walls it breaks."""
        grid = self.game_state["grid"]
        cells = {(bomb_x, bomb_y)}
        walls = set()
        for dx, dy in _MOVES.values():
            for distance in range(1, self.bomb_radius + 1):
                x, y = bomb_x + dx * distance, bomb_y + dy * distance
                if not (0 <= x < self.grid_size and 0 <= y < self.grid_size) or grid[y][x] == INDESTRUCTIBLE_WALL:
                    break
                cells.add((x, y))
                if grid[y][x] == DESTRUCTIBLE_WALL:
                    walls.add((x, y))
                    break
        return cells, walls
