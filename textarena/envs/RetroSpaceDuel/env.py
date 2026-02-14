import random
from typing import Any, Dict, Optional, Tuple, List
import numpy as np

import textarena as ta

class RetroSpaceDuelEnv(ta.Env):
    """Environment for playing Retro Space Duel, a two-player competitive space shooter."""

    def __init__(self, grid_size: Tuple[int, int] = (15, 15), max_turns: int = 100, 
                 num_asteroids: int = 5, num_debris: int = 8, num_nebulas: int = 3,
                 num_mines: int = 4, num_powerups: int = 3):
        self.grid_size = grid_size
        self.width, self.height = grid_size
        self.num_asteroids = num_asteroids
        self.num_debris = num_debris
        self.num_nebulas = num_nebulas
        self.num_mines = num_mines
        self.num_powerups = num_powerups
        
        self.state = ta.State(
            num_players=2,
            max_turns=max_turns,
            role_mapping={0: "Player 1", 1: "Player 2"}
        )
        
        self.asteroids = []
        self.debris = []
        self.nebulas = []
        self.mines = []
        self.powerups = []
        self.projectiles = []  # (x, y, dx, dy, player_id) to track who fired
        
        self.player_positions = [(1, 1), (self.width-2, self.height-2)]
        self.player_health = [100, 100]
        self.player_shields = [0, 0]
        self.player_speed = [1, 1]
        self.player_weapons = [1, 1]
        
        self.directions = [(0,-1), (1,-1), (1,0), (1,1), (0,1), (-1,1), (-1,0), (-1,-1)]
        
        # Emoji mappings
        self.empty_symbol = '  '
        self.boundary_symbol = '🌍'
        self.asteroid_symbol = '💥'  # Indestructible
        self.debris_symbol = '🟤'    # Destructible
        self.nebula_symbol = '🌪️'   # Updated nebula icon
        self.mine_symbol = '💣'      # Destructible
        self.powerup_symbol = '⚡'    # Destructible
        self.projectile_symbol = '🔥'
        self.player_symbols = {0: '🚀', 1: '🛸'}

    @property
    def offline_renderer(self):
        from textarena.envs.two_player.RetroSpaceDuel.render.renderer import RetroSpaceDuelRenderer
        return RetroSpaceDuelRenderer

    @property
    def terminal_render_keys(self):
        return ["arena_state"]

    def reset(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self.player_positions = [(1, 1), (self.width-2, self.height-2)]
        self.player_health = [100, 100]
        self.player_shields = [0, 0]
        self.player_speed = [1, 1]
        self.player_weapons = [1, 1]
        self.projectiles = []

        self._generate_game_elements()

        return self.state.reset(
            game_state={
                "arena_state": self._get_arena_state(),
                "player_health": self.player_health.copy(),
                "player_shields": self.player_shields.copy(),
                "player_speed": self.player_speed.copy(),
                "player_weapons": self.player_weapons.copy(),
                "turn": 0,
                "max_turns": self.state.max_turns
            },
            player_prompt_function=self._generate_player_prompt
        )

    def _generate_game_elements(self):
        def get_random_position(existing_positions):
            attempts = 0
            while attempts < 100:
                pos = (random.randint(1, self.width-2), random.randint(1, self.height-2))
                if pos not in existing_positions and pos not in self.player_positions:
                    return pos
                attempts += 1
            return None

        all_positions = []
        
        self.asteroids = []
        for _ in range(self.num_asteroids):
            pos = get_random_position(all_positions)
            if pos:
                self.asteroids.append(pos)
                all_positions.append(pos)
        
        self.debris = []
        for _ in range(self.num_debris):
            pos = get_random_position(all_positions)
            if pos:
                self.debris.append(pos)
                all_positions.append(pos)
        
        self.nebulas = []
        for _ in range(self.num_nebulas):
            pos = get_random_position(all_positions)
            if pos:
                self.nebulas.append(pos)
                all_positions.append(pos)
        
        self.mines = []
        for _ in range(self.num_mines):
            pos = get_random_position(all_positions)
            if pos:
                self.mines.append(pos)
                all_positions.append(pos)
        
        self.powerups = []
        for _ in range(self.num_powerups):
            pos = get_random_position(all_positions)
            if pos:
                self.powerups.append(pos)
                all_positions.append(pos)

    def _get_arena_state(self) -> str:
        grid = [[self.empty_symbol for _ in range(self.width)] for _ in range(self.height)]
        
        # Set boundaries
        for i in range(self.width):
            grid[0][i] = self.boundary_symbol
            grid[self.height-1][i] = self.boundary_symbol
        for i in range(self.height):
            grid[i][0] = self.boundary_symbol
            grid[i][self.width-1] = self.boundary_symbol
        
        # Place asteroids (indestructible)
        for x, y in self.asteroids:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.asteroid_symbol
                
        # Place debris (destructible)
        for x, y in self.debris:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.debris_symbol
                
        # Place nebulas
        for x, y in self.nebulas:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.nebula_symbol
                
        # Place mines
        for x, y in self.mines:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.mine_symbol
                
        # Place power-ups
        for x, y in self.powerups:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.powerup_symbol
        
        # Place projectiles
        for x, y, _, _, _ in self.projectiles:
            if 0 <= y < self.height and 0 <= x < self.width:
                grid[y][x] = self.projectile_symbol
        
        # Place players
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
            self.player_symbols[opponent_id]: 'Enemy spaceship'
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
            "1. Move: Use a single direction key\n"
            "   - w: up\n"
            "   - s: down\n"
            "   - a: left\n"
            "   - d: right\n"
            "   - q: upleft\n"
            "   - e: upright\n"
            "   - z: downleft\n"
            "   - c: downright\n"
            "2. Shoot: Use 'f' followed by a direction key\n"
            "   - f w: shoot up\n"
            "   - f s: shoot down\n"
            "   - f a: shoot left\n"
            "   - f d: shoot right\n"
            "   - f q: shoot upleft\n"
            "   - f e: shoot upright\n"
            "   - f z: shoot downleft\n"
            "   - f c: shoot downright\n\n"
            "EXAMPLES:\n"
            "- w (move up)\n"
            "- d (move right)\n"
            "- f a (shoot left)\n"
            "- f e (shoot upright)\n\n"
            f"ARENA:\n{game_state['arena_state']}\n\n"
            "Enter your action: "
        )
        
        return prompt

    def step(self, action: str) -> Tuple[ta.Observations, ta.Rewards, bool, bool, ta.Info]:
        """
        Process the player's action and update the game state, ensuring the board is displayed.
        
        Args:
            action (str): The player's action
        
        Returns:
            tuple: (observations, rewards, done, truncated, info)
        """
        player_id = self.state.current_player_id
        
        self.state.add_observation(
            from_id=player_id,
            to_id=-1,
            message=f"Player {player_id + 1} chooses: {action}",
            for_logging=True
        )

        action_result = self._execute_player_action(
            player_id=player_id,
            action=action
        )
        
        if not action_result['success']:
            self.state.add_observation(
                from_id=-1,
                to_id=player_id,
                message=f"Invalid action: {action_result['reason']}. Please try again with a valid command.",
                for_logging=True
            )
            self.state.set_invalid_move(
                player_ids=[player_id],
                reasons=[action_result['reason']]
            )
        else:
            self._update_game_state()
            
            self.state.add_observation(
                from_id=-1,
                to_id=-1,
                message=f"\n=== Updated Arena After Player {player_id + 1}'s Move ===\n{self.state.game_state['arena_state']}\n",
                for_logging=True
            )
            
            self._check_gameover()

        return self.state.step()

    def _execute_player_action(self, player_id: int, action: str) -> Dict[str, Any]:
        result = {"success": False, "reason": "Could not understand action"}
        
        try:
            action = action.lower().strip()
            
            # Simplified input mapping
            direction_map = {
                'w': 'up',
                's': 'down',
                'a': 'left',
                'd': 'right',
                'q': 'upleft',
                'e': 'upright',
                'z': 'downleft',
                'c': 'downright'
            }
            
            # Check if it's a move or shoot action
            if action in direction_map:  # Move action
                direction = direction_map[action]
                steps = 1
                if self.player_positions[player_id] in self.nebulas:
                    steps = min(steps, 1)
                else:
                    steps = min(steps, self.player_speed[player_id])
                
                dx, dy = self._direction_to_delta(direction)
                if dx is None or dy is None:
                    return {"success": False, "reason": "Invalid direction"}
                
                new_x = self.player_positions[player_id][0] + dx * steps
                new_y = self.player_positions[player_id][1] + dy * steps
                
                if self._is_valid_move(new_x, new_y):
                    self.player_positions[player_id] = (new_x, new_y)
                    self._handle_collisions(player_id)
                    return {"success": True}
                else:
                    return {"success": False, "reason": "Invalid move: collision or out of bounds"}
            
            elif action.startswith('f ') and len(action.split()) == 2:  # Shoot action
                _, dir_key = action.split()
                if dir_key not in direction_map:
                    return {"success": False, "reason": "Invalid shooting direction"}
                
                direction = direction_map[dir_key]
                dx, dy = self._direction_to_delta(direction)
                if dx is None or dy is None:
                    return {"success": False, "reason": "Invalid direction"}
                
                px, py = self.player_positions[player_id]
                
                if self.player_weapons[player_id] == 1:  # Normal shot
                    self._fire_projectile(player_id, px, py, dx, dy)
                else:  # Spread shot
                    self._fire_projectile(player_id, px, py, dx, dy)
                    dir_index = self.directions.index((dx, dy)) if (dx, dy) in self.directions else -1
                    if dir_index != -1:
                        left_index = (dir_index - 1) % len(self.directions)
                        right_index = (dir_index + 1) % len(self.directions)
                        left_dx, left_dy = self.directions[left_index]
                        right_dx, right_dy = self.directions[right_index]
                        self._fire_projectile(player_id, px, py, left_dx, left_dy)
                        self._fire_projectile(player_id, px, py, right_dx, right_dy)
                
                return {"success": True}
            else:
                return {"success": False, "reason": "Invalid action format. Use a direction key to move (e.g., 'w') or 'f' followed by a direction to shoot (e.g., 'f a')."}

        except Exception as e:
            return {"success": False, "reason": f"Error processing action: {str(e)}"}

    def _fire_projectile(self, player_id: int, x: int, y: int, dx: int, dy: int):
        """Fire a projectile that travels all the way until it hits something."""
        px, py = x + dx, y + dy
        
        while 0 <= px < self.width and 0 <= py < self.height:
            # Check for boundary (indestructible, causes ricochet)
            if (px, py) in [(i, 0) for i in range(self.width)] or \
               (px, py) in [(i, self.height-1) for i in range(self.width)] or \
               (px, py) in [(0, i) for i in range(self.height)] or \
               (px, py) in [(self.width-1, i) for i in range(self.height)]:
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Player {player_id + 1}'s projectile hit the boundary and ricocheted back, eliminating them!",
                    for_logging=True
                )
                self.player_health[player_id] = 0
                break
            
            # Check for asteroid (indestructible, causes ricochet)
            if (px, py) in self.asteroids:
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Player {player_id + 1}'s projectile hit an asteroid and ricocheted back, eliminating them!",
                    for_logging=True
                )
                self.player_health[player_id] = 0
                break
            
            # Check for debris (destructible, gets removed)
            if (px, py) in self.debris:
                self.debris.remove((px, py))
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"A projectile destroyed space debris at {px, py}!",
                    for_logging=True
                )
                break
            
            # Check for mines (destructible, gets removed but causes damage if player is nearby)
            if (px, py) in self.mines:
                self.mines.remove((px, py))
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"A projectile detonated a mine at {px, py}!",
                    for_logging=True
                )
                # Check if any player is at the mine's position (unlikely since projectile moves instantly)
                for i, (px_player, py_player) in enumerate(self.player_positions):
                    if (px, py) == (px_player, py_player):
                        damage = 20 if self.player_shields[i] == 0 else 10
                        self.player_health[i] = max(0, self.player_health[i] - damage)
                        if self.player_shields[i] > 0:
                            self.player_shields[i] -= 1
                        self.state.add_observation(
                            from_id=-1,
                            to_id=-1,
                            message=f"Player {i + 1} was hit by the mine explosion and took {damage} damage!",
                            for_logging=True
                        )
                break
            
            # Check for power-ups (destructible, gets removed)
            if (px, py) in self.powerups:
                self.powerups.remove((px, py))
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"A projectile destroyed a power-up at {px, py}!",
                    for_logging=True
                )
                break
            
            # Check for nebulas (neither indestructible nor destructible, projectile passes through)
            if (px, py) in self.nebulas:
                px += dx
                py += dy
                continue
            
            # Check for players
            for i, (px_player, py_player) in enumerate(self.player_positions):
                if (px, py) == (px_player, py_player):
                    damage = 10
                    if self.player_shields[i] > 0:
                        self.player_shields[i] -= 1
                        damage = 5
                        self.state.add_observation(
                            from_id=-1,
                            to_id=-1,
                            message=f"Player {i + 1}'s shield absorbed some damage! {self.player_shields[i]} shield points remaining.",
                            for_logging=True
                        )
                    self.player_health[i] = max(0, self.player_health[i] - damage)
                    self.state.add_observation(
                        from_id=-1,
                        to_id=-1,
                        message=f"Player {i + 1} was hit by a projectile and took {damage} damage! Health: {self.player_health[i]}",
                        for_logging=True
                    )
                    return  # Stop projectile after hitting a player
            
            # If nothing is hit, continue moving
            px += dx
            py += dy

    def _extract_direction(self, action: str) -> Optional[str]:
        # Not used anymore due to simplified inputs, but kept for compatibility
        if ("up" in action or "north" in action) and ("right" in action or "east" in action):
            return "upright"
        elif ("up" in action or "north" in action) and ("left" in action or "west" in action):
            return "upleft"
        elif ("down" in action or "south" in action) and ("right" in action or "east" in action):
            return "downright"
        elif ("down" in action or "south" in action) and ("left" in action or "west" in action):
            return "downleft"
        elif "up" in action or "north" in action:
            return "up"
        elif "down" in action or "south" in action:
            return "down"
        elif "left" in action or "west" in action:
            return "left"
        elif "right" in action or "east" in action:
            return "right"
        elif "diagonal" in action:
            if "up" in action and "right" in action:
                return "upright"
            elif "up" in action and "left" in action:
                return "upleft"
            elif "down" in action and "right" in action:
                return "downright"
            elif "down" in action and "left" in action:
                return "downleft"
        return None

    def _direction_to_delta(self, direction: str) -> Tuple[Optional[int], Optional[int]]:
        direction_map = {
            "up": (0, -1),
            "down": (0, 1),
            "left": (-1, 0),
            "right": (1, 0),
            "upleft": (-1, -1),
            "upright": (1, -1),
            "downleft": (-1, 1),
            "downright": (1, 1)
        }
        return direction_map.get(direction, (None, None))

    def _is_valid_move(self, x: int, y: int) -> bool:
        if not (0 < x < self.width-1 and 0 < y < self.height-1):
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
            
            self.state.add_observation(
                from_id=-1,
                to_id=-1,
                message=f"Player {player_id + 1} hit a mine and took {damage} damage!",
                for_logging=True
            )

    def _apply_powerup(self, player_id: int):
        powerup_type = random.choice(["shield", "speed", "weapon"])
        
        powerup_message = f"Player {player_id + 1} collected a "
        
        if powerup_type == "shield":
            self.player_shields[player_id] = 3
            powerup_message += "shield power-up! +3 shields."
        elif powerup_type == "speed":
            self.player_speed[player_id] = 2
            powerup_message += "speed power-up! Movement increased to 2 steps."
        elif powerup_type == "weapon":
            self.player_weapons[player_id] = 2
            powerup_message += "weapon power-up! Upgraded to spread shot."
        
        self.state.add_observation(
            from_id=-1,
            to_id=-1,
            message=powerup_message,
            for_logging=True
        )

    def _update_game_state(self):
        # Projectiles now move instantly via _fire_projectile, so we don't need to update them here
        self.projectiles = []  # Clear projectiles since they move instantly

        self.state.game_state.update({
            "arena_state": self._get_arena_state(),
            "player_health": self.player_health.copy(),
            "player_shields": self.player_shields.copy(),
            "player_speed": self.player_speed.copy(),
            "player_weapons": self.player_weapons.copy(),
            "turn": self.state.turn,
            "max_turns": self.state.max_turns
        })

    def _check_gameover(self):
        for i, health in enumerate(self.player_health):
            if health <= 0:
                winner_id = 1 - i
                
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Player {i + 1} has been eliminated! Player {winner_id + 1} wins!",
                    for_logging=True
                )
                
                self.state.set_winners(
                    player_ids=[winner_id],
                    reason=f"Player {winner_id + 1} wins by eliminating Player {i + 1}"
                )
                return

        if self.state.turn >= self.state.max_turns - 1:
            if self.player_health[0] > self.player_health[1]:
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Maximum turns reached! Player 1 wins with {self.player_health[0]} health vs Player 2's {self.player_health[1]}!",
                    for_logging=True
                )
                
                self.state.set_winners(
                    player_ids=[0],
                    reason="Player 1 wins by having more health when turns expired"
                )
            elif self.player_health[1] > self.player_health[0]:
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Maximum turns reached! Player 2 wins with {self.player_health[1]} health vs Player 1's {self.player_health[0]}!",
                    for_logging=True
                )
                
                self.state.set_winners(
                    player_ids=[1],
                    reason="Player 2 wins by having more health when turns expired"
                )
            else:
                self.state.add_observation(
                    from_id=-1,
                    to_id=-1,
                    message=f"Maximum turns reached! The game ends in a draw with both players at {self.player_health[0]} health!",
                    for_logging=True
                )
                
                self.state.set_draw(
                    reason="Game ended in a draw - equal health when turns expired"
                )
