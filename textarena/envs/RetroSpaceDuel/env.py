import random
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta


class RetroSpaceDuelEnv(ta.Env):
    """Environment for playing Retro Space Duel, a two-player competitive space shooter."""

    def __init__(self, grid_size: Tuple[int, int] = (15, 15), max_turns: int = 100,
                 num_asteroids: int = 5, num_debris: int = 8, num_nebulas: int = 3,
                 num_mines: int = 4, num_powerups: int = 3):
        self.grid_size = grid_size
        self.width, self.height = grid_size
        self.max_turns = max_turns
        self.num_asteroids = num_asteroids
        self.num_debris = num_debris
        self.num_nebulas = num_nebulas
        self.num_mines = num_mines
        self.num_powerups = num_powerups

        self.directions = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)]

        # Emoji mappings
        self.empty_symbol = '  '
        self.boundary_symbol = '🌍'
        self.asteroid_symbol = '💥'   # Indestructible
        self.debris_symbol = '🟤'     # Destructible
        self.nebula_symbol = '🌪️'    # Slows movement, projectiles pass through
        self.mine_symbol = '💣'       # Destructible
        self.powerup_symbol = '⚡'     # Destructible
        self.projectile_symbol = '🔥'
        self.player_symbols = {0: '🚀', 1: '🛸'}

    def get_board_str(self):
        return self._get_arena_state()

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)

        self.player_positions = [(1, 1), (self.width - 2, self.height - 2)]
        self.player_health = [100, 100]
        self.player_shields = [0, 0]
        self.player_speed = [1, 1]
        self.player_weapons = [1, 1]
        self.projectiles = []  # (x, y, dx, dy, player_id)

        self._generate_game_elements()

        game_state = {"arena_state": self._get_arena_state(), "turn": 0, "max_turns": self.max_turns}
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
            role_mapping={0: "Player 1", 1: "Player 2"},
        )
        self.state.add_observation(message=self._get_arena_state(), observation_type=ta.ObservationType.GAME_BOARD)

    def _generate_game_elements(self):
        def get_random_position(existing_positions):
            attempts = 0
            while attempts < 100:
                pos = (random.randint(1, self.width - 2), random.randint(1, self.height - 2))
                if pos not in existing_positions and pos not in self.player_positions:
                    return pos
                attempts += 1
            return None

        all_positions = []
        for target, count in (
            ("asteroids", self.num_asteroids), ("debris", self.num_debris),
            ("nebulas", self.num_nebulas), ("mines", self.num_mines), ("powerups", self.num_powerups),
        ):
            placed = []
            for _ in range(count):
                pos = get_random_position(all_positions)
                if pos:
                    placed.append(pos)
                    all_positions.append(pos)
            setattr(self, target, placed)

    def _get_arena_state(self) -> str:
        grid = [[self.empty_symbol for _ in range(self.width)] for _ in range(self.height)]

        # Boundaries
        for i in range(self.width):
            grid[0][i] = self.boundary_symbol
            grid[self.height - 1][i] = self.boundary_symbol
        for i in range(self.height):
            grid[i][0] = self.boundary_symbol
            grid[i][self.width - 1] = self.boundary_symbol

        for layer, symbol in (
            (self.asteroids, self.asteroid_symbol), (self.debris, self.debris_symbol),
            (self.nebulas, self.nebula_symbol), (self.mines, self.mine_symbol),
            (self.powerups, self.powerup_symbol),
        ):
            for x, y in layer:
                if 0 <= y < self.height and 0 <= x < self.width:
                    grid[y][x] = symbol

        for x, y, _, _, _ in self.projectiles:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.projectile_symbol

        for i, (x, y) in enumerate(self.player_positions):
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.player_symbols[i]

        return '\n'.join([''.join(row) for row in grid])

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        opponent_id = 1 - player_id
        element_descriptions = {
            self.empty_symbol: 'Empty space',
            self.boundary_symbol: 'Boundary (blocks everything, reflects projectiles)',
            self.asteroid_symbol: 'Asteroid (indestructible, reflects projectiles)',
            self.debris_symbol: 'Debris (destructible, blocks movement)',
            self.nebula_symbol: 'Nebula (slows movement, projectiles pass through)',
            self.mine_symbol: 'Mine (destructible, causes damage on contact)',
            self.powerup_symbol: 'Power-up (destructible, grants special abilities)',
            self.projectile_symbol: 'Projectile (causes damage on contact)',
            self.player_symbols[player_id]: 'Your spaceship',
            self.player_symbols[opponent_id]: 'Enemy spaceship',
        }
        in_nebula = self.player_positions[player_id] in self.nebulas
        prompt = (
            f"=== RETRO SPACE DUEL - TURN {game_state['turn']}/{game_state['max_turns']} ===\n\n"
            f"You are Player {player_id + 1} in Retro Space Duel.\n"
            f"Your position: {self.player_positions[player_id]}\n"
            f"Your health: {self.player_health[player_id]}\n"
            f"Your shield: {self.player_shields[player_id]} remaining\n"
            f"Your speed: {self.player_speed[player_id]} {'(reduced in nebula)' if in_nebula else ''}\n"
            f"Your weapon: {'Normal' if self.player_weapons[player_id] == 1 else 'Spread Shot'}\n\n"
            f"Enemy health: {self.player_health[opponent_id]}\n"
            f"Enemy position: {self.player_positions[opponent_id]}\n\n"
            "LEGEND:\n"
        )
        for symbol, description in element_descriptions.items():
            prompt += f"{symbol}: {description}\n"
        prompt += (
            "\nAVAILABLE ACTIONS:\n"
            "1. Move: a single direction key\n"
            "   - w: up      s: down     a: left     d: right\n"
            "   - q: upleft  e: upright  z: downleft c: downright\n"
            "2. Shoot: 'f' followed by a direction key (e.g. 'f a' shoots left).\n"
            "   Warning: a shot that reaches a boundary or asteroid ricochets back and eliminates you,\n"
            "   so only fire when something is lined up in that direction.\n\n"
            "EXAMPLES: 'w' (move up), 'd' (move right), 'f a' (shoot left), 'f e' (shoot upright)\n\n"
            f"ARENA:\n{game_state['arena_state']}\n\n"
            "Enter your action:"
        )
        return prompt

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(
            from_id=player_id, to_id=-1,
            message=f"Player {player_id + 1} chooses: {action}",
            observation_type=ta.ObservationType.PLAYER_ACTION,
        )

        action_result = self._execute_player_action(player_id=player_id, action=action)

        if not action_result['success']:
            self.state.set_invalid_move(reason=action_result['reason'])
        else:
            self.projectiles = []  # projectiles resolve instantly inside _fire_projectile
            self.state.add_observation(
                message=f"=== Updated Arena After Player {player_id + 1}'s Move ===\n{self._get_arena_state()}",
                observation_type=ta.ObservationType.GAME_BOARD,
            )
            self._check_gameover()

        return self.state.step()

    def _execute_player_action(self, player_id: int, action: str) -> Dict[str, Any]:
        try:
            action = action.strip().lower()
            if action.startswith('[') and action.endswith(']'):  # tolerate ActionFormattingWrapper brackets
                action = action[1:-1].strip()
            direction_map = {
                'w': 'up', 's': 'down', 'a': 'left', 'd': 'right',
                'q': 'upleft', 'e': 'upright', 'z': 'downleft', 'c': 'downright',
            }

            if action in direction_map:  # Move
                direction = direction_map[action]
                steps = 1 if self.player_positions[player_id] in self.nebulas else min(1, self.player_speed[player_id])
                dx, dy = self._direction_to_delta(direction)
                new_x = self.player_positions[player_id][0] + dx * steps
                new_y = self.player_positions[player_id][1] + dy * steps
                if self._is_valid_move(new_x, new_y):
                    self.player_positions[player_id] = (new_x, new_y)
                    self._handle_collisions(player_id)
                    return {"success": True}
                return {"success": False, "reason": "Invalid move: collision or out of bounds"}

            elif action.startswith('f ') and len(action.split()) == 2:  # Shoot
                _, dir_key = action.split()
                if dir_key not in direction_map:
                    return {"success": False, "reason": "Invalid shooting direction"}
                dx, dy = self._direction_to_delta(direction_map[dir_key])
                px, py = self.player_positions[player_id]
                self._fire_projectile(player_id, px, py, dx, dy)
                if self.player_weapons[player_id] != 1 and (dx, dy) in self.directions:  # Spread shot
                    dir_index = self.directions.index((dx, dy))
                    for offset in (-1, 1):
                        ldx, ldy = self.directions[(dir_index + offset) % len(self.directions)]
                        self._fire_projectile(player_id, px, py, ldx, ldy)
                return {"success": True}

            return {"success": False, "reason": "Invalid action format. Use a direction key to move (e.g. 'w') or 'f' followed by a direction to shoot (e.g. 'f a')."}
        except Exception as e:
            return {"success": False, "reason": f"Error processing action: {str(e)}"}

    def _fire_projectile(self, player_id: int, x: int, y: int, dx: int, dy: int):
        """Fire a projectile that travels until it hits something."""
        px, py = x + dx, y + dy
        while 0 <= px < self.width and 0 <= py < self.height:
            # Boundary or asteroid (indestructible) -> ricochets back and eliminates the shooter
            if px in (0, self.width - 1) or py in (0, self.height - 1):
                self.state.add_observation(
                    message=f"Player {player_id + 1}'s projectile hit the boundary and ricocheted back, eliminating them!",
                    observation_type=ta.ObservationType.GAME_MESSAGE,
                )
                self.player_health[player_id] = 0
                break
            if (px, py) in self.asteroids:
                self.state.add_observation(
                    message=f"Player {player_id + 1}'s projectile hit an asteroid and ricocheted back, eliminating them!",
                    observation_type=ta.ObservationType.GAME_MESSAGE,
                )
                self.player_health[player_id] = 0
                break
            if (px, py) in self.debris:  # Destructible
                self.debris.remove((px, py))
                self.state.add_observation(message=f"A projectile destroyed space debris at {(px, py)}!", observation_type=ta.ObservationType.GAME_MESSAGE)
                break
            if (px, py) in self.mines:  # Destructible
                self.mines.remove((px, py))
                self.state.add_observation(message=f"A projectile detonated a mine at {(px, py)}!", observation_type=ta.ObservationType.GAME_MESSAGE)
                for i, ppos in enumerate(self.player_positions):
                    if (px, py) == ppos:
                        damage = 20 if self.player_shields[i] == 0 else 10
                        self.player_health[i] = max(0, self.player_health[i] - damage)
                        if self.player_shields[i] > 0:
                            self.player_shields[i] -= 1
                        self.state.add_observation(message=f"Player {i + 1} was hit by the mine explosion and took {damage} damage!", observation_type=ta.ObservationType.GAME_MESSAGE)
                break
            if (px, py) in self.powerups:  # Destructible
                self.powerups.remove((px, py))
                self.state.add_observation(message=f"A projectile destroyed a power-up at {(px, py)}!", observation_type=ta.ObservationType.GAME_MESSAGE)
                break
            if (px, py) in self.nebulas:  # Projectile passes through
                px += dx
                py += dy
                continue
            hit_player = False
            for i, ppos in enumerate(self.player_positions):
                if (px, py) == ppos:
                    damage = 10
                    if self.player_shields[i] > 0:
                        self.player_shields[i] -= 1
                        damage = 5
                        self.state.add_observation(message=f"Player {i + 1}'s shield absorbed some damage! {self.player_shields[i]} shield points remaining.", observation_type=ta.ObservationType.GAME_MESSAGE)
                    self.player_health[i] = max(0, self.player_health[i] - damage)
                    self.state.add_observation(message=f"Player {i + 1} was hit by a projectile and took {damage} damage! Health: {self.player_health[i]}", observation_type=ta.ObservationType.GAME_MESSAGE)
                    hit_player = True
                    break
            if hit_player:
                return
            px += dx
            py += dy

    def _direction_to_delta(self, direction: str) -> Tuple[int, int]:
        return {
            "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),
            "upleft": (-1, -1), "upright": (1, -1), "downleft": (-1, 1), "downright": (1, 1),
        }[direction]

    def _is_valid_move(self, x: int, y: int) -> bool:
        if not (0 < x < self.width - 1 and 0 < y < self.height - 1):
            return False
        if (x, y) in self.asteroids or (x, y) in self.debris:
            return False
        if (x, y) in self.player_positions:
            return False
        return True

    def _handle_collisions(self, player_id: int):
        pos = self.player_positions[player_id]
        if pos in self.powerups:
            self.powerups.remove(pos)
            self._apply_powerup(player_id)
        if pos in self.mines:
            self.mines.remove(pos)
            damage = 20 if self.player_shields[player_id] == 0 else 10
            self.player_health[player_id] = max(0, self.player_health[player_id] - damage)
            if self.player_shields[player_id] > 0:
                self.player_shields[player_id] -= 1
            self.state.add_observation(message=f"Player {player_id + 1} hit a mine and took {damage} damage!", observation_type=ta.ObservationType.GAME_MESSAGE)

    def _apply_powerup(self, player_id: int):
        powerup_type = random.choice(["shield", "speed", "weapon"])
        message = f"Player {player_id + 1} collected a "
        if powerup_type == "shield":
            self.player_shields[player_id] = 3
            message += "shield power-up! +3 shields."
        elif powerup_type == "speed":
            self.player_speed[player_id] = 2
            message += "speed power-up! Movement increased to 2 steps."
        else:
            self.player_weapons[player_id] = 2
            message += "weapon power-up! Upgraded to spread shot."
        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)

    def _check_gameover(self):
        for i, health in enumerate(self.player_health):
            if health <= 0:
                winner_id = 1 - i
                self.state.set_winner(player_id=winner_id, reason=f"Player {winner_id + 1} wins by eliminating Player {i + 1}.")
                return

        if self.state.check_turn_limit():
            if self.player_health[0] > self.player_health[1]:
                self.state.set_winner(player_id=0, reason=f"Turn limit reached. Player 1 wins with more health ({self.player_health[0]} vs {self.player_health[1]}).")
            elif self.player_health[1] > self.player_health[0]:
                self.state.set_winner(player_id=1, reason=f"Turn limit reached. Player 2 wins with more health ({self.player_health[1]} vs {self.player_health[0]}).")
            else:
                self.state.set_draw(reason=f"Turn limit reached with equal health ({self.player_health[0]} each). The duel ends in a draw.")
