import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta

from textarena.envs.Sokoban.utils import generate_room, find_cells, CHANGE_COORDINATES


def _shifted(position: Tuple[int, int], change: Tuple[int, int]) -> Tuple[int, int]:
    return position[0] + change[0], position[1] + change[1]


class SokobanEnv(ta.GameEnv):
    min_players = 1
    max_players = 1
    mdp_includes_actions = False
    max_action_chars = 4096

    dim_room = ta.Param(
        (6, 6), "The room size as (rows, columns); the outer ring is always wall.",
        check=lambda dim: len(dim) == 2 and all(isinstance(v, int) and not isinstance(v, bool) and v >= 4 for v in dim)
        and dim[0] * dim[1] <= 400,
        rule="two integers of at least 4 with at most 400 cells in total",
    )
    num_boxes = ta.Param(3, "The number of boxes and goals. It must leave room for the player inside the walls.", min=1)
    max_turns = ta.Param(100, "The number of valid moves allowed. Generated rooms are always solvable within it.", min=1)
    max_retries = ta.Param(50, "Generation attempts before reset gives up with RuntimeError.", min=1, max=100)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.num_boxes + 1 >= (self.dim_room[0] - 2) * (self.dim_room[1] - 2):
            raise ValueError("num_boxes is too large for the room dimensions")
        self.num_gen_steps = int(1.7 * (self.dim_room[0] + self.dim_room[1]))
        self.action_space = ['up', 'down', 'left', 'right']

    @property
    def room_state(self) -> List[List[int]]: return self.game_state["board"]

    @property
    def room_fixed(self) -> List[List[int]]: return self.game_state["room_fixed"]

    @property
    def player_position(self) -> Tuple[int, int]: return self.game_state["player_position"]

    @player_position.setter
    def player_position(self, value): self.game_state["player_position"] = value

    def setup(self) -> Dict[str, Any]:
        # The reverse search only returns rooms solvable in at most search_depth - 2 moves.
        search_depth = min(max(10, min(self.max_turns, 30)), self.max_turns + 2)
        for _ in range(self.max_retries):
            room = generate_room(
                self.rng,
                dim=self.dim_room,
                num_steps=self.num_gen_steps,
                num_boxes=self.num_boxes,
                search_depth=search_depth,
            )
            if room is not None:
                room_fixed, room_state, box_mapping = room
                return {
                    "board": room_state,
                    "room_fixed": room_fixed,
                    "box_mapping": box_mapping,
                    "player_position": find_cells(room_state, 5)[0],
                }
        raise RuntimeError(f"Failed to generate valid room after {self.max_retries} attempts")

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

    def create_board_str(self, board_state: List[List[int]]) -> str:
        grid_lookup = {0: "#", 1: "_", 2: "O", 3: "√", 4: "X", 5: "P", 6: "+"}
        room_fixed = self.room_fixed

        board_str = ""
        for r, row in enumerate(board_state):
            cells = [6 if cell == 5 and room_fixed[r][c] == 2 else cell for c, cell in enumerate(row)]
            board_str += ' '.join([grid_lookup[cell] for cell in cells])
            board_str += "\n"
        return board_str

    def apply(self, player_id: int, move: str) -> Union[ta.Outcome, ta.Invalid, None]:
        # Accept both full and alias directions (e.g., up, w)
        matches = re.fullmatch(
            r"(up|down|left|right|w|a|s|d)",
            move,
            re.IGNORECASE,
        )

        if matches is None:
            return self.invalid("The submitted move does not follow the correct format. Use 'up', 'down', 'left', 'right' or 'w', 'a', 's', 'd'.")

        raw_action = matches.group(1).lower()
        alias_to_action = {'w': 'up', 'a': 'left', 's': 'down', 'd': 'right'}
        action = alias_to_action.get(raw_action, raw_action)

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
        new_position = _shifted(self.player_position, change)

        # Check bounds
        if (new_position[0] < 0 or new_position[0] >= len(self.room_state) or
                new_position[1] < 0 or new_position[1] >= len(self.room_state[0])):
            return "You cannot move into a wall!"

        # Check if the new position is a wall (value 0)
        if self.room_state[new_position[0]][new_position[1]] == 0:
            return "You cannot move into a wall!"

        # Check if there's a box that would be pushed into a wall or out of bounds
        if self.room_state[new_position[0]][new_position[1]] in [3, 4]:  # There's a box
            box_new_position = _shifted(new_position, change)

            # Check if box would go out of bounds
            if (box_new_position[0] < 0 or box_new_position[0] >= len(self.room_state) or
                    box_new_position[1] < 0 or box_new_position[1] >= len(self.room_state[0])):
                return "You cannot push a box into a wall!"

            # Check if box would be pushed into a wall or another box
            if self.room_state[box_new_position[0]][box_new_position[1]] in [3, 4]:
                return "You cannot push a box into another box!"
            if self.room_state[box_new_position[0]][box_new_position[1]] not in [1, 2]:  # Not empty floor or target
                return "You cannot push a box into a wall!"

        return None

    def _push(self, action):
        """
        Perform a push, if a box is adjacent in the right direction. If no box, can be pushed, try to move.
        Returns (move_successful, box_pushed)
        """
        change = CHANGE_COORDINATES[self.action_space.index(action)]
        new_position = _shifted(self.player_position, change)
        current_position = self.player_position

        # Check bounds first
        if (new_position[0] < 0 or new_position[0] >= len(self.room_state) or
                new_position[1] < 0 or new_position[1] >= len(self.room_state[0])):
            return False, False

        # No push, if the push would get the box out of the room's grid
        new_box_position = _shifted(new_position, change)
        if (new_box_position[0] < 0 or new_box_position[0] >= len(self.room_state) or
                new_box_position[1] < 0 or new_box_position[1] >= len(self.room_state[0])):
            # Try to move instead if no box pushing is possible
            return self._move(action), False

        can_push_box = self.room_state[new_position[0]][new_position[1]] in [3, 4]
        can_push_box &= self.room_state[new_box_position[0]][new_box_position[1]] in [1, 2]
        if can_push_box:
            # Move Player
            self.player_position = new_position
            self.room_state[new_position[0]][new_position[1]] = 5
            self.room_state[current_position[0]][current_position[1]] = self.room_fixed[current_position[0]][current_position[1]]

            # Move Box
            box_type = 4
            if self.room_fixed[new_box_position[0]][new_box_position[1]] == 2: box_type = 3
            self.room_state[new_box_position[0]][new_box_position[1]] = box_type
            return True, True

        # Try to move if no box to push, available
        else:
            return self._move(action), False

    def _move(self, action):
        """
        Moves the player to the next field, if it is not occupied.
        """
        change = CHANGE_COORDINATES[self.action_space.index(action)]
        new_position = _shifted(self.player_position, change)
        current_position = self.player_position

        # Check bounds
        if (new_position[0] < 0 or new_position[0] >= len(self.room_state) or
                new_position[1] < 0 or new_position[1] >= len(self.room_state[0])):
            return False

        # Move player if the field in the moving direction is either
        # an empty field or an empty box target.
        if self.room_state[new_position[0]][new_position[1]] in [1, 2]:
            self.player_position = new_position
            self.room_state[new_position[0]][new_position[1]] = 5
            self.room_state[current_position[0]][current_position[1]] = self.room_fixed[current_position[0]][current_position[1]]
            return True
        return False

    def _check_if_all_boxes_on_target(self):
        """
        Check how many boxes are currently on targets and if all boxes are on targets.

        Returns:
            tuple: (number_of_boxes_on_targets, all_boxes_on_targets_boolean)
        """
        # Count boxes that are on targets (value 3 = √)
        boxes_on_targets = sum(row.count(3) for row in self.room_state)
        all_boxes_on_targets = (boxes_on_targets == self.num_boxes)
        return boxes_on_targets, all_boxes_on_targets

    def _get_percentage_completion(self) -> float:
        """ Compute how many boxes are on targets """
        boxes_on_targets, all_boxes_on_targets = self._check_if_all_boxes_on_target()
        return boxes_on_targets / self.num_boxes if not all_boxes_on_targets else 1.0
