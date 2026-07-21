import re, random
from typing import List, Optional, Tuple, Dict, Any

import textarena as ta


class Game2048Env(ta.Env):
    DEFAULT_BOARD_SIZE = 4
    CELL_W = 6  
    ACTIONS = {"[UP]": 0, "[DOWN]": 1, "[LEFT]": 2, "[RIGHT]": 3, "[W]": 0, "[S]": 1, "[A]": 2, "[D]": 3}
    _BRACKET_GROUP_RE = re.compile(r"\[[^\[\]]*\]")
    _VALID_DIRECTIONS = {"UP", "DOWN", "LEFT", "RIGHT", "W", "A", "S", "D"}
                                                                                            
    def __init__(self, target_tile: int = 2048, board_size: int = None):
        super().__init__()
        self.target_tile = target_tile
        self.board_size = board_size if board_size is not None else self.DEFAULT_BOARD_SIZE
        
        # Validate board size
        if self.board_size < 2:
            raise ValueError("Board size must be at least 2")
        if self.board_size > 10:
            raise ValueError("Board size cannot exceed 10 for practical reasons")

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed)
        board = [[0] * self.board_size for _ in range(self.board_size)]
        self._spawn_tile(board)
        self._spawn_tile(board)
        self.state.reset(game_state={"board": board, "score": 0}, player_prompt_function=self._prompt)
        self._observe_state()

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", board_size=self.board_size, target_tile=self.target_tile)

    def _observe_state(self):
        board = self.state.game_state["board"]
        make_cell = lambda v: f"{v:^{self.CELL_W}}" if v else "  .   "
        rows = [" ".join(make_cell(v) for v in row) for row in board]
        horiz = "+" + "-" * (len(rows[0])) + "+"
        framed = [horiz] + [f"|{r}|" for r in rows] + [horiz]
        self.state.add_observation(message=self.m("board", "current_board", score=self.state.game_state['score'], board="\n".join(framed)), observation_type=ta.ObservationType.GAME_BOARD,)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        self.state.add_observation(from_id=self.state.current_player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        dir_idx = self._parse_action(action)
        if dir_idx is None:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "invalid_action"),)
            return self.state.step()

        moved, gained = self._apply_move(dir_idx)
        if not moved: # Move had no effect – treat as invalid but continue the episode.
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid_move", "no_change"))
            return self.state.step()

        self.state.game_state["score"] += gained
        self._spawn_tile(self.state.game_state["board"])

        status = self._check_status()
        if status == "win":     self.state.set_outcome(reward=1.0, reason=self.m("outcome", "win", target_tile=self.target_tile, score=self.state.game_state['score']))
        elif status == "lose":  self.state.set_outcome(reward=self._get_percentage_completion(), reason=self.m("outcome", "lose", max_tile=self._max_tile(), score=self.state.game_state['score']))
        else:                   self._observe_state()

        return self.state.step()
    
    @staticmethod
    def _min_score_to_reach_tile(tile: int) -> int:
        assert (tile & (tile - 1)) == 0, "tile must be a power of 2"
        total = 0
        while tile > 2: total += tile; tile //= 2
        return total

    def _get_percentage_completion(self) -> float:
        if self._max_tile() >= self.target_tile: return 1.0
        min_score_needed = self._min_score_to_reach_tile(self.target_tile) * 1.5
        score_part = self.state.game_state['score'] / min_score_needed
        max_part = self._max_tile() / self.target_tile
        reward = 0.5 * score_part + 0.5 * max_part
        return float(min(1.0, reward))
    
    def _parse_action(self, action: str) -> Optional[int]:
        groups = list(self._BRACKET_GROUP_RE.finditer(action))
        if not groups: return None
        for g in reversed(groups):
            inner = g.group(0)[1:-1]  
            tokens = re.findall(r"\b\w+\b", inner)
            for token in reversed(tokens): 
                upper_token = token.upper()
                if upper_token in self._VALID_DIRECTIONS:
                    return self.ACTIONS.get(f"[{upper_token}]")
        return None

    def _apply_move(self, dir_idx: int) -> Tuple[bool, int]:
        board = self.state.game_state["board"]
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
        r, c = random.choice(empties)
        board[r][c] = 4 if random.random() < 0.1 else 2

    def _max_tile(self) -> int:
        return max(max(row) for row in self.state.game_state["board"])

    def _check_status(self) -> str:
        # Win condition
        if self._max_tile() >= self.target_tile:                        return "win"
        # Still space? Continue
        if any(0 in row for row in self.state.game_state["board"]):     return "ongoing"
        # Any possible merge?
        board = self.state.game_state["board"]
        for r in range(self.board_size):
            for c in range(self.board_size):
                v = board[r][c]
                for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.board_size and 0 <= nc < self.board_size and board[nr][nc] == v:
                        return "ongoing"
        return "lose"