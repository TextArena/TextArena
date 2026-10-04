import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class Game2048Env(ta.GameEnv):
    min_players = 1
    max_players = 1
    DEFAULT_BOARD_SIZE = 4
    MAX_TARGET_TILE = 65536
    CELL_W = 6
    ACTIONS = {"UP": 0, "DOWN": 1, "LEFT": 2, "RIGHT": 3}
    _ACTION_RE = re.compile(r"(?P<wrapped>\[)?\s*(?P<direction>[A-Za-z]+)\s*(?(wrapped)\])")

    def __init__(self, target_tile: int = 2048, board_size: int = None):
        if (
            not isinstance(target_tile, int)
            or isinstance(target_tile, bool)
            or target_tile < 4
            or target_tile & (target_tile - 1)
        ):
            raise ValueError("target_tile must be a power of two greater than or equal to 4")
        if target_tile > self.MAX_TARGET_TILE:
            raise ValueError(f"target_tile cannot exceed {self.MAX_TARGET_TILE}")
        self.target_tile = target_tile
        self.board_size = board_size if board_size is not None else self.DEFAULT_BOARD_SIZE

        # Validate board size
        if not isinstance(self.board_size, int) or isinstance(self.board_size, bool):
            raise ValueError("Board size must be an integer")
        if self.board_size < 2:
            raise ValueError("Board size must be at least 2")
        if self.board_size > 10:
            raise ValueError("Board size cannot exceed 10 for practical reasons")

    def setup(self) -> Dict[str, Any]:
        board = [[0] * self.board_size for _ in range(self.board_size)]
        self._spawn_tile(board)
        self._spawn_tile(board)
        return {"board": board, "score": 0}

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing 2048 on a {self.board_size}x{self.board_size} board. Your goal is to reach a {self.target_tile} tile by sliding identical numbers together!\n"
            "Valid moves: 'up', 'down', 'left', 'right'. Tiles combine when they collide, doubling their value.\n"
        )

    def render(self, player_id: int) -> str:
        board = self.game_state["board"]
        make_cell = lambda v: f"{v:^{self.CELL_W}}" if v else "  .   "
        rows = [" ".join(make_cell(v) for v in row) for row in board]
        horiz = "+" + "-" * (len(rows[0])) + "+"
        framed = [horiz] + [f"|{r}|" for r in rows] + [horiz]
        return f"Score: {self.game_state['score']}\n" + "\n".join(framed)

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        dir_idx = self._parse_action(move)
        if dir_idx is None:
            return self.invalid("Invalid action. Use 'up'/'down'/'left'/'right'.")

        moved, gained = self._apply_move(dir_idx)
        if not moved:  # Move had no effect – treat as invalid but continue the episode.
            return self.invalid("Board did not change - choose a different direction.")

        self.game_state["score"] += gained

        if self._check_status() == "win":
            return self.outcome({0: 1.0}, reason=f"Congratulations, you reached {self.target_tile}! Final score {self.game_state['score']}.")

        self._spawn_tile(self.game_state["board"])
        if self._check_status() == "lose":
            return self.outcome({0: self._get_percentage_completion()}, reason=f"No moves left. Max tile {self._max_tile()} - final score {self.game_state['score']}.")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    @staticmethod
    def _min_score_to_reach_tile(tile: int) -> int:
        assert (tile & (tile - 1)) == 0, "tile must be a power of 2"
        total = 0
        while tile > 2: total += tile; tile //= 2
        return total

    def _get_percentage_completion(self) -> float:
        if self._max_tile() >= self.target_tile: return 1.0
        min_score_needed = self._min_score_to_reach_tile(self.target_tile) * 1.5
        score_part = self.game_state['score'] / min_score_needed
        max_part = self._max_tile() / self.target_tile
        reward = 0.5 * score_part + 0.5 * max_part
        return float(min(1.0, reward))

    def _parse_action(self, action: str) -> Optional[int]:
        m = self._ACTION_RE.fullmatch(action.strip())
        if not m: return None
        return self.ACTIONS.get(m.group("direction").upper())

    def _apply_move(self, dir_idx: int) -> Tuple[bool, int]:
        board = self.game_state["board"]
        moved = False
        gained = 0

        # Helper generating *views* of rows/columns, allowing us to reuse
        # the left‑shift logic for every direction.
        def iterable_rows():
            if dir_idx == 0:  # Up: treat each column top→bottom
                for c in range(self.board_size):    yield [board[r][c] for r in range(self.board_size)], c, True
            elif dir_idx == 1:  # Down: column bottom→top (reversed)
                for c in range(self.board_size):    yield [board[r][c] for r in reversed(range(self.board_size))], c, True
            elif dir_idx == 2:  # Left: natural rows
                for r in range(self.board_size):    yield board[r][:], r, False
            else:  # Right: rows reversed
                for r in range(self.board_size):    yield list(reversed(board[r])), r, False

        for line, idx, is_col in iterable_rows():
            original = line[:]
            new_line, delta_score = self._compress_and_merge(line)
            gained += delta_score
            if new_line != original:
                moved = True

            # Write back to *board* with appropriate orientation
            for i, v in enumerate(new_line):
                if is_col:
                    if dir_idx == 0:    board[i][idx] = v # Up: top→bottom
                    else:               board[self.board_size - 1 - i][idx] = v # Down: bottom→top
                else:
                    if dir_idx == 2:    board[idx][i] = v # Left
                    else:               board[idx][self.board_size - 1 - i] = v # Right

        return moved, gained

    def _compress_and_merge(self, line: List[int]) -> Tuple[List[int], int]:
        """Slide non- zero tiles left and merge identical neighbours."""
        if len(line) != self.board_size:
            raise ValueError(f"line must contain exactly {self.board_size} cells")
        tiles = [v for v in line if v != 0]
        score_gain = 0
        i = 0
        while i < len(tiles) - 1:
            if tiles[i] == tiles[i + 1]:
                tiles[i] *= 2
                score_gain += tiles[i]
                del tiles[i + 1]
                i += 1
            else:
                i += 1
        tiles.extend([0] * (self.board_size - len(tiles)))
        return tiles, score_gain

    def _spawn_tile(self, board: List[List[int]]):
        """Spawn a new tile (2 with 90%, 4 with 10%) in a random empty cell."""
        empties = [(r, c) for r in range(self.board_size) for c in range(self.board_size) if board[r][c] == 0]
        if not empties: return
        r, c = self.rng.choice(empties)
        board[r][c] = 4 if self.target_tile > 4 and self.rng.random() < 0.1 else 2

    def _max_tile(self) -> int:
        return max(max(row) for row in self.game_state["board"])

    def _check_status(self) -> str:
        # Win condition
        if self._max_tile() >= self.target_tile:                    return "win"
        # Still space? Continue
        if any(0 in row for row in self.game_state["board"]):       return "ongoing"
        # Any possible merge?
        board = self.game_state["board"]
        for r in range(self.board_size):
            for c in range(self.board_size):
                v = board[r][c]
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board_size and 0 <= nc < self.board_size and board[nr][nc] == v:
                        return "ongoing"
        return "lose"
