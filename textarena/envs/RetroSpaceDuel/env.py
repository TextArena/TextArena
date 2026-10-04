import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

# key -> (name, dx, dy); y grows downward, so "up" decreases y
DIRECTIONS = {
    "w": ("up", 0, -1), "s": ("down", 0, 1), "a": ("left", -1, 0), "d": ("right", 1, 0),
    "q": ("up-left", -1, -1), "e": ("up-right", 1, -1), "z": ("down-left", -1, 1), "c": ("down-right", 1, 1),
}
CLOCKWISE = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]
_ACTION_RE = re.compile(r"^(f\s*)?([wasdqezc])$", re.IGNORECASE)

OBJECT_KINDS = ("asteroid", "debris", "nebula", "mine", "powerup")
GLYPHS = {"asteroid": "A", "debris": "D", "nebula": "~", "mine": "M", "powerup": "+"}
DESTRUCTIBLE_NAMES = {"debris": "debris", "mine": "a mine", "powerup": "a power-up"}
BOUNDARY, EMPTY = "#", "."
SHIP_SYMBOLS = ("0", "1")

START_HEALTH = 100
SHOT_DAMAGE, SHIELDED_SHOT_DAMAGE = 10, 5
MINE_DAMAGE, SHIELDED_MINE_DAMAGE = 20, 10
SHIELD_CHARGES = 3
BOOSTED_SPEED = 2
POWERUP_TYPES = ("shield", "speed", "weapon")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _format_grid(canvas: List[List[str]]) -> str:
    """Grid with column numbers (x) on top and row numbers (y) on the left."""
    width = len(str(max(len(canvas), len(canvas[0])) - 1))
    header = " " * (width + 1) + " ".join(str(x).rjust(width) for x in range(len(canvas[0])))
    rows = [str(y).rjust(width) + " " + " ".join(cell.rjust(width) for cell in row) for y, row in enumerate(canvas)]
    return "\n".join([header] + rows)


