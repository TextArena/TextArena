import math, itertools, re
from collections import deque
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta
from textarena.envs.Snake.renderer import create_board_str, head_symbol

_DIR_DELTAS = {"up":(0,1), "w":(0,1), "down":(0,-1), "s":(0,-1), "left":(-1,0), "a":(-1,0), "right":(1,0), "d":(1,0)}
_DIR_NAMES = {"w": "up", "s": "down", "a": "left", "d": "right"}
_DIR_RE = re.compile(r"^(up|down|left|right|w|a|s|d)$", re.I)
_DEATH_DESCRIPTIONS = {"wall": "hit the wall", "head-on": "collided head-on", "body collision": "ran into a snake body"}

def _dir_token(move: str) -> Optional[str]:
    """Return the direction name if *move* is a single bare direction."""
    m = _DIR_RE.match(move)
    if not m:
        return None
    token = m.group(1).lower()
    return _DIR_NAMES.get(token, token)

class Snake:
    """ Represents a snake in the game with position and alive status """
    def __init__(self, positions: List[Tuple[int, int]]):
        self.positions = deque(positions)
        self.alive: bool = True
        self.death_reason: Optional[str] = None
    @property
    def head(self) -> Tuple[int, int]:
        return self.positions[0]

class SnakeEnv(ta.GameEnv):
    """ N-player Snake environment with simultaneous movement """
    min_players = 2
    max_players = 15
    mdp_includes_actions = False
    broadcast_actions = False  # moves are sealed until the round resolves

    width = ta.Param(10, "The board width.", min=1)
    height = ta.Param(10, "The board height.", min=1)
    num_apples = ta.Param(3, "The number of apples kept on the board (fewer only when no empty cell is left).", min=0)
    max_turns = ta.Param(100, "The number of rounds, each one move by every living snake, before the game ends.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.width * self.height < self.num_apples + 15:
            raise ValueError(f"Board {self.width}x{self.height} too small for {self.num_apples} apples and up to 15 snakes")

    @property
    def pending_actions(self) -> Dict[int, Optional[str]]:
        return self.game_state["pending_actions"]

    def _generate_spawn_positions(self, k: int) -> List[Tuple[int, int]]:
        """ Farthest-point sampling for balanced spawns. """
        candidates = [(x, y) for x in range(1, self.width - 1) for y in range(1, self.height - 1)]
        if len(candidates) < k:
            candidates = [(x, y) for x in range(self.width) for y in range(self.height)]
        if len(candidates) < k:
            raise ValueError(f"Board {self.width}x{self.height} is too small for {k} snakes")
        self.rng.shuffle(candidates)
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
        return self.rng.choice(free) if free else None

    def get_board_str(self):
        return create_board_str(width=self.width, height=self.height, snakes=self.state.game_state["snakes"], apples=self.state.game_state["apples"])

    def _get_board_string(self, snakes: Dict[int, "Snake"], apples: List[Tuple[int, int]]) -> str:
        """ASCII board. Top row printed first so y grows upward."""
        return create_board_str(width=self.width, height=self.height, snakes=snakes, apples=apples)

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        # Engine turns count individual submissions, while Snake resolves and
        # limits complete simultaneous rounds.
        self.state.max_turns = None
        snakes = {pid: Snake([pos]) for pid, pos in enumerate(self._generate_spawn_positions(num_players))}
        apples: List[Tuple[int, int]] = []
        for _ in range(self.num_apples):
            cell = self._random_free_cell(snakes, apples)
            if cell is not None:
                apples.append(cell)
        scores = {pid: 0 for pid in range(num_players)}
        game_state = {
            "snakes": snakes, "apples": apples, "scores": scores, "death_turn": {},
            "board_state": "", "pending_actions": {pid: None for pid in range(num_players)},
            "round_count": 0,
        }
        game_state["board_state"] = self._get_board_string(snakes, apples)
        return game_state

    def prompt(self, player_id: int) -> str:
        return (
            f"{self.state.num_players}-Player Snake on a {self.width}×{self.height} grid.\n"
            f"You control snake {player_id}; its head is shown as '{head_symbol(player_id)}'.\n"
            "Every round, all living snakes move one cell at the same time. Reply with one direction: "
            "'up', 'down', 'left' or 'right' (or 'w', 's', 'a', 'd'); 'up' moves toward the top of the printed board. "
            "Moves stay hidden until the round resolves.\n"
            f"Board legend: heads show snake numbers (snakes 10-14 appear as A-E), '#' is a body segment, '*' is an apple, '.' is empty.\n"
            "Rules:\n"
            "- Moving onto an apple scores 1 point and grows your snake by one segment; eaten apples reappear on random empty cells.\n"
            "- A snake dies if it moves off the board, into a cell occupied by any snake (including itself and snakes that die this round), "
            "into the same cell as another head, or trades places with another head. A tail cell is free if its snake moves on this round "
            "without eating or dying.\n"
            "- An invalid reply gets a warning and you reply again; a second invalid reply in a row kills your snake.\n"
            f"The game ends when at most one snake is alive or after {self.max_turns} rounds. Living snakes rank above dead ones, "
            "dead snakes rank by the round they died in (later is better), and score breaks ties; snakes that are still tied share a rank. "
            "Rewards are spread evenly from +1 (best rank) to -1 (worst rank); if every snake ties, all get 0."
        )

    def render(self, player_id: int) -> str:
        gs = self.game_state
        lines = [f"Current Board:\n{gs['board_state']}", f"Rounds played: {gs['round_count']}/{self.max_turns}"]
        for pid, snake in gs["snakes"].items():
            you = " (you)" if pid == player_id else ""
            if snake.alive:
                lines.append(f"Snake {pid}{you} [{head_symbol(pid)}]: length {len(snake.positions)}, score {gs['scores'][pid]}")
            else:
                lines.append(f"Snake {pid}{you}: died in round {gs['death_turn'][pid] + 1} ({snake.death_reason}), score {gs['scores'][pid]}")
        return "\n".join(lines)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        token = _dir_token(action)
        if token is None:
            return self.invalid("Reply with exactly one direction: up, down, left or right (or w, s, a, d).")
        self.game_state["pending_actions"][player_id] = token
        return self._resolve_round_if_ready()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        gs = self.game_state
        snake = gs["snakes"][player_id]
        if snake.alive:
            snake.alive = False
            snake.death_reason = "invalid move"
            gs["death_turn"][player_id] = gs["round_count"]
            self.eliminate(player_id)
            self.broadcast(f"Snake {player_id} died due to an invalid move: {reason}", ta.ObservationType.GAME_MESSAGE)
            gs["board_state"] = self._get_board_string(gs["snakes"], gs["apples"])
        gs["pending_actions"][player_id] = None
        return self._resolve_round_if_ready()

    def _resolve_round_if_ready(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        living = [pid for pid, snake in gs["snakes"].items() if snake.alive]
        if len(living) <= 1:
            return self._finalise_rewards(f"Snake {living[0]} outlived all others." if living else "All snakes are dead.")
        if not all(gs["pending_actions"][pid] for pid in living):
            return None
        outcome = self._apply_simultaneous_moves()
        for pid in gs["pending_actions"]:
            gs["pending_actions"][pid] = None
        return outcome

    def on_turn_limit(self) -> ta.Outcome:
        return self._finalise_rewards("Turn limit reached - best score wins tie-break.")

    def _finalise_rewards(self, reason: str) -> ta.Outcome:
        snakes = self.game_state["snakes"]
        scores = self.game_state["scores"]
        death_turn = self.game_state["death_turn"]

        # 1) survival time in complete simultaneous rounds.
        survival_turn = {
            pid: self.game_state["round_count"] if s.alive else death_turn.get(pid, -1)
            for pid, s in snakes.items()
        }

        # 2) keys
        #    • lifetime  (higher -> better)
        #    • alive?    (True>False breaks same-turn ties)
        #    • score     (higher -> better)
        #    • -pid      only to keep ordering deterministic
        sort_key  = lambda pid: (survival_turn[pid], snakes[pid].alive, scores[pid], -pid)
        group_key = lambda pid: (survival_turn[pid], snakes[pid].alive, scores[pid])

        ranked = sorted(range(self.state.num_players), key=sort_key)

        # 3) collapse equal-key players into tie-groups
        groups: list[list[int]] = []
        for pid in ranked:
            if not groups or group_key(groups[-1][0]) != group_key(pid):
                groups.append([pid])
            else:
                groups[-1].append(pid)

        # 4) assign rewards
        G = len(groups)
        reward_dict: dict[int, float] = {}
        if G == 1:                         # complete draw
            reward_dict = {pid: 0.0 for pid in groups[0]}
        else:
            for g_idx, g in enumerate(groups):           # worst -> best
                r = -1.0 + 2.0 * g_idx / (G - 1)         # linear scale
                for pid in g: reward_dict[pid] = r

        return self.outcome(reward_dict, reason=f"{reason} Final ranking groups (worst→best): {groups}")

    def _apply_simultaneous_moves(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        snakes = gs["snakes"]
        apples = gs["apples"]
        scores = gs["scores"]
        deaths: Dict[int, str] = {}
        old_head = {pid: s.head for pid, s in snakes.items() if s.alive}

        # 1. Calculate desired new head positions
        desired = {}
        for pid, snake in snakes.items():
            if not snake.alive:
                continue
            # Skip if no pending action (e.g., player died from invalid move)
            if gs["pending_actions"][pid] is None:
                continue
            dx, dy = _DIR_DELTAS[gs["pending_actions"][pid]]
            hx, hy = snake.head
            desired[pid] = (hx + dx, hy + dy)
        planned = dict(desired)

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
            gs["death_turn"][pid] = gs["round_count"]
            self.eliminate(pid)
            desired.pop(pid, None)

        # 6. Check for body collisions. A tail vacates only if its snake
        # survives long enough to complete a non-growing move. Discovering a
        # body collision can therefore make that snake's tail solid and cause
        # another collision; iterate until no new deaths are found.
        while True:
            occupied = set()
            for pid in old_head:
                snake = snakes[pid]
                for i, pos in enumerate(snake.positions):
                    is_tail = i == len(snake.positions) - 1
                    tail_vacates = pid not in deaths and planned[pid] not in apples
                    if not is_tail or not tail_vacates:
                        occupied.add(pos)

            collided = {
                pid
                for pid, new_head in desired.items()
                if new_head in occupied
            }
            if not collided:
                break
            for pid in collided:
                deaths[pid] = "body collision"
                desired.pop(pid)

        for pid in deaths:
            snake = snakes[pid]
            if snake.alive:
                snake.alive, snake.death_reason = False, deaths[pid]
                gs["death_turn"][pid] = gs["round_count"]
                self.eliminate(pid)

        # 7. Execute moves for surviving snakes
        eating = {pid for pid, new_head in desired.items() if new_head in apples}
        for pid, new_head in desired.items():
            snake = snakes[pid]
            snake.positions.appendleft(new_head)
            if pid in eating:
                apples.remove(new_head)
                scores[pid] += 1
            else:
                snake.positions.pop()  # no growth

        # Replenish only after every snake has moved so a new apple cannot spawn
        # underneath a later snake's already-committed destination.
        while len(apples) < self.num_apples:
            new_apple = self._random_free_cell(snakes, apples)
            if new_apple is None:
                break
            apples.append(new_apple)

        # 8. Update the board state and reveal the round's moves
        gs["board_state"] = self._get_board_string(snakes, apples)
        gs["round_count"] += 1
        results = [f"Round {gs['round_count']} results:"]
        for pid in sorted(planned):
            direction = gs["pending_actions"][pid]
            if pid in deaths:
                results.append(f"- Snake {pid} moved {direction} and died ({_DEATH_DESCRIPTIONS[deaths[pid]]}).")
            elif pid in eating:
                results.append(f"- Snake {pid} moved {direction} and ate an apple.")
            else:
                results.append(f"- Snake {pid} moved {direction}.")
        self.broadcast("\n".join(results), ta.ObservationType.GAME_MESSAGE)

        # 9. Check for end-of-game conditions
        alive = [pid for pid, s in snakes.items() if s.alive]
        if len(alive) <= 1:
            return self._finalise_rewards(f"Player {alive[0]} survived; all others perished." if alive else "All snakes died simultaneously.")
        if gs["round_count"] >= self.max_turns:
            return self.on_turn_limit()
        return None
