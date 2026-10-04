import math, re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Surround.renderer import create_board_str

_DIR_DELTAS = {"up": (0, 1), "w": (0, 1), "down": (0, -1), "s": (0, -1), "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0)}
_DIR_RE = re.compile(r"^\s*\[?\s*(up|down|left|right|w|a|s|d)\s*\]?\s*$", re.I)

def _dir_token(move: str) -> Optional[str]:
    """Return the direction token if *move* is a single bare direction (brackets tolerated)."""
    m = _DIR_RE.match(move)
    return m.group(1).lower() if m else None

def _step_from_str(move: str) -> Tuple[int, int]:
    """Return (dx, dy) for the direction token in *move*."""
    token = _dir_token(move)
    return _DIR_DELTAS[token] if token else (0, 0)

class _Player:
    def __init__(self, pos: Tuple[int, int]):
        self.position: Tuple[int, int] = pos
        self.alive: bool = True
        self.death_reason: Optional[str] = None

class SurroundEnv(ta.GameEnv):
    MAX_PLAYERS = 15
    min_players = 2
    max_players = 15
    broadcast_actions = False  # moves are sealed until the round resolves
    error_allowance = 0  # every malformed action is immediately fatal

    def __init__(self, width: int = 10, height: int = 10, max_turns: int = 100):
        if (
            not isinstance(width, int) or isinstance(width, bool)
            or not isinstance(height, int) or isinstance(height, bool)
        ):
            raise ValueError("Board dimensions must be integers")
        if width < 3 or height < 3:
            raise ValueError("Board dimensions must each be at least 3")
        if (width - 2) * (height - 2) < self.min_players:
            raise ValueError("Board interior must have room for at least two players")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self.width, self.height, self.max_turns = width, height, max_turns

    @property
    def pending_actions(self) -> Dict[int, Optional[str]]:
        return self.game_state["pending_actions"]

    def get_board_str(self) -> str:
        return create_board_str(width=self.width, height=self.height, game_state=self.game_state)

    def _ascii_board(self, board, players) -> str:
        grid = [["." for _ in range(self.width)] for _ in range(self.height)]
        # trails
        for y in range(self.height):
            for x in range(self.width):
                if board[y][x] is not None:
                    grid[y][x] = "#"
        # heads
        for pid, pl in players.items():
            if pl.alive:
                x, y = pl.position
                grid[y][x] = format(pid, "X")
        horiz = "+" + "-" * (self.width * 2 + 1) + "+"
        rows = [horiz]
        for row in reversed(grid): # y grows upward
            rows.append("| " + " ".join(row) + " |")
        rows.append(horiz)
        return "\n".join(rows)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        # Simultaneous submissions make a game turn a completed round, not one
        # player's sealed action. The environment enforces the round limit.
        self.state.max_turns = None
        # spawn players (farthest-point sampling like Snake for fairness)
        spawns: List[Tuple[int, int]] = self._generate_spawn_positions(num_players)
        players: Dict[int, _Player] = {pid: _Player(pos) for pid, pos in enumerate(spawns)}
        game_state = {
            "board": [[None for _ in range(self.width)] for _ in range(self.height)],
            "players": players, "death_turn": {}, "board_state": "", "round": 0,
            "pending_actions": {pid: None for pid in range(num_players)},
        }
        game_state["board_state"] = self._ascii_board(game_state["board"], players)
        return game_state

    def _generate_spawn_positions(self, k: int) -> List[Tuple[int, int]]:
        candidates = [(x, y) for x in range(1, self.width - 1) for y in range(1, self.height - 1)]
        if len(candidates) < k: raise ValueError("Board too small for spawn sampling")
        self.rng.shuffle(candidates)
        spawns = [candidates.pop()]
        while len(spawns) < k:
            best = max(candidates, key=lambda p: min(math.dist(p, s) for s in spawns))
            spawns.append(best)
            candidates.remove(best)
        return spawns

    def prompt(self, player_id: int) -> str:
        return (
            f"{self.state.num_players}-Player Surround on a {self.width}x{self.height} grid.\n"
            f"You are player {player_id}. Valid moves: 'up' 'down' 'left' 'right' or 'w'/'s'/'a'/'d'.\n"
            f"Objective: outlive everyone else. Trails are deadly; wall hits kill; head-on crashes kill both."
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n{self.game_state['board_state']}"

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        players: Dict[int, _Player] = gs["players"]
        token = _dir_token(action)

        # Invalid move → instant death, like in SnakeEnv
        if token is None:
            outcome = self._eliminate_for_invalid_action(player_id)
            if outcome is not None:
                return outcome
        else:
            gs["pending_actions"][player_id] = action

        # resolve turn when all living acted
        outcome = None
        living = [p for p, pl in players.items() if pl.alive]
        if living and all(gs["pending_actions"][p] for p in living):
            outcome = self._apply_simultaneous_moves()
            for p in living:
                gs["pending_actions"][p] = None
        if outcome is not None:
            return outcome

        alive = [pid for pid, pl in players.items() if pl.alive]
        if len(alive) <= 1:
            return self._finalise_rewards("Player outlived all others." if alive else "All players dead.")
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """Keep engine preflight rejections consistent with Surround deaths.

        Oversized and non-string actions are rejected by the shared engine
        before ``apply`` runs. They still count as fatal malformed actions in
        Surround and therefore must update both the engine elimination list
        and the environment's per-player alive state.
        """
        return self._eliminate_for_invalid_action(player_id)

    def _eliminate_for_invalid_action(self, player_id: int) -> Optional[ta.Outcome]:
        gs = self.game_state
        player = gs["players"][player_id]
        if player.alive:
            player.alive = False
            player.death_reason = "invalid move"
            gs["death_turn"][player_id] = gs["round"]
            x, y = player.position
            gs["board"][y][x] = player_id
            self.eliminate(player_id)
            self.broadcast(
                f"Player {player_id} died due to invalid move.",
                ta.ObservationType.GAME_ADMIN,
            )
            gs["board_state"] = self._ascii_board(gs["board"], gs["players"])
        gs["pending_actions"][player_id] = None

        alive = [pid for pid, candidate in gs["players"].items() if candidate.alive]
        if len(alive) <= 1:
            reason = "Player outlived all others." if alive else "All players dead."
            return self._finalise_rewards(reason)
        return None

    def _apply_simultaneous_moves(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        players: Dict[int, _Player] = gs["players"]
        board = gs["board"]

        living = [pid for pid, pl in players.items() if pl.alive]
        old_pos = {pid: players[pid].position for pid in living}
        desired: Dict[int, Tuple[int, int]] = {}

        # 1. desired head positions
        for pid in living:
            dx, dy = _step_from_str(gs["pending_actions"][pid])
            x, y = old_pos[pid]
            desired[pid] = (x + dx, y + dy)

        crashes: set[int] = set()

        # 2. out-of-bounds
        for pid, (x, y) in desired.items():
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                crashes.add(pid)

        # 3. trail collisions
        for pid, (x, y) in desired.items():
            if pid not in crashes and board[y][x] is not None:
                crashes.add(pid)

        # 4. move into current head of someone else (will leave trail)
        current_positions = set(old_pos.values())
        for pid, pos in desired.items():
            if pid not in crashes and pos in current_positions:
                crashes.add(pid)

        # 5. head-on collisions (multiple snakes to same cell)
        bins = defaultdict(list)
        for pid, pos in desired.items():
            if pid not in crashes: bins[pos].append(pid)
        for pos, ids in bins.items():
            if len(ids) > 1: crashes.update(ids)

        # Every old head square becomes trail, including heads that crash.
        for pid in living:
            ox, oy = old_pos[pid]
            board[oy][ox] = pid

        # ── apply results ──
        for pid in living:
            if pid in crashes:
                players[pid].alive = False
                players[pid].death_reason = "crash"
                gs["death_turn"][pid] = gs["round"]
                self.eliminate(pid)
            else:
                nx, ny = desired[pid]
                players[pid].position = (nx, ny)

        gs["round"] += 1
        gs["board_state"] = self._ascii_board(board, players)

        # ── end-of-game checks ──
        alive = [pid for pid, pl in players.items() if pl.alive]
        if len(alive) <= 1:
            if alive: return self._finalise_rewards(f"Player {alive[0]} survived; all others crashed.")
            return self._finalise_rewards("All players crashed simultaneously.")
        if gs["round"] >= self.max_turns:
            return self._finalise_rewards("Turn limit reached - longest survivor wins.")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self._finalise_rewards("Turn limit reached - longest survivor wins.")

    def _finalise_rewards(self, reason: str) -> ta.Outcome:
        gs = self.game_state
        survival_turn = {pid: (gs["round"] + 1) if pl.alive else gs["death_turn"].get(pid, -1) for pid, pl in gs["players"].items()}
        # build ranking groups (same survival = tie)
        sorted_pids = sorted(range(self.state.num_players), key=lambda pid: (survival_turn[pid], gs["players"][pid].alive, -pid))
        groups: List[List[int]] = []
        for pid in sorted_pids:
            if not groups or survival_turn[groups[-1][0]] != survival_turn[pid]: groups.append([pid])
            else: groups[-1].append(pid)
        # linear rewards from –1 (worst) to +1 (best) across groups
        reward: Dict[int, float] = {}
        G = len(groups)
        if G == 1: reward = {pid: 0.0 for pid in groups[0]}
        else:
            for g_idx, grp in enumerate(reversed(groups)): # best group first
                r = 1.0 - 2.0 * g_idx / (G - 1)
                for pid in grp: reward[pid] = r
        return self.outcome(reward, reason=f"{reason} Final ranking groups (best→worst): {list(reversed(groups))}")
