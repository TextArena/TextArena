import re, random
from typing import Optional, Tuple, List, Dict, Any

import textarena as ta
from textarena.envs.Battleship.renderer import create_board_str

class BattleshipEnv(ta.Env):
    def __init__(self, grid_size: Optional[int] = 10):
        """
        Args:
            grid_size (int): Grid size
        """
        self.grid_size = grid_size
        self.ships = {"Aircraft Carrier": 5, "Battleship": 4, "Submarine": 3, "Destroyer": 3, "Patrol Boat": 2}

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def reset(self, num_players: int, seed: Optional[int]=None):
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        board, tracking_board, ship_placements = self._generate_board()
        game_state={"board": board, "tracking_board": tracking_board, "ship_placements": ship_placements} #, "rendered_board": self._render_board()}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()  # Observe the initial state of the game
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("player_prompt", "intro", player_id=player_id)

    def _generate_board(self) -> List[List[str]]:
        """ Generate a new grid, tracking grid, and place ships on the grid for both players, where each entity is a dictionary with the player_ids as the keys """
        board = {0: [['~'] * self.grid_size for _ in range(self.grid_size)], 1: [['~'] * self.grid_size for _ in range(self.grid_size)]}
        tracking_board = {0: [['~'] * self.grid_size for _ in range(self.grid_size)], 1: [['~'] * self.grid_size for _ in range(self.grid_size)]}
        ship_placements = {0: {}, 1: {}}
        ## place ships on the board for both players
        for player_id in range(2):
            for ship_name, length in self.ships.items():
                placement = self._place_ship_on_board(board[player_id], ship_name, length)
                ship_placements[player_id][ship_name] = placement
        return board, tracking_board, ship_placements
    
    def _place_ship_on_board(self, grid: List[List[str]], ship_name: str, length: int) -> List[Tuple[Tuple[int, int], str]]:
        """ Place a ship on the board in one of four directions: right, left, down, or up """
        placed = False; directions = ["right", "left", "down", "up"]
        while not placed:
            direction = random.choice(directions)
            if direction == "right":  # →
                row, col = random.randint(0, self.grid_size - 1), random.randint(0, self.grid_size - length)
                if all(grid[row][col + i] == '~' for i in range(length)):
                    for i in range(length):
                        grid[row][col + i] = ship_name[0]
                        if i == 0:
                            placement = [(row, col),(row, col + length - 1)]
                    placed = True

            elif direction == "left":  # ←
                row, col = random.randint(0, self.grid_size - 1), random.randint(length - 1, self.grid_size - 1)
                if all(grid[row][col - i] == '~' for i in range(length)):
                    for i in range(length):
                        grid[row][col - i] = ship_name[0]
                        if i == 0:
                            placement = [(row, col),(row, col - length + 1)]
                    placed = True

            elif direction == "down":  # ↓
                row, col = random.randint(0, self.grid_size - length), random.randint(0, self.grid_size - 1)
                if all(grid[row + i][col] == '~' for i in range(length)):
                    for i in range(length):
                        grid[row + i][col] = ship_name[0]
                        if i == 0:
                            placement = [(row, col),(row + length - 1, col)]
                    placed = True

            elif direction == "up":  # ↑
                row, col = random.randint(length - 1, self.grid_size - 1), random.randint(0, self.grid_size - 1)
                if all(grid[row - i][col] == '~' for i in range(length)):
                    for i in range(length):
                        grid[row - i][col] = ship_name[0]
                        if i == 0:
                            placement = [(row, col),(row - length + 1, col)]
                    placed = True
        return placement

    def _render_board(self) -> str:
        # Prepare header for both players and column numbers
        view = []
        view.append("   " + "Player 0's Ships".center(self.grid_size * 3) + "        " + "Player 1's Ships".center(self.grid_size * 3))
        view.append("   " + " ".join([f"{i:2}" for i in range(self.grid_size)]) + "      " + "   " + " ".join([f"{i:2}" for i in range(self.grid_size)]))
        for i in range(self.grid_size):
            # Row labels (letters) and grid display for both players' grids
            row_label = chr(i + ord('A'))
            row_player1 = " ".join(f"{cell:2}" for cell in self.state.game_state['board'][0][i])
            row_player2 = " ".join(f"{cell:2}" for cell in self.state.game_state['board'][1][i])
            view.append(f"{row_label}   {row_player1}     {row_label}   {row_player2}")
        return "\n".join(view)
    
    def _observe_current_state(self) -> None:
        """ Observe the current state of the game and update the rendered board """
        
        # Generate the player's view of the game
        player_id = self.state.current_player_id
        player_view = self._render_player_view(player_id)
        
        # Add observation for the player
        self.state.add_observation(from_id=-1, to_id=player_id, message=f"{player_view}", observation_type=ta.ObservationType.GAME_BOARD)
    
    def _render_player_view(self, player_id: int) -> str:
        """ Render the player's view of the game. """
        # Determine which player's view to return
        if player_id == 0:
            own_grid = self.state.game_state['board'][0]
            tracking_grid = self.state.game_state['tracking_board'][0]
            player_label = "Player 0"
        else:
            own_grid = self.state.game_state['board'][1]
            tracking_grid = self.state.game_state['tracking_board'][1]
            player_label = "Player 1"
        
        # Prepare header with Player ID and column numbers
        view = []
        view.append(f"\n{player_label}'s View".center(self.grid_size * 4 + 15))
        view.append("   " + "Your Ships".center(self.grid_size * 3) + "        " + "Your Hits on Opponent".center(self.grid_size * 3))
        view.append("   " + " ".join([f"{i:2}" for i in range(self.grid_size)]) + "      " + "   " + " ".join([f"{i:2}" for i in range(self.grid_size)]))
        
        for i in range(self.grid_size):
            # Row labels (letters) and grid display for both player's ships and tracking grid
            row_label = chr(i + ord('A'))
            row_own_grid = " ".join(f"{cell:2}" for cell in own_grid[i])
            row_tracking_grid = " ".join(f"{cell:2}" for cell in tracking_grid[i])
            view.append(f"{row_label}   {row_own_grid}     {row_label}   {row_tracking_grid}")
        
        return "\n".join(view) # Join all lines into a single string with newlines
    
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        match = re.compile(r"\[([A-Z])(\d+)\]", re.IGNORECASE).search(action)

        if match is None:
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format"))
        
        else:
            row = ord(match.group(1).upper()) - ord('A') # convert letter to row index
            col = int(match.group(2))
            
            opponent_id = 1 - player_id
            opponent_board = self.state.game_state['board'][opponent_id]
            tracking_board = self.state.game_state['tracking_board'][player_id]

            ## check if the move is valid
            if row < 0 or row >= self.grid_size or col < 0 or col >= self.grid_size:
                self.state.set_invalid_move(reason=self.m("invalid_move", "out_of_board", coord=match.group()[1:3]))
            elif tracking_board[row][col] != '~':
                self.state.set_invalid_move(reason=self.m("invalid_move", "already_fired", coord=match.group()[1:3]))
            else:
                if opponent_board[row][col] != '~':
                    tracking_board[row][col] = 'X'
                    ship_initial = opponent_board[row][col]
                    opponent_board[row][col] = 'X'
                    if not any(ship_initial in row for row in opponent_board):
                        self.state.add_observation(to_id=player_id, message=self.m("game_action", "you_sunk", coord=match.group()[1:3], view=self._render_player_view(player_id=player_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                        self.state.add_observation(to_id=opponent_id, message=self.m("game_action", "opp_sunk", coord=match.group()[1:3], view=self._render_player_view(player_id=opponent_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    else:
                        self.state.add_observation(to_id=player_id, message=self.m("game_action", "you_hit", coord=match.group()[1:3], view=self._render_player_view(player_id=player_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                        self.state.add_observation(to_id=opponent_id, message=self.m("game_action", "opp_hit", coord=match.group()[1:3], view=self._render_player_view(player_id=opponent_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                else:
                    tracking_board[row][col] = 'O'; opponent_board[row][col] = 'O'
                    self.state.add_observation(to_id=player_id, message=self.m("game_action", "you_miss", coord=match.group()[1:3], view=self._render_player_view(player_id=player_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    self.state.add_observation(to_id=opponent_id, message=self.m("game_action", "opp_miss", coord=match.group()[1:3], view=self._render_player_view(player_id=opponent_id)), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
            
            ## check if the game is over
            if self._check_win(player_id):
                self.state.set_winner(player_id=player_id, reason=self.m("outcome", "win", player_id=player_id))

        ## update the rendered board
        # self.state.game_state["rendered_board"] = self._render_board()

        return self.state.step()
    
    def _check_win(self, player_id: int) -> bool:
        """ Check if the game is over """
        opponent_board = self.state.game_state['board'][1 - player_id]
        abbreviations = {name[0] for name in self.ships.keys()}
        return not any(any(cell in abbreviations for cell in row) for row in opponent_board)