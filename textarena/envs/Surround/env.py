import math, re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Surround.renderer import create_board_str

_DIR_DELTAS = {"up": (0, 1), "w": (0, 1), "down": (0, -1), "s": (0, -1), "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0)}
_DIR_NAMES = {"w": "up", "s": "down", "a": "left", "d": "right"}
_DIR_RE = re.compile(r"^(up|down|left|right|w|a|s|d)$", re.I)
_CRASH_DESCRIPTIONS = {"wall": "hit the wall", "trail": "hit a trail", "head-on": "collided head-on"}

def _dir_token(move: str) -> Optional[str]:
    """Return the direction name if *move* is a single bare direction."""
    m = _DIR_RE.match(move)
    if not m:
        return None
    token = m.group(1).lower()
    return _DIR_NAMES.get(token, token)

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
    error_allowance = 0  # every invalid action is immediately fatal

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
        if len(candidates) < k:
            raise ValueError(
                f"A {self.width}x{self.height} Surround board fits at most {len(candidates)} players "
                f"(spawns use interior cells); got {k}."
            )
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
            f"You are player {player_id}; your position is shown as '{format(player_id, 'X')}'.\n"
            "Every round, all living players move one cell at the same time. Reply with one direction: "
            "'up', 'down', 'left' or 'right' (or 'w', 's', 'a', 'd'); 'up' moves toward the top of the printed board. "
            "Moves stay hidden until the round resolves.\n"
            "Board legend: players show their numbers (players 10-14 appear as A-E), '#' is a trail, '.' is empty.\n"
            "Rules:\n"
            "- Every cell you leave becomes a permanent trail.\n"
            "- You crash if you move off the board, onto a trail, onto a cell another player occupies at the start of the round, "
            "or onto the same cell as another player. Crashed players are out and their trails stay.\n"
            "- An invalid reply counts as a crash.\n"
            f"The game ends when at most one player is left or after {self.max_turns} rounds. Players are ranked by how long they "
            "survived (players still in the game rank highest); players who crash in the same round share a rank. "
            "Rewards are spread evenly from +1 (best rank) to -1 (worst rank); if every player ties, all get 0."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        lines = [f"Current Board:\n{gs['board_state']}", f"Rounds played: {gs['round']}/{self.max_turns}"]
        for pid, player in gs["players"].items():
            you = " (you)" if pid == player_id else ""
            if player.alive:
                lines.append(f"Player {pid}{you} [{format(pid, 'X')}]: alive")
            else:
                lines.append(f"Player {pid}{you}: crashed in round {gs['death_turn'][pid] + 1} ({player.death_reason})")
        return "\n".join(lines)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        token = _dir_token(action)
        if token is None:
            return self.invalid("Reply with exactly one direction: up, down, left or right (or w, s, a, d).")
        self.game_state["pending_actions"][player_id] = token
        return self._resolve_round_if_ready()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
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
                f"Player {player_id} died due to an invalid move: {reason}",
                ta.ObservationType.GAME_ADMIN,
            )
            gs["board_state"] = self._ascii_board(gs["board"], gs["players"])
        gs["pending_actions"][player_id] = None
        return self._resolve_round_if_ready()

    def _resolve_round_if_ready(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        living = [pid for pid, player in gs["players"].items() if player.alive]
        if len(living) <= 1:
            return self._finalise_rewards(f"Player {living[0]} outlived all others." if living else "All players are out.")
        if not all(gs["pending_actions"][pid] for pid in living):
            return None
        outcome = self._apply_simultaneous_moves()
        for pid in gs["pending_actions"]:
            gs["pending_actions"][pid] = None
        return outcome

    def _apply_simultaneous_moves(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        players: Dict[int, _Player] = gs["players"]
        board = gs["board"]

        living = [pid for pid, pl in players.items() if pl.alive]
        old_pos = {pid: players[pid].position for pid in living}
        desired: Dict[int, Tuple[int, int]] = {}

        # 1. desired head positions
        for pid in living:
            dx, dy = _DIR_DELTAS[gs["pending_actions"][pid]]
            x, y = old_pos[pid]
            desired[pid] = (x + dx, y + dy)

        crashes: Dict[int, str] = {}

        # 2. out-of-bounds
        for pid, (x, y) in desired.items():
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                crashes[pid] = "wall"

        # 3. trail collisions
        for pid, (x, y) in desired.items():
            if pid not in crashes and board[y][x] is not None:
                crashes[pid] = "trail"

        # 4. move into current head of someone else (will leave trail)
        current_positions = set(old_pos.values())
        for pid, pos in desired.items():
            if pid not in crashes and pos in current_positions:
                crashes[pid] = "trail"

        # 5. head-on collisions (multiple snakes to same cell)
        bins = defaultdict(list)
        for pid, pos in desired.items():
            if pid not in crashes: bins[pos].append(pid)
        for pos, ids in bins.items():
            if len(ids) > 1:
                for pid in ids: crashes[pid] = "head-on"

        # Every old head square becomes trail, including heads that crash.
        for pid in living:
            ox, oy = old_pos[pid]
            board[oy][ox] = pid

        # ── apply results ──
        for pid in living:
            if pid in crashes:
                players[pid].alive = False
                players[pid].death_reason = crashes[pid]
                gs["death_turn"][pid] = gs["round"]
                self.eliminate(pid)
            else:
                nx, ny = desired[pid]
                players[pid].position = (nx, ny)

        gs["round"] += 1
        gs["board_state"] = self._ascii_board(board, players)
        results = [f"Round {gs['round']} results:"]
        for pid in living:
            direction = gs["pending_actions"][pid]
            if pid in crashes:
                results.append(f"- Player {pid} moved {direction} and crashed ({_CRASH_DESCRIPTIONS[crashes[pid]]}).")
            else:
                results.append(f"- Player {pid} moved {direction}.")
        self.broadcast("\n".join(results), ta.ObservationType.GAME_MESSAGE)

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
