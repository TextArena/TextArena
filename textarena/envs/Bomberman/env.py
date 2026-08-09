import re, random
from typing import Any, Dict, Optional, Tuple, List

import textarena as ta


class TwoPlayerBombermanEnv(ta.Env):
    """Environment for a turn-based two-player adaptation of Bomberman."""

    def __init__(self, grid_size: int = 10, max_turns: int = 100,
                 bomb_timer: int = 6, bomb_radius: int = 2, wall_density: float = 0.3):
        """
        Args:
            grid_size (int): Size of the square grid arena.
            max_turns (int): Maximum number of rounds (both players move each round) before a draw.
            bomb_timer (int): Number of half-turns before a bomb explodes.
            bomb_radius (int): Radius of bomb explosions.
            wall_density (float): Density of destructible walls (0.0 to 1.0).
        """
        self.grid_size = grid_size
        self.max_turns = max_turns
        self.bomb_timer = bomb_timer
        self.bomb_radius = bomb_radius
        self.wall_density = wall_density

        # Grid element glyphs
        self.EMPTY = " "
        self.INDESTRUCTIBLE_WALL = "#"
        self.DESTRUCTIBLE_WALL = "+"
        self.PLAYER_SYMBOLS = ["1", "2"]
        self.BOMB = "B"
        self.EXPLOSION = "*"

        self.move_pattern = re.compile(r"\[(up|down|left|right|stay|bomb)\]", re.IGNORECASE)

    def get_board_str(self) -> str:
        return self._generate_board_string()

    def reset(self, num_players: int, seed: Optional[int] = None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed, max_turns=None)

        self.current_turn = 0
        self.bombs = []       # [x, y, timer]
        self.explosions = []  # [x, y, timer]

        self._initialize_grid()
        self.player_positions = [[1, 1], [self.grid_size - 2, self.grid_size - 2]]

        # Clear a pocket around each spawn so both players can actually stand and move.
        for px, py in self.player_positions:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    x, y = px + dx, py + dy
                    if 0 <= x < self.grid_size and 0 <= y < self.grid_size:
                        if self.grid[y][x] == self.DESTRUCTIBLE_WALL:
                            self.grid[y][x] = self.EMPTY
            self.grid[py][px] = self.EMPTY  # spawn cell may be an indestructible pillar; force it clear

        game_state = {
            "current_board": self._generate_board_string(),
            "valid_moves": "Valid moves: [up], [down], [left], [right], [stay], [bomb]",
            "turn_info": f"Turn: 0/{self.max_turns}",
        }
        self.state.reset(
            game_state=game_state,
            player_prompt_function=self._generate_player_prompt,
            role_mapping={0: "Player 1", 1: "Player 2"},
        )
        self.state.add_observation(message=self._generate_board_string(), observation_type=ta.ObservationType.GAME_BOARD)

    def _initialize_grid(self):
        self.grid = [[self.EMPTY for _ in range(self.grid_size)] for _ in range(self.grid_size)]
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if (i == 0 or i == self.grid_size - 1 or j == 0 or j == self.grid_size - 1 or
                        (i % 2 == 0 and j % 2 == 0)):
                    self.grid[i][j] = self.INDESTRUCTIBLE_WALL
        for i in range(1, self.grid_size - 1):
            for j in range(1, self.grid_size - 1):
                if self.grid[i][j] == self.EMPTY and random.random() < self.wall_density:
                    self.grid[i][j] = self.DESTRUCTIBLE_WALL

    def _generate_board_string(self) -> str:
        render_grid = [row[:] for row in self.grid]
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if render_grid[i][j] in self.PLAYER_SYMBOLS:
                    render_grid[i][j] = self.EMPTY
        for x, y, _ in self.bombs:
            render_grid[y][x] = self.BOMB
        for x, y, _ in self.explosions:
            render_grid[y][x] = self.EXPLOSION
        for i, pos in enumerate(self.player_positions):
            if pos is not None:
                render_grid[pos[1]][pos[0]] = self.PLAYER_SYMBOLS[i]

        board_str = "+" + "-" * self.grid_size * 2 + "+\n"
        for row in render_grid:
            board_str += "|" + "".join(cell + " " for cell in row) + "|\n"
        board_str += "+" + "-" * self.grid_size * 2 + "+"
        return board_str

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        player_name = self.PLAYER_SYMBOLS[player_id]
        prompt = (
            f"You are Player {player_name} in a turn-based Bomberman game.\n"
            "Make your move using one of these commands (in square brackets):\n"
            "[up] / [down] / [left] / [right] - move one cell\n"
            "[stay] - stay in place\n"
            "[bomb] - place a bomb at your current position\n"
            f"Bombs explode after {self.bomb_timer} half-turns (about {self.bomb_timer // 2} of your own turns) "
            f"with a blast radius of {self.bomb_radius}. Destructible walls (+) block and are destroyed by blasts; "
            "indestructible walls (#) block everything.\n\n"
            "You may include extra text, but mention the move command only once.\n\n"
            f"Current board state:\n{game_state['current_board']}\n\n"
            f"{game_state['turn_info']}\n\n"
            "Legend:\n"
            f"{self.PLAYER_SYMBOLS[0]} - Player 1\n"
            f"{self.PLAYER_SYMBOLS[1]} - Player 2\n"
            f"{self.INDESTRUCTIBLE_WALL} - Indestructible wall\n"
            f"{self.DESTRUCTIBLE_WALL} - Destructible wall\n"
            f"{self.BOMB} - Bomb\n"
            f"{self.EXPLOSION} - Explosion\n\n"
            f"{game_state['valid_moves']}"
        )
        return prompt

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        if not self._execute_player_move(player_id=player_id, action=action):
            return self.state.step()  # invalid move already recorded

        self._update_bombs_and_explosions()

        if player_id == 1:  # a full round has completed
            self.current_turn += 1
            self.state.game_state["turn_info"] = f"Turn: {self.current_turn}/{self.max_turns}"
            if self.current_turn >= self.max_turns:
                alive = [i for i, p in enumerate(self.player_positions) if p is not None]
                if len(alive) > 1:
                    self.state.set_draw(reason=f"Maximum turns ({self.max_turns}) reached. The game ends in a draw.")

        self._check_gameover()

        self.state.game_state["current_board"] = self._generate_board_string()
        self.state.add_observation(message=self._generate_board_string(), observation_type=ta.ObservationType.GAME_BOARD)
        return self.state.step()

    def _execute_player_move(self, player_id: int, action: str) -> bool:
        match = self.move_pattern.search(action.strip())
        if match is None:
            self.state.set_invalid_move(reason=f"Player {player_id + 1} did not provide a valid move, e.g. [up] or [bomb].")
            return False

        if self.player_positions[player_id] is None:
            self.state.set_invalid_move(reason=f"Player {player_id + 1} has been eliminated and cannot move.")
            return False

        move = match.group(1).lower()
        x, y = self.player_positions[player_id]

        if move == "bomb":
            if any(b[0] == x and b[1] == y for b in self.bombs):
                self.state.set_invalid_move(reason=f"Player {player_id + 1} tried to place a bomb where one already exists.")
                return False
            self.bombs.append([x, y, self.bomb_timer])
            self.state.add_observation(message=f"Player {player_id + 1} placed a bomb at ({x}, {y}).", observation_type=ta.ObservationType.GAME_MESSAGE)
            return True

        deltas = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0), "stay": (0, 0)}
        dx, dy = deltas[move]
        new_x, new_y = x + dx, y + dy

        if move == "stay":
            self.state.add_observation(message=f"Player {player_id + 1} stayed in place.", observation_type=ta.ObservationType.GAME_MESSAGE)
            return True

        if not (0 <= new_x < self.grid_size and 0 <= new_y < self.grid_size):
            self.state.set_invalid_move(reason=f"Player {player_id + 1} tried to move {move} but hit the boundary.")
            return False
        if self.grid[new_y][new_x] in (self.INDESTRUCTIBLE_WALL, self.DESTRUCTIBLE_WALL):
            self.state.set_invalid_move(reason=f"Player {player_id + 1} tried to move {move} but hit a wall.")
            return False
        if any(b[0] == new_x and b[1] == new_y for b in self.bombs):
            self.state.set_invalid_move(reason=f"Player {player_id + 1} tried to move {move} but a bomb is there.")
            return False
        if any(p is not None and p[0] == new_x and p[1] == new_y for i, p in enumerate(self.player_positions) if i != player_id):
            self.state.set_invalid_move(reason=f"Player {player_id + 1} tried to move {move} but the other player is there.")
            return False

        self.player_positions[player_id] = [new_x, new_y]
        self.state.add_observation(message=f"Player {player_id + 1} moved {move} to ({new_x}, {new_y}).", observation_type=ta.ObservationType.GAME_MESSAGE)
        return True

    def _update_bombs_and_explosions(self):
        self.explosions = [[x, y, t - 1] for x, y, t in self.explosions if t > 1]
        new_bombs = []
        for x, y, timer in self.bombs:
            if timer > 1:
                new_bombs.append([x, y, timer - 1])
            else:
                self._create_explosion(x, y)
                self.state.add_observation(message=f"Bomb at ({x}, {y}) exploded!", observation_type=ta.ObservationType.GAME_MESSAGE)
        self.bombs = new_bombs

    def _create_explosion(self, bomb_x: int, bomb_y: int):
        self._add_explosion_cell(bomb_x, bomb_y)
        for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
            for r in range(1, self.bomb_radius + 1):
                x, y = bomb_x + dx * r, bomb_y + dy * r
                if not (0 <= x < self.grid_size and 0 <= y < self.grid_size):
                    break
                if self.grid[y][x] == self.INDESTRUCTIBLE_WALL:
                    break
                self._add_explosion_cell(x, y)
                if self.grid[y][x] == self.DESTRUCTIBLE_WALL:
                    self.grid[y][x] = self.EMPTY  # destroy the wall; blast stops here
                    break

    def _add_explosion_cell(self, x: int, y: int):
        self.explosions.append([x, y, 2])  # visible for 2 half-turns
        for player_id, pos in enumerate(self.player_positions):
            if pos is not None and pos[0] == x and pos[1] == y:
                self.player_positions[player_id] = None
                self.state.add_observation(message=f"Player {player_id + 1} was caught in an explosion and eliminated!", observation_type=ta.ObservationType.GAME_MESSAGE)

    def _check_gameover(self):
        if self.state.done:
            return
        alive = [i for i, pos in enumerate(self.player_positions) if pos is not None]
        if len(alive) == 0:
            self.state.set_draw(reason="Both players were eliminated in the same blast. The game ends in a draw.")
        elif len(alive) == 1:
            winner_id = alive[0]
            self.state.set_winner(player_id=winner_id, reason=f"Player {winner_id + 1} wins - the other player was eliminated.")
