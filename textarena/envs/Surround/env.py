import random, math
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Any

import textarena as ta
from textarena.envs.Surround.renderer import create_board_str 

_DIR_DELTAS = {"up": (0, 1), "w": (0, 1), "down": (0, -1), "s": (0, -1), "left": (-1, 0), "a": (-1, 0), "right": (1, 0), "d": (1, 0)}

def _step_from_str(move: str) -> Tuple[int, int]:
    """Return (dx, dy) for the *first* direction token in *move*."""
    lower = move.lower()
    for tok, d in _DIR_DELTAS.items():
        if f"[{tok}]" in lower: return d
    return (0, 0)

class _Player:
    def __init__(self, pos: Tuple[int, int]):
        self.position: Tuple[int, int] = pos
        self.alive: bool = True
        self.death_reason: Optional[str] = None

class SurroundEnv(ta.Env):
    MAX_PLAYERS = 15
    def __init__(self, width: int = 10, height: int = 10, max_turns: int = 100):
        if width * height < self.MAX_PLAYERS + 5: raise ValueError("Board too small for potential players+trails")
        self.width, self.height, self.max_turns = width, height, max_turns
        self.pending_actions: Dict[int, Optional[str]] = {}

    def get_board_str(self) -> str: return create_board_str(width=self.width, height=self.height, board=self.state.game_state["board"], players=self.state.game_state["players"])
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

    def _random_free_cell(self, occupied: set[Tuple[int, int]]) -> Tuple[int, int]:
        while True:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            if (x, y) not in occupied: return (x, y)

    def reset(self, num_players: int, seed: Optional[int] = None):
        if not 2 <= num_players <= self.MAX_PLAYERS: raise ValueError(f"2 ≤ players ≤ {self.MAX_PLAYERS}")
        self.state = ta.FFAMultiPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        # spawn players (farthest-point sampling like Snake for fairness)
        spawns: List[Tuple[int, int]] = self._generate_spawn_positions(num_players)
        players: Dict[int, _Player] = {pid: _Player(pos) for pid, pos in enumerate(spawns)}
        game_state = {"board": [[None for _ in range(self.width)] for _ in range(self.height)], "players": players, "death_turn": {}, "board_state": "",}
        self.state.reset(game_state=game_state, player_prompt_function=self._prompt)
        self.pending_actions = {pid: None for pid in range(num_players)}
        # initial board broadcast
        game_state["board_state"] = self._ascii_board(game_state["board"], players)
        self.state.add_observation(self.m("board", "current", board=game_state['board_state']), observation_type=ta.ObservationType.GAME_BOARD)

    def _generate_spawn_positions(self, k: int) -> List[Tuple[int, int]]:
        candidates = [(x, y) for x in range(1, self.width - 1) for y in range(1, self.height - 1)]
        if len(candidates) < k: raise ValueError("Board too small for spawn sampling")
        random.shuffle(candidates)
        spawns = [candidates.pop()]
        while len(spawns) < k:
            best = max(candidates, key=lambda p: min(math.dist(p, s) for s in spawns))
            spawns.append(best)
            candidates.remove(best)
        return spawns

    def _prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", num_players=self.state.num_players, width=self.width, height=self.height, player_id=player_id)

    def step(self, action: str):
        pid = self.state.current_player_id
        token = next((t for t in _DIR_DELTAS if f"[{t}]" in action.lower()), None)

        # Invalid move → instant death, like in SnakeEnv
        players: Dict[int, _Player] = self.state.game_state["players"]
        if token is None:
            pl = players[pid]
            if pl.alive:
                pl.alive, pl.death_reason = False, "invalid move"
                self.state.game_state["death_turn"][pid] = self.state.turn
                self.state.add_observation(self.m("game_action", "invalid_death", player_id=pid), observation_type=ta.ObservationType.GAME_ADMIN)
            self.pending_actions[pid] = None
        else:
            self.pending_actions[pid] = action

        # resolve turn when all living acted
        living = [p for p, pl in players.items() if pl.alive]
        if living and all(self.pending_actions[p] for p in living):
            self._apply_simultaneous_moves()
            for p in living:
                self.pending_actions[p] = None

        self._rotate_players()
        self._check_turn_limit()
        return self.state.step(rotate_player=False)

    def _apply_simultaneous_moves(self):
        gs = self.state.game_state
        players: Dict[int, _Player] = gs["players"]
        board = gs["board"]

        living = [pid for pid, pl in players.items() if pl.alive]
        old_pos = {pid: players[pid].position for pid in living}
        desired: Dict[int, Tuple[int, int]] = {}

        # 1. desired head positions
        for pid in living:
            dx, dy = _step_from_str(self.pending_actions[pid])
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

        # ── apply results ──
        for pid in living:
            if pid in crashes:
                players[pid].alive = False
                players[pid].death_reason = "crash"
                gs["death_turn"][pid] = self.state.turn
            else:
                ox, oy = old_pos[pid]
                nx, ny = desired[pid]
                players[pid].position = (nx, ny)
                board[oy][ox] = pid              # leave trail

        # ── end-of-game checks ──
        alive = [pid for pid, pl in players.items() if pl.alive]
        if len(alive) <= 1:
            if alive: self._finalise_rewards(self.m("outcome", "survived_win", player_id=alive[0]))
            else: self._finalise_rewards(self.m("outcome", "all_crashed"))
            self.state.step(rotate_player=False)   # make terminal transition
            return

        # broadcast board every normal turn
        gs["board_state"] = self._ascii_board(board, players)
        self.state.add_observation(self.m("board", "after_moves", board=gs['board_state']), observation_type=ta.ObservationType.GAME_BOARD)

    def _rotate_players(self):
        if self.state.done: return
        alive = {pid for pid, pl in self.state.game_state["players"].items() if pl.alive}
        if len(alive) <= 1: self._finalise_rewards(self.m("outcome", "outlived") if alive else self.m("outcome", "all_dead")); return
        nxt = (self.state.current_player_id + 1) % self.state.num_players
        while nxt not in alive: nxt = (nxt + 1) % self.state.num_players
        self.state.manually_set_current_player_id(nxt)

    def _check_turn_limit(self):
        if not self.state.done and self.state.turn >= self.state.max_turns: self._finalise_rewards(self.m("outcome", "turn_limit"))

    def _finalise_rewards(self, reason: str):
        survival_turn = {pid: (self.state.turn + 1) if pl.alive else self.state.game_state["death_turn"].get(pid, -1) for pid, pl in self.state.game_state["players"].items()}
        # build ranking groups (same survival = tie)
        sorted_pids = sorted(range(self.state.num_players), key=lambda pid: (survival_turn[pid], self.state.game_state["players"][pid].alive, -pid))
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
        self.state.set_game_outcome(reward_dict=reward, reason=self.m("outcome", "ranking", reason=reason, groups=list(reversed(groups))))
