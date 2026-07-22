import random, math, itertools
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import textarena as ta
from textarena.envs.Snake.renderer import create_board_str

_DIR_DELTAS = {"up":(0,1), "w":(0,1), "down":(0,-1), "s":(0,-1), "left":(-1,0), "a":(-1,0), "right":(1,0), "d":(1,0)}

def _step_from_str(move: str) -> Tuple[int, int]:
    """Return (dx, dy) corresponding to the *first* direction token in *move*."""
    lower = move.lower()
    for token, delta in _DIR_DELTAS.items():
        if f"[{token}]" in lower: return delta
    return (0, 0) # unreachable if caller validated the string first

class Snake:
    """ Represents a snake in the game with position and alive status """
    def __init__(self, positions: List[Tuple[int, int]]):
        self.positions = deque(positions)
        self.alive: bool = True
        self.death_reason: Optional[str] = None
    @property
    def head(self) -> Tuple[int, int]:
        return self.positions[0]

class SnakeEnv(ta.Env):
    """ N-player Snake environment with simultaneous movement """
    def __init__(self, width: int = 10, height: int = 10, num_apples: int = 3, max_turns: int = 100):
        if width * height < (num_apples + 15): raise ValueError(f"Board {width}x{height} too small for {num_apples} apples and up to {15} snakes")
        self.width, self.height = width, height
        self.num_apples = num_apples
        self.max_turns = max_turns
        self.pending_actions: Dict[int, Optional[str]] = {}

    def _generate_spawn_positions(self, k: int) -> List[Tuple[int, int]]:
        """ Farthest-point sampling for balanced spawns. """
        candidates = [(x, y) for x in range(1, self.width - 1) for y in range(1, self.height - 1)]
        if len(candidates) < k: raise ValueError(f"Board {self.width}x{self.height} is too small for {k} snakes (needs inner cells)")
        random.shuffle(candidates)
        spawns = [candidates.pop()]
        while len(spawns) < k:
            best = max(candidates, key=lambda p: min(math.dist(p, s) for s in spawns))
            spawns.append(best)
            candidates.remove(best)
        return spawns

    def _random_free_cell(self, snakes: Dict[int, "Snake"] | None = None, apples: List[Tuple[int, int]] | None = None) -> Optional[Tuple[int, int]]:
        """ Return a uniform random free cell or *None* if board is full """
        occupied = {p for s in (snakes or {}).values() if s.alive for p in s.positions}
        occupied.update(apples or [])
        free = [(x, y) for x in range(self.width) for y in range(self.height) if (x, y) not in occupied]
        return random.choice(free) if free else None

    def get_board_str(self):
        return create_board_str(width=self.width, height=self.height, snakes=self.state.game_state["snakes"], apples=self.state.game_state["apples"])

    def _get_board_string(self, snakes: Dict[int, "Snake"], apples: List[Tuple[int, int]]) -> str:
        """ASCII board. Top row printed last so y grows upward."""
        board = [["." for _ in range(self.width)] for _ in range(self.height)]
        for ax, ay in apples:
            board[ay][ax] = "A"
        for pid, snake in snakes.items():
            if not snake.alive: continue
            for idx, (x, y) in enumerate(snake.positions):
                board[y][x] = format(pid, "X") if idx == 0 else "#"
        horiz = "+" + "-" * (self.width * 2 + 1) + "+"
        lines = [horiz]
        for row in reversed(board):
            lines.append("| " + " ".join(row) + " |")
        lines.append(horiz)
        return "\n".join(lines)

    def reset(self, num_players: int, seed: Optional[int] = None):
        assert 2<=num_players<=15, f"The number of players has to be 2<=x<=15, received {num_players}"
        self.state = ta.FFAMultiPlayerState(num_players=num_players, max_turns=self.max_turns, seed=seed)
        snakes = {pid: Snake([pos]) for pid, pos in enumerate(self._generate_spawn_positions(num_players))}
        apples: List[Tuple[int, int]] = [c for _ in range(self.num_apples) if (c := self._random_free_cell(snakes, [])) is not None]
        scores = {pid: 0 for pid in range(num_players)}
        game_state = {"snakes": snakes, "apples": apples, "scores": scores, "death_turn": {}, "board_state": ""}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self.pending_actions = {pid: None for pid in range(num_players)}
        game_state["board_state"] = self._get_board_string(snakes, apples)
        self.state.add_observation(self.m("board", "current", board=game_state['board_state']), observation_type=ta.ObservationType.GAME_BOARD)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        return self.m("player_prompt", "intro", num_players=self.state.num_players, width=self.width, height=self.height, player_id=player_id, max_turns=self.max_turns)

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        snakes = self.state.game_state["snakes"]
        pid = self.state.current_player_id

        # ── validate & possibly kill on invalid ──
        token = next((k for k in _DIR_DELTAS if f"[{k}]" in action.lower()), None)
        if token is None:
            snake = snakes[pid]
            if snake.alive:
                snake.alive = False
                snake.death_reason = "invalid move"
                self.state.game_state["death_turn"][pid] = self.state.turn
                self.state.add_observation(self.m("game_action", "invalid_death", player_id=pid), observation_type=ta.ObservationType.GAME_MESSAGE)

            self.pending_actions[pid] = None  # clear any stale action
        else: self.pending_actions[pid] = action

        # ── resolve turn if all living snakes have acted ──
        living = [p for p, s in snakes.items() if s.alive]
        if living and all(self.pending_actions[p] for p in living):
            self._apply_simultaneous_moves()
            for p in living:
                self.pending_actions[p] = None

        self._rotate_players()
        self._check_turn_limit()
        return self.state.step(rotate_player=False)

    def _check_turn_limit(self):
        if not self.state.done and self.state.turn >= self.state.max_turns:
            self._finalise_rewards(self.m("outcome", "turn_limit"))

    def _rotate_players(self):
        if self.state.done:
            return
        alive = {pid for pid, s in self.state.game_state["snakes"].items() if s.alive}
        if len(alive) <= 1:
            self._finalise_rewards(self.m("outcome", "outlived") if alive else self.m("outcome", "all_dead"))
            return
        nxt = (self.state.current_player_id + 1) % self.state.num_players
        while nxt not in alive:
            nxt = (nxt + 1) % self.state.num_players
        self.state.manually_set_current_player_id(nxt)

    def _finalise_rewards(self, reason: str):
        snakes = self.state.game_state["snakes"]
        scores = self.state.game_state["scores"]
        death_turn = self.state.game_state["death_turn"]

        # 1) survival time (alive snakes count the current turn + 1)
        survival_turn = {pid: (self.state.turn + 1) if s.alive else death_turn.get(pid, -1) for pid, s in snakes.items()}

        # 2) keys
        #    • lifetime  (higher -> better)
        #    • alive?    (True>False breaks same-turn ties)
        #    • score     (higher -> better)
        #    • -pid      only to keep ordering deterministic
        sort_key  = lambda pid: (survival_turn[pid], snakes[pid].alive, scores[pid], -pid)
        group_key = lambda pid: (survival_turn[pid], snakes[pid].alive, scores[pid])
        
        # Sort players by performance
        ranked = sorted(range(self.state.num_players), key=sort_key)

        # 3) collapse equal-key players into tie-groups
        groups: list[list[int]] = []
        for pid in ranked:
            if not groups or group_key(groups[-1][0]) != group_key(pid): 
                groups.append([pid])
            else: 
                groups[-1].append(pid)

        # print("DEBUG: Final groups:", groups)

        # 4) assign rewards
        G = len(groups)
        reward_dict: dict[int, float] = {}

        if G == 1:                         # complete draw
            reward_dict = {pid: 0.0 for pid in groups[0]}
        else:
            for g_idx, g in enumerate(groups):           # worst -> best
                r = -1.0 + 2.0 * g_idx / (G - 1)         # linear scale
                for pid in g: reward_dict[pid] = r
        # 5) finish
        self.state.set_game_outcome(reward_dict=reward_dict, reason=self.m("outcome", "ranking", reason=reason, groups=groups))



    # the heavy lifting lives here (unchanged from previous refactor)
    def _apply_simultaneous_moves(self):
        snakes = self.state.game_state["snakes"]
        apples = self.state.game_state["apples"]
        scores = self.state.game_state["scores"]
        deaths: Dict[int, str] = {}
        old_head = {pid: s.head for pid, s in snakes.items() if s.alive}
        
        # 1. Calculate desired new head positions
        desired = {}
        for pid, snake in snakes.items():
            if not snake.alive:
                continue
            # Skip if no pending action (e.g., player died from invalid move)
            if self.pending_actions[pid] is None:
                continue
            dx, dy = _step_from_str(self.pending_actions[pid])
            hx, hy = snake.head
            desired[pid] = (hx + dx, hy + dy)
        
        # 2. Check for wall collisions
        for pid, (x, y) in desired.items():
            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                deaths[pid] = "wall"
        
        # 3. Check for head-on collisions (multiple snakes moving to same position)
        bins: Dict[Tuple[int, int], List[int]] = {}
        for pid, pos in desired.items():
            bins.setdefault(pos, []).append(pid)
        for pos, ids in bins.items():
            if len(ids) > 1:
                for pid in ids:
                    deaths[pid] = "head-on"
        
        # 4. Check for swap collisions (two snakes swapping positions)
        for a, b in itertools.combinations(desired, 2):
            if desired[a] == old_head[b] and desired[b] == old_head[a]:
                deaths[a] = deaths[b] = "head-on"
        
        # 5. Remove dead snakes and prune their desired positions
        for pid, reason in deaths.items():
            snake = snakes[pid]
            snake.alive, snake.death_reason = False, reason
            self.state.game_state["death_turn"][pid] = self.state.turn
            desired.pop(pid, None)
        
        # 6. Check for body collisions
        # Build occupied positions, excluding tails that will move (unless snake eats apple)
        occupied = set()
        for pid, snake in snakes.items():
            if snake.alive:
                # Add all positions except the tail (tail will move unless snake eats apple)
                for i, pos in enumerate(snake.positions):
                    if i < len(snake.positions) - 1:  # Not the tail
                        occupied.add(pos)
                    else:  # This is the tail
                        # Only add tail to occupied if this snake will eat an apple (and thus not move tail)
                        if pid in desired and desired[pid] in apples:
                            occupied.add(pos)
        
        # Check if any snake would move into an occupied position
        for pid, new_head in list(desired.items()):
            if new_head in occupied:
                snake = snakes[pid]
                snake.alive, snake.death_reason = False, "body collision"
                self.state.game_state["death_turn"][pid] = self.state.turn
                desired.pop(pid)
        
        # 7. Execute moves for surviving snakes
        for pid, new_head in desired.items():
            snake = snakes[pid]
            snake.positions.appendleft(new_head)
            
            # Check if snake ate an apple
            if new_head in apples:
                apples.remove(new_head)
                scores[pid] += 1
                # Snake grows (don't remove tail)
                # Spawn new apple
                if (na := self._random_free_cell(snakes, apples)):
                    apples.append(na)
            else:
                # Snake didn't eat apple, remove tail (no growth)
                snake.positions.pop()
        
        # 8. Update board state and broadcast (always do this)
        self.state.game_state["board_state"] = self._get_board_string(snakes, apples)
        self.state.add_observation(from_id=ta.GAME_ID, to_id=-1, message=self.m("board", "after_moves", board=self.state.game_state['board_state']), observation_type=ta.ObservationType.GAME_BOARD)

        # 9. Check for end-of-game conditions
        alive = [pid for pid, s in snakes.items() if s.alive]
        if len(alive) <= 1:
            self._finalise_rewards(self.m("outcome", "survived_win", player_id=alive[0]) if alive else self.m("outcome", "all_dead_simul"))
            self.state.step(rotate_player=False)  # propagate terminal transition
            return
        # 7 broadcast
        self.state.game_state["board_state"] = self._get_board_string(snakes, apples)
        self.state.add_observation(self.m("board", "current", board=self.state.game_state['board_state']), observation_type=ta.ObservationType.GAME_BOARD)

