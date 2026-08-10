import re, random
from typing import Any, Dict, List, Tuple, Optional, Union, Literal

import textarena as ta
from textarena.envs.FifteenPuzzle.renderer import create_board_str

class FifteenPuzzleEnv(ta.Env):
    """ Fifteen Puzzle environment """
    _DIFFICULTY_MOVES = {"easy": (1, 5), "medium": (6, 10), "hard": (11, 20)}

    def __init__(self, max_turns: int = 50, difficulty: Optional[Literal["easy", "medium", "hard"]] = None):
        """ Initialize the Fifteen Puzzle environment.

        difficulty: when set, the board is scrambled a bounded number of slides from the
        solved layout (easy/medium/hard); when None, a fully shuffled solvable board is used.
        """
        super().__init__()
        if difficulty is not None and difficulty not in self._DIFFICULTY_MOVES:
            raise ValueError(f"difficulty must be one of {sorted(self._DIFFICULTY_MOVES)} or None, got {difficulty!r}")
        self.max_turns = max_turns
        self.difficulty = difficulty

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)
    
    def reset(self, num_players: int, seed: Optional[int] = None):
        """ Reset the environment to its initial state """
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns) ## initialize the game state
        self.board = self._generate_board() ## initialize the game state
        self.initial_board = [row[:] for row in self.board]  # Deep copy of the initial board
        game_state = {"board": self.board, "rendered_board": self._render_board(self.board)} ## reset the game state
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state()  # Observe the initial state of the game

    def _observe_current_state(self) -> None:
        """Send current board and legal moves as observation."""
        r, c = self._get_empty_position()
        moves = {"[up]": r < 3, "[down]": r > 0, "[left]": c < 3, "[right]": c > 0}
        legal_moves = [m for m, valid in moves.items() if valid]
        msg = f"Current Board:\n\n{self.state.game_state['rendered_board']}\nAvailable Moves: {', '.join(legal_moves)}"
        self.state.add_observation(message=msg, observation_type=ta.ObservationType.GAME_BOARD)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return (
            f"You are Player {player_id}. You are playing the 15-Puzzle game.\n"
            "The objective of the game is to arrange the numbered tiles in ascending order from 1 to 15, with the empty space located in the bottom-right corner.\n"
            "To make a move, you can slide a tile into the empty space (represented by a double underscore, e.g. __) by using one of the following commands:\n"
            "- 'up': Move the tile below the empty space up.\n"
            "- 'down': Move the tile above the empty space down.\n"
            "- 'left': Move the tile to the right of the empty space left.\n"
            "- 'right': Move the tile to the left of the empty space right.\n"
            "To submit your move, type the direction (e.g., 'up', 'down', 'left', or 'right') in square brackets, e.g. [up].\n"
            "The current board layout is shown below. Use the information to solve the puzzle.\n"
        )
    
    def _generate_board(self):
        """ Generate a solvable board configuration. With a difficulty set the board is
        scrambled a bounded number of slides from solved (solvable by construction);
        otherwise it is fully shuffled and repaired to a solvable layout. """
        if self.difficulty is not None:
            return self._scramble_from_solved(random.randint(*self._DIFFICULTY_MOVES[self.difficulty]))
        tiles = list(range(1, 16)) + [None]
        random.shuffle(tiles)
        if not self._is_solvable(tiles):
            # A single transposition of two non-blank tiles flips the inversion
            # parity (and leaves the blank's row untouched), turning an
            # unsolvable layout into a solvable one.
            i, j = [k for k, t in enumerate(tiles) if t is not None][:2]
            tiles[i], tiles[j] = tiles[j], tiles[i]
        return [tiles[i:i + 4] for i in range(0, 16, 4)] # e.g. [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, None]]

    def _scramble_from_solved(self, n_moves: int) -> List[List[Optional[int]]]:
        """ Slide the blank `n_moves` times from the solved layout. The result is always
        solvable, and its distance from solved scales with n_moves (i.e. with difficulty). """
        tiles = list(range(1, 16)) + [None]
        board = [tiles[i:i + 4] for i in range(0, 16, 4)]
        r, c = 3, 3  # the blank starts in the bottom-right corner
        previous = None  # avoid immediately sliding the blank back where it came from
        for _ in range(n_moves):
            neighbors = [(nr, nc) for nr, nc in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)) if 0 <= nr < 4 and 0 <= nc < 4]
            if previous is not None and len(neighbors) > 1:
                neighbors.remove(previous)
            nr, nc = random.choice(neighbors)
            board[r][c], board[nr][nc] = board[nr][nc], board[r][c]
            previous = (r, c)
            r, c = nr, nc
        return board

    def _is_solvable(self, tiles: List[Optional[int]]) -> bool:
        """ A 4-wide sliding puzzle is solvable iff the blank sits on an
        even row counting from the bottom with an odd inversion count, or on an
        odd row from the bottom with an even inversion count. """
        values = [t for t in tiles if t is not None]
        inversions = sum(
            1
            for i in range(len(values))
            for j in range(i + 1, len(values))
            if values[i] > values[j]
        )
        blank_row_from_bottom = 4 - (tiles.index(None) // 4)
        if blank_row_from_bottom % 2 == 0:
            return inversions % 2 == 1
        return inversions % 2 == 0

    def _render_board(self, board):
        """ Render the current board layout """
        rendered_board = ""
        for row in board:
            rendered_board += ' '.join(['__' if x is None else f"{x:2}" for x in row]) + "\n"
        return rendered_board
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """ Process the player's action and update the environment state """
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION) ## add the action to the game state
        action_search_pattern = re.compile(r"\[([a-zA-Z]+)\]") # e.g. [up]
        match = action_search_pattern.search(action)

        if match is None:
            reason=f"Invalid move format. Player {player_id} did not respond with a valid direction in square brackets."
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=reason)

        else:
            direction = match.group(1)
            if not self._move(direction):
                reason=f"Invalid move. The tile cannot be moved in the specified direction."
                self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=reason)

            else:
                self.state.game_state["rendered_board"] = self._render_board(self.board) ## update the rendered board
                message=f"Game Board:\n{self._render_board(self.board)}"
                self.state.add_observation(from_id=-1, to_id=player_id, message=message, observation_type=ta.ObservationType.GAME_BOARD)
            
        if self._is_solved(): ## check if the puzzle is solved
            reason=f"Congratulations! Player {player_id} have successfully solved the 15-Puzzle."
            self.state.set_winners(player_ids=[player_id], reason=reason)
        elif self.state.check_turn_limit():
            pct_completion = self._get_percentage_completion()
            reason=f"The turn limit has been reached. The model completed {pct_completion*100} percent of the puzzle"
            self.state.set_outcome(reward=pct_completion, reason=reason)
        self._observe_current_state()  # Observe the new state after the move
        return self.state.step()
    
    def _is_solved(self) -> bool:
        """ Check if the board is in a solved state """
        correct_tiles = list(range(1, 16)) + [None]
        current_tiles = [tile for row in self.board for tile in row]
        return current_tiles == correct_tiles

    def _move(self, direction: str) -> bool:
        """ Move a tile into the empty space if the direction is valid """
        empty_row, empty_col = self._get_empty_position()
        target_row, target_col = empty_row, empty_col

        if direction == 'up' and empty_row < 3:         target_row += 1
        elif direction == 'down' and empty_row > 0:     target_row -= 1
        elif direction == 'left' and empty_col < 3:     target_col += 1
        elif direction == 'right' and empty_col > 0:    target_col -= 1
        else:                                           return False ## invalid move

        ## swap the target tile with the empty tile
        self.board[empty_row][empty_col], self.board[target_row][target_col] = (self.board[target_row][target_col], self.board[empty_row][empty_col])
        return True
    
    def _get_empty_position(self):
        for r in range(4):
            for c in range(4):
                if self.board[r][c] is None:
                    return r, c

    def _get_percentage_completion(self) -> float:
        goal = list(range(1, 16)) + [None]
        correct = 0
        total = 0
        # Flatten all 3 boards for easier comparison
        flat_current = [tile for row in self.board for tile in row]
        flat_initial = [tile for row in self.initial_board for tile in row]
        for idx, goal_tile in enumerate(goal):
            if flat_initial[idx] == goal_tile: continue  # Skip tiles that were already in the right place initially
            total += 1
            if flat_current[idx] == goal_tile:
                correct += 1
        return correct / total if total > 0 else 0.0
