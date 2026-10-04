import re
import numpy as np
from typing import Any, Dict, Optional, Tuple, Union

import textarena as ta

from textarena.envs.Sokoban.utils import generate_room, CHANGE_COORDINATES


class SokobanEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    max_room_cells = 400
    max_action_chars = 4096

    def __init__(self, dim_room=(6, 6), max_turns=100, num_boxes=3):
        if (
            not isinstance(dim_room, tuple)
            or len(dim_room) != 2
            or any(not isinstance(v, int) or isinstance(v, bool) or v < 4 for v in dim_room)
        ):
            raise ValueError("dim_room must be a (rows, cols) tuple with both dimensions at least 4")
        if dim_room[0] * dim_room[1] > self.max_room_cells:
            raise ValueError(
                f"dim_room creates more than {self.max_room_cells} room cells"
            )
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns <= 0:
            raise ValueError("max_turns must be a positive integer")
        if not isinstance(num_boxes, int) or isinstance(num_boxes, bool) or num_boxes <= 0:
            raise ValueError("num_boxes must be a positive integer")
        if num_boxes + 1 >= (dim_room[0] - 2) * (dim_room[1] - 2):
            raise ValueError("num_boxes is too large for the room dimensions")
        self.dim_room = dim_room
        self.num_gen_steps = int(1.7 * (dim_room[0] + dim_room[1]))
        self.num_boxes = num_boxes
        self.max_turns = max_turns
        self.action_space = ['up', 'down', 'left', 'right']
        self._max_retries: int = 50

    def reset(self, num_players: int, seed: Optional[int] = None, max_retries: int = 50):
        if (
            not isinstance(max_retries, int)
            or isinstance(max_retries, bool)
            or not 1 <= max_retries <= 100
        ):
            raise ValueError("max_retries must be an integer between 1 and 100")
        self._max_retries = max_retries
        super().reset(num_players=num_players, seed=seed)

    @property
    def room_state(self) -> np.ndarray: return self.game_state["board"]

    @property
    def room_fixed(self) -> np.ndarray: return self.game_state["room_fixed"]

    @property
    def box_mapping(self) -> Dict: return self.game_state["box_mapping"]

    @property
    def player_position(self) -> np.ndarray: return self.game_state["player_position"]

    @player_position.setter
    def player_position(self, value): self.game_state["player_position"] = value

    def setup(self) -> Dict[str, Any]:
        # The reverse search only returns rooms solvable in at most search_depth - 2 moves.
        search_depth = min(max(10, min(self.max_turns, 30)), self.max_turns + 2)
        for attempt in range(self._max_retries):
            try:
                room_fixed, room_state, box_mapping = generate_room(
                    dim=self.dim_room,
                    num_steps=self.num_gen_steps,
                    num_boxes=self.num_boxes,
                    seed=self.rng.getrandbits(32),
                    search_depth=search_depth,
                )
                break
            except (RuntimeError, RuntimeWarning):
                if attempt == self._max_retries - 1:
                    raise RuntimeError(f"Failed to generate valid room after {self._max_retries} attempts")
                continue

        return {
            "board": room_state,
            "room_fixed": room_fixed,
            "box_mapping": box_mapping,
            "player_position": np.argwhere(room_state == 5)[0],
        }

    def prompt(self, player_id: int) -> str:
        return (
            "You are solving the Sokoban puzzle. You are the player and you need to push all boxes to targets.\n"
            "When you are right next to a box, you can push it by moving in the same direction.\n"
            "You cannot push a box through a wall or into another box, and you cannot pull a box.\n"
            "On the board, objects are represented as:\n"
            "- The player (you) appears as 'P', or '+' while standing on an empty goal\n"
            "- Walls are represented with '#'\n"
            "- Empty floor is shown as '_'\n"
            "- Boxes are marked as 'X'\n"
            "- Empty goals are shown with a 'O'\n"
            "- Boxes on goals are visualized with '√'\n"
            "Reply with a direction: 'up', 'down', 'left' or 'right'.\n"
            "You can also use 'w' for up, 'a' for left, 's' for down, and 'd' for right.\n"
            f"Walking into a wall or making a blocked push is an invalid move. You have {self.max_turns} moves.\n"
        )

    def render(self, player_id: int) -> str:
        return f"Current Board:\n\n{self.create_board_str(self.room_state)}\nAvailable Moves: " + ", ".join(self.action_space)

    def get_board_str(self):
        return self.create_board_str(board_state=self.state.game_state['board'])

    def create_board_str(self, board_state: np.ndarray) -> str:
        grid_lookup = {0: "#", 1: "_", 2: "O", 3: "√", 4: "X", 5: "P", 6: "+"}
        room_fixed = self.room_fixed

        board_str = ""
        for r, row in enumerate(board_state):
            cells = [6 if cell == 5 and room_fixed[r, c] == 2 else cell for c, cell in enumerate(row)]
            board_str += ' '.join([grid_lookup[cell] for cell in cells])
            board_str += "\n"
        return board_str

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        if len(move) > self.max_action_chars:
            return self.invalid(
                f"Action is too long (maximum {self.max_action_chars} characters)."
            )
        # Accept both full and alias directions (e.g., up, w)
        action_text = move.strip()
        if action_text.startswith("[") or action_text.endswith("]"):
            if not (action_text.startswith("[") and action_text.endswith("]")):
                return self.invalid("The submitted move has mismatched brackets.")
            action_text = action_text[1:-1].strip()
        matches = re.fullmatch(
            r"(up|down|left|right|w|a|s|d)",
            action_text,
            re.IGNORECASE,
        )

        if matches is None:
            return self.invalid("The submitted move does not follow the correct format. Use 'up', 'down', 'left', 'right' or 'w', 'a', 's', 'd'.")

        raw_action = matches.group(1).lower()
        alias_to_action = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}
        action = alias_to_action.get(raw_action, raw_action)

        if action not in self.action_space:
            return self.invalid("The submitted move is not a valid action.")
        collision = self._collision_reason(action)
        if collision is not None:
            return self.invalid(collision)

        move_successful, box_pushed = self._push(action)
        if not move_successful:
            return self.invalid("Invalid move - cannot move to that position.")

        msg = f"You moved {action} and pushed a box." if box_pushed else f"You moved {action}."
        self.broadcast(msg, ta.ObservationType.GAME_MESSAGE)

        boxes_on_targets, all_boxes_on_targets = self._check_if_all_boxes_on_target()
        if all_boxes_on_targets:
            return self.outcome({0: 1}, reason="Congratulations! You have solved the Sokoban puzzle!")
        return None

    def on_turn_limit(self) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason="The turn limit has been reached. You did not solve the puzzle.")

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _would_collide_with_wall(self, action: str) -> bool:
        """
        Check if the given action would result in a wall collision.
        Returns True if the player would collide with a wall, False otherwise.
        """
        return self._collision_reason(action) is not None

    def _collision_reason(self, action: str) -> Optional[str]:
        """Why the player cannot move in this direction (a wall or a blocked push), or None if they can."""
        change = CHANGE_COORDINATES[self.action_space.index(action)]
        new_position = self.player_position + change

        # Check bounds
        if (new_position[0] < 0 or new_position[0] >= self.room_state.shape[0] or
                new_position[1] < 0 or new_position[1] >= self.room_state.shape[1]):
            return "You cannot move into a wall!"

        # Check if the new position is a wall (value 0)
        if self.room_state[new_position[0], new_position[1]] == 0:
            return "You cannot move into a wall!"

        # Check if there's a box that would be pushed into a wall or out of bounds
        if self.room_state[new_position[0], new_position[1]] in [3, 4]:  # There's a box
            box_new_position = new_position + change

            # Check if box would go out of bounds
            if (box_new_position[0] < 0 or box_new_position[0] >= self.room_state.shape[0] or
                    box_new_position[1] < 0 or box_new_position[1] >= self.room_state.shape[1]):
                return "You cannot push a box into a wall!"

            # Check if box would be pushed into a wall or another box
            if self.room_state[box_new_position[0], box_new_position[1]] in [3, 4]:
                return "You cannot push a box into another box!"
            if self.room_state[box_new_position[0], box_new_position[1]] not in [1, 2]:  # Not empty floor or target
                return "You cannot push a box into a wall!"

        return None

    def _push(self, action):
        """
        Perform a push, if a box is adjacent in the right direction. If no box, can be pushed, try to move.
        Returns (move_successful, box_pushed)
        """
        change = CHANGE_COORDINATES[self.action_space.index(action)]
        new_position = self.player_position + change
        current_position = self.player_position.copy()

        # Check bounds first
        if (new_position[0] < 0 or new_position[0] >= self.room_state.shape[0] or
                new_position[1] < 0 or new_position[1] >= self.room_state.shape[1]):
            return False, False

        # No push, if the push would get the box out of the room's grid
        new_box_position = new_position + change
        if (new_box_position[0] < 0 or new_box_position[0] >= self.room_state.shape[0] or
                new_box_position[1] < 0 or new_box_position[1] >= self.room_state.shape[1]):
            # Try to move instead if no box pushing is possible
            return self._move(action), False

        can_push_box = self.room_state[new_position[0], new_position[1]] in [3, 4]
        can_push_box &= self.room_state[new_box_position[0], new_box_position[1]] in [1, 2]
        if can_push_box:
            self.new_box_position = tuple(new_box_position)
            self.old_box_position = tuple(new_position)

            # Move Player
            self.player_position = new_position
            self.room_state[(new_position[0], new_position[1])] = 5
            self.room_state[current_position[0], current_position[1]] = self.room_fixed[current_position[0], current_position[1]]

            # Move Box
            box_type = 4
            if self.room_fixed[new_box_position[0], new_box_position[1]] == 2: box_type = 3
            self.room_state[new_box_position[0], new_box_position[1]] = box_type
            return True, True

        # Try to move if no box to push, available
        else:
            return self._move(action), False

    def _move(self, action):
        """
        Moves the player to the next field, if it is not occupied.
        """
        change = CHANGE_COORDINATES[self.action_space.index(action)]
        new_position = self.player_position + change
        current_position = self.player_position.copy()

        # Check bounds
        if (new_position[0] < 0 or new_position[0] >= self.room_state.shape[0] or
                new_position[1] < 0 or new_position[1] >= self.room_state.shape[1]):
            return False

        # Move player if the field in the moving direction is either
        # an empty field or an empty box target.
        if self.room_state[new_position[0], new_position[1]] in [1, 2]:
            self.player_position = new_position
            self.room_state[(new_position[0], new_position[1])] = 5
            self.room_state[current_position[0], current_position[1]] = self.room_fixed[current_position[0], current_position[1]]
            return True
        return False

    def _check_if_all_boxes_on_target(self):
        """
        Check how many boxes are currently on targets and if all boxes are on targets.

        Returns:
            tuple: (number_of_boxes_on_targets, all_boxes_on_targets_boolean)
        """
        # Count boxes that are on targets (value 3 = √)
        boxes_on_targets = int(np.sum(self.room_state == 3))
        all_boxes_on_targets = (boxes_on_targets == self.num_boxes)
        return boxes_on_targets, all_boxes_on_targets

    def _get_percentage_completion(self) -> float:
        """ Compute how many boxes are on targets """
        boxes_on_targets, all_boxes_on_targets = self._check_if_all_boxes_on_target()
        return boxes_on_targets / self.num_boxes if not all_boxes_on_targets else 1.0