class RetroSpaceDuelEnv(ta.GameEnv):
    """Turn-based two-player space shooter: ships alternate single moves or shots."""
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    grid_size = ta.Param(
        (15, 15), "The arena width and height, including the boundary ring.",
        check=lambda size: len(size) == 2 and all(_is_int(v) and v >= 5 for v in size),
        rule="a (width, height) pair of integers of at least 5",
    )
    max_turns = ta.Param(
        100, "The total number of turns, counting both players, before the duel is decided on health.",
        check=lambda turns: _is_int(turns) and turns >= 2 and turns % 2 == 0,
        rule="a positive even integer, so both ships get the same number of turns",
    )
    num_asteroids = ta.Param(5, "The number of asteroids to scatter.", min=0)
    num_debris = ta.Param(8, "The number of debris objects to scatter.", min=0)
    num_nebulas = ta.Param(3, "The number of nebulas to scatter.", min=0)
    num_mines = ta.Param(4, "The number of mines to scatter.", min=0)
    num_powerups = ta.Param(3, "The number of power-ups to scatter.", min=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.width, self.height = self.grid_size
        counts = {"asteroid": self.num_asteroids, "debris": self.num_debris, "nebula": self.num_nebulas,
                  "mine": self.num_mines, "powerup": self.num_powerups}
        self.object_counts = counts
        free_cells = len(self._placeable_cells())
        if sum(counts.values()) > free_cells:
            raise ValueError(f"a {self.width}x{self.height} arena only has room for {free_cells} objects")

    # ------------------------------------------------------------------ setup
    def setup(self) -> Dict[str, Any]:
        ships = [
            {"pos": pos, "health": START_HEALTH, "shields": 0, "speed": 1, "spread": False}
            for pos in self._spawns()
        ]
        cells = self.rng.sample(self._placeable_cells(), sum(self.object_counts.values()))
        objects: Dict[Tuple[int, int], str] = {}
        for kind in OBJECT_KINDS:
            for _ in range(self.object_counts[kind]):
                objects[cells.pop()] = kind
        return {"ships": ships, "objects": objects}

    def _spawns(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        return (1, 1), (self.width - 2, self.height - 2)

    def _placeable_cells(self) -> List[Tuple[int, int]]:
        """Interior cells outside both spawn neighbourhoods, so no ship starts boxed in or next to a free power-up."""
        reserved = {(sx + dx, sy + dy) for sx, sy in self._spawns() for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
        return [
            (x, y) for y in range(1, self.height - 1) for x in range(1, self.width - 1) if (x, y) not in reserved
        ]

    # ----------------------------------------------------------------- prompts
    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in Retro Space Duel, a turn-based two-player space shooter on a "
            f"{self.width}x{self.height} grid. Your ship is shown as '{SHIP_SYMBOLS[player_id]}' and the enemy ship as "
            f"'{SHIP_SYMBOLS[1 - player_id]}'. Players alternate turns and Player 0 moves first.\n"
            "Positions are (x, y): x is the column number and y the row number printed around the arena, so 'up' "
            "decreases y.\n\n"
            "On your turn, reply with exactly one action:\n"
            "- Move: a single direction key: w (up), s (down), a (left), d (right), q (up-left), e (up-right), "
            "z (down-left), c (down-right).\n"
            "- Shoot: 'f' followed by a direction key.\n"
            "Examples: 'w' (move up), 'c' (move down-right), 'f a' (shoot left), 'f e' (shoot up-right).\n\n"
            "Rules:\n"
            f"- Both ships start with {START_HEALTH} health. A ship whose health reaches 0 is destroyed and its player loses; "
            "if both ships are destroyed on the same turn, the duel is a draw.\n"
            "- Moving: your ship moves 1 cell, or up to 2 cells after a speed power-up (only 1 cell when it starts the move "
            "inside a nebula). The boundary (#), asteroids (A), debris (D) and the enemy ship block movement: a move "
            "stops in front of a blocked cell, and a move whose first cell is blocked is invalid. A move also ends as "
            "soon as your ship enters a nebula, mine or power-up cell.\n"
            "- Shooting: a shot flies in a straight line until it hits something. The enemy ship takes "
            f"{SHOT_DAMAGE} damage ({SHIELDED_SHOT_DAMAGE} while it has a shield charge, which the hit uses up). Debris, "
            "mines and power-ups are destroyed and stop the shot. Shots pass through nebulas, but a ship inside a nebula "
            "can still be hit. A shot that reaches the boundary or an asteroid ricochets back and destroys YOUR ship, so "
            "only fire when something is lined up in that direction.\n"
            f"- Mines (M): entering one costs {MINE_DAMAGE} health ({SHIELDED_MINE_DAMAGE} while you have a shield "
            "charge, which it uses up).\n"
            "- Power-ups (+): entering one grants a random upgrade: shield (recharges your shield to "
            f"{SHIELD_CHARGES} charges), speed (move up to {BOOSTED_SPEED} cells per turn) or spread shot (every shot also "
            "fires two extra projectiles 45 degrees to either side; extra projectiles that reach the boundary or an "
            "asteroid simply dissipate).\n"
            f"- After {self.max_turns} turns in total ({self.max_turns // 2} each), the ship with more health wins; "
            "equal health is a draw.\n\n"
            "Legend: '0' and '1' ships, '#' boundary, 'A' asteroid, 'D' debris, '~' nebula, 'M' mine, '+' power-up, "
            "'.' empty space."
        )

    def render(self, player_id: int) -> str:
        if self.state.done:
            header = "Final arena:"
        else:
            header = f"Turn {self.state.turn + 1}/{self.max_turns}: Player {player_id} to move."
        return f"{header}\n{self.get_board_str()}"

    def get_board_str(self) -> str:
        gs = self.game_state
        canvas = [
            [BOUNDARY if self._is_boundary(x, y) else EMPTY for x in range(self.width)] for y in range(self.height)
        ]
        for (x, y), kind in gs["objects"].items():
            canvas[y][x] = GLYPHS[kind]
        for pid, ship in enumerate(gs["ships"]):
            if ship["health"] > 0:
                x, y = ship["pos"]
                canvas[y][x] = SHIP_SYMBOLS[pid]
        return "\n".join([_format_grid(canvas)] + [self._ship_status(pid) for pid in range(2)])

    def _ship_status(self, player_id: int) -> str:
        ship = self.game_state["ships"][player_id]
        x, y = ship["pos"]
        if ship["health"] <= 0:
            return f"Player {player_id} ('{SHIP_SYMBOLS[player_id]}'): destroyed at ({x}, {y})"
        speed = f"speed {ship['speed']}"
        if self.game_state["objects"].get((x, y)) == "nebula":
            speed += " (inside a nebula: moves 1 cell this turn)"
        weapon = "spread shot" if ship["spread"] else "normal"
        return (
            f"Player {player_id} ('{SHIP_SYMBOLS[player_id]}'): position ({x}, {y}), health {ship['health']}, "
            f"shields {ship['shields']}, {speed}, weapon {weapon}"
        )

    # ----------------------------------------------------------------- actions
    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        match = _ACTION_RE.match(action)
        if match is None:
            return self.invalid(
                "Reply with a direction key (w, a, s, d, q, e, z, c) to move, or 'f' followed by a direction key to "
                "shoot, e.g. 'f a'."
            )
        key = match.group(2).lower()
        if match.group(1):
            self._shoot(player_id, key)
        else:
            invalid = self._move(player_id, key)
            if invalid is not None:
                return invalid
        return self._check_destroyed()

    def on_turn_limit(self) -> ta.Outcome:
        health = [ship["health"] for ship in self.game_state["ships"]]
        if health[0] != health[1]:
            leader = 0 if health[0] > health[1] else 1
            return self.winner(
                leader,
                reason=f"Turn limit reached. Player {leader} wins with more health ({health[leader]} vs {health[1 - leader]}).",
            )
        return self.draw(reason=f"Turn limit reached with equal health ({health[0]} each). The duel ends in a draw.")

    def _move(self, player_id: int, key: str) -> Optional[ta.Invalid]:
        gs = self.game_state
        ship = gs["ships"][player_id]
        name, dx, dy = DIRECTIONS[key]
        start_x, start_y = x, y = ship["pos"]
        steps = 1 if gs["objects"].get((x, y)) == "nebula" else ship["speed"]
        for step in range(steps):
            blocker = self._movement_blocker(x + dx, y + dy, player_id)
            if blocker is not None:
                if step == 0:
                    return self.invalid(
                        f"You cannot move {name} from ({start_x}, {start_y}): ({x + dx}, {y + dy}) is blocked by {blocker}."
                    )
                break
            x, y = x + dx, y + dy
            if gs["objects"].get((x, y)) in ("nebula", "mine", "powerup"):
                break

        ship["pos"] = (x, y)
        self.broadcast(f"Player {player_id} moved {name} to ({x}, {y}).", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        entered = gs["objects"].get((x, y))
        if entered == "mine":
            del gs["objects"][(x, y)]
            damage = self._damage(player_id, MINE_DAMAGE, SHIELDED_MINE_DAMAGE)
            self.broadcast(
                f"Player {player_id} hit a mine at ({x}, {y}) and took {damage} damage (health {ship['health']}).",
                ta.ObservationType.GAME_MESSAGE,
            )
        elif entered == "powerup":
            del gs["objects"][(x, y)]
            self._collect_powerup(player_id)
        return None

    def _movement_blocker(self, x: int, y: int, player_id: int) -> Optional[str]:
        if self._is_boundary(x, y):
            return "the boundary"
        kind = self.game_state["objects"].get((x, y))
        if kind == "asteroid":
            return "an asteroid"
        if kind == "debris":
            return "debris"
        if self.game_state["ships"][1 - player_id]["pos"] == (x, y):
            return "the enemy ship"
        return None

    def _shoot(self, player_id: int, key: str):
        ship = self.game_state["ships"][player_id]
        name, dx, dy = DIRECTIONS[key]
        shot = "a spread shot" if ship["spread"] else "a shot"
        self.broadcast(f"Player {player_id} fired {shot} {name}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._fire(player_id, dx, dy, ricochet_is_lethal=True)
        if ship["spread"]:
            index = CLOCKWISE.index((dx, dy))
            for offset in (-1, 1):
                side_dx, side_dy = CLOCKWISE[(index + offset) % len(CLOCKWISE)]
                self._fire(player_id, side_dx, side_dy, ricochet_is_lethal=False)

    def _fire(self, player_id: int, dx: int, dy: int, ricochet_is_lethal: bool):
        """Resolve one projectile instantly along its straight path."""
        gs = self.game_state
        shooter, target_id = gs["ships"][player_id], 1 - player_id
        target = gs["ships"][target_id]
        x, y = shooter["pos"]
        while True:
            x, y = x + dx, y + dy
            kind = gs["objects"].get((x, y))
            if self._is_boundary(x, y) or kind == "asteroid":
                obstacle = "the boundary" if self._is_boundary(x, y) else f"an asteroid at ({x}, {y})"
                if ricochet_is_lethal:
                    shooter["health"] = 0
                    message = f"Player {player_id}'s shot hit {obstacle} and ricocheted back, destroying their own ship!"
                else:
                    message = f"A side projectile of Player {player_id}'s spread shot hit {obstacle} and dissipated."
                self.broadcast(message, ta.ObservationType.GAME_MESSAGE)
                return
            if target["pos"] == (x, y):
                damage = self._damage(target_id, SHOT_DAMAGE, SHIELDED_SHOT_DAMAGE)
                self.broadcast(
                    f"Player {player_id}'s shot hit Player {target_id} at ({x}, {y}) for {damage} damage "
                    f"(health {target['health']}, shields {target['shields']}).",
                    ta.ObservationType.GAME_MESSAGE,
                )
                return
            if kind in DESTRUCTIBLE_NAMES:
                del gs["objects"][(x, y)]
                self.broadcast(
                    f"Player {player_id}'s shot destroyed {DESTRUCTIBLE_NAMES[kind]} at ({x}, {y}).",
                    ta.ObservationType.GAME_MESSAGE,
                )
                return

    def _damage(self, player_id: int, damage: int, shielded_damage: int) -> int:
        ship = self.game_state["ships"][player_id]
        if ship["shields"] > 0:
            ship["shields"] -= 1
            damage = shielded_damage
        ship["health"] = max(0, ship["health"] - damage)
        return damage

    def _collect_powerup(self, player_id: int):
        ship = self.game_state["ships"][player_id]
        kind = self.rng.choice(POWERUP_TYPES)
        if kind == "shield":
            ship["shields"] = SHIELD_CHARGES
            effect = f"a shield power-up: shields recharged to {SHIELD_CHARGES}."
        elif kind == "speed":
            ship["speed"] = BOOSTED_SPEED
            effect = f"a speed power-up: it now moves up to {BOOSTED_SPEED} cells per turn."
        else:
            ship["spread"] = True
            effect = "a weapon power-up: its shots are now spread shots."
        self.broadcast(f"Player {player_id} collected {effect}", ta.ObservationType.GAME_MESSAGE)

    def _check_destroyed(self) -> Optional[ta.Outcome]:
        destroyed = [pid for pid, ship in enumerate(self.game_state["ships"]) if ship["health"] <= 0]
        if len(destroyed) == 2:
            return self.draw(reason="Both ships were destroyed on the same turn. The duel ends in a draw.")
        if destroyed:
            loser = destroyed[0]
            return self.winner(1 - loser, reason=f"Player {1 - loser} wins - Player {loser}'s ship was destroyed.")
        return None

    def _is_boundary(self, x: int, y: int) -> bool:
        return not (0 < x < self.width - 1 and 0 < y < self.height - 1)
