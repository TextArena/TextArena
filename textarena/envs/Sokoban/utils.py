import random
from dataclasses import dataclass, field
from itertools import chain
from typing import Optional


# Moves are mapped to coordinate changes as follows
# 0: Move up
# 1: Move down
# 2: Move left
# 3: Move right
CHANGE_COORDINATES = {
    0: (-1, 0),
    1: (1, 0),
    2: (0, -1),
    3: (0, 1)
}
MAX_EXPLORED_STATES = 50_000


def find_cells(room, *values):
    """(row, col) of every cell holding one of `values`, in row-major order."""
    return [(r, c) for r, row in enumerate(room) for c, cell in enumerate(row) if cell in values]


def generate_room(
    rng: random.Random,
    dim=(13, 13),
    p_change_directions=0.35,
    num_steps=25,
    num_boxes=3,
    search_depth: int = 100,
):
    """
    One attempt at a room: carve floors with a random walk, put every box on its goal, then pull the boxes off
    by playing in reverse. Undoing the pulls solves the room, so every room returned is solvable.
    Returns (room_structure, room_state, box_mapping), or None if this attempt failed.
    """
    room = room_topology_generation(rng, dim, p_change_directions, num_steps)
    floors = find_cells(room, 1)
    if len(floors) <= num_boxes + 1:
        return None
    player, *goals = rng.sample(floors, num_boxes + 1)
    room[player[0]][player[1]] = 5
    for r, c in goals:
        room[r][c] = 2

    # Room structure holds the parts of the room that never move; room state adds the boxes and the player.
    room_structure = [[1 if cell == 5 else cell for cell in row] for row in room]
    room_state = [[4 if cell == 2 else cell for cell in row] for row in room]
    room_state, score, box_mapping = reverse_playing(room_state, room_structure, search_depth=search_depth)
    if score <= 0:
        return None
    for r, c in find_cells(room_state, 3, 4):
        room_state[r][c] = 3 if room_structure[r][c] == 2 else 4
    return room_structure, room_state, box_mapping


def room_topology_generation(rng, dim=(10, 10), p_change_directions=0.35, num_steps=15):
    """
    Generate a room topology, which consits of empty floors and walls.
    """
    dim_x, dim_y = dim

    # The ones in the mask represent all fields which will be set to floors
    # during the random walk. The centered one will be placed over the current
    # position of the walk.
    masks = [
        [
            [0, 0, 0],
            [1, 1, 1],
            [0, 0, 0]
        ],
        [
            [0, 1, 0],
            [0, 1, 0],
            [0, 1, 0]
        ],
        [
            [0, 0, 0],
            [1, 1, 0],
            [0, 1, 0]
        ],
        [
            [0, 0, 0],
            [1, 1, 0],
            [1, 1, 0]
        ],
        [
            [0, 0, 0],
            [0, 1, 1],
            [0, 1, 0]
        ]
    ]

    # Possible directions during the walk
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    direction = rng.choice(directions)

    # Starting position of random walk
    position = (
        rng.randint(1, dim_x - 1),
        rng.randint(1, dim_y - 1)
    )

    level = [[0] * dim_y for _ in range(dim_x)]

    for s in range(num_steps):

        # Change direction randomly
        if rng.random() < p_change_directions:
            direction = rng.choice(directions)

        # Update position
        position = (
            max(min(position[0] + direction[0], dim_x - 2), 1),
            max(min(position[1] + direction[1], dim_y - 2), 1)
        )

        # Apply mask
        mask = rng.choice(masks)
        mask_start = (position[0] - 1, position[1] - 1)
        for dx, mask_row in enumerate(mask):
            for dy, floor in enumerate(mask_row):
                if floor:
                    level[mask_start[0] + dx][mask_start[1] + dy] = 1

    for row in level:
        row[0] = row[dim_y - 1] = 0
    level[0] = [0] * dim_y
    level[dim_x - 1] = [0] * dim_y

    return level


@dataclass
class ReverseSearch:
    """Explored states and the best room found so far by one reverse-play search."""
    num_boxes: int
    best_box_mapping: dict
    best_room: Optional[list] = None
    best_room_score: int = -1
    explored_states: set = field(default_factory=set)


def reverse_playing(room_state, room_structure, search_depth=100):
    """
    This function plays Sokoban reverse in a way, such that the player can
    move and pull boxes.
    It ensures a solvable level with all boxes not being placed on a box target.
    """
    # Box_Mapping is used to calculate the box displacement for every box
    box_mapping = {box: box for box in find_cells(room_structure, 2)}

    search = ReverseSearch(num_boxes=len(box_mapping), best_box_mapping=box_mapping)
    depth_first_search(
        search,
        room_state,
        room_structure,
        box_mapping,
        box_swaps=0,
        last_pull=(-1, -1),
        ttl=search_depth,
    )

    return search.best_room, search.best_room_score, search.best_box_mapping


def depth_first_search(search, room_state, room_structure, box_mapping, box_swaps=0, last_pull=(-1, -1), ttl=300):
    """
    Searches through all possible states of the room.
    This is a recursive function, which stops if the ttl is reduced to 0 or
    MAX_EXPLORED_STATES states have been explored.
    """
    ttl -= 1
    if ttl <= 0 or len(search.explored_states) >= MAX_EXPLORED_STATES:
        return

    # Cell values are 0-5, so a room state packs into one byte per cell.
    state_tohash = bytes(chain.from_iterable(room_state))

    # Only search this state, if it not yet has been explored
    if not (state_tohash in search.explored_states):

        # Add current state and its score to explored states
        room_score = box_swaps * box_displacement_score(box_mapping)
        if sum(row.count(2) for row in room_state) != search.num_boxes:
            room_score = 0

        if room_score > search.best_room_score:
            search.best_room = room_state
            search.best_room_score = room_score
            search.best_box_mapping = box_mapping

        search.explored_states.add(state_tohash)

        for action in ['up', 'down', 'left', 'right']:
            moved = reverse_move(room_state, room_structure, box_mapping, last_pull, action)
            if moved is None:
                continue
            room_state_next, box_mapping_next, last_pull_next = moved

            box_swaps_next = box_swaps
            if last_pull_next != last_pull:
                box_swaps_next += 1

            depth_first_search(search, room_state_next, room_structure,
                               box_mapping_next, box_swaps_next,
                               last_pull_next, ttl)


def reverse_move(room_state, room_structure, box_mapping, last_pull, action):
    """
    Perform a reverse action: the player moves one field and pulls along the box
    behind them, if there is one. Returns the new room state, box mapping and last
    pulled box, leaving the arguments unchanged, or None if the move is blocked.
    """
    player_row = next(r for r, row in enumerate(room_state) if 5 in row)
    player_position = (player_row, room_state[player_row].index(5))

    change = CHANGE_COORDINATES[['up', 'down', 'left', 'right'].index(action)]
    next_position = (player_position[0] + change[0], player_position[1] + change[1])

    # Check if next position is an empty floor or an empty box target
    if room_state[next_position[0]][next_position[1]] not in [1, 2]:
        return None

    room_state = [row[:] for row in room_state]

    # Move player, independent of pull or move action.
    room_state[player_position[0]][player_position[1]] = room_structure[player_position[0]][player_position[1]]
    room_state[next_position[0]][next_position[1]] = 5

    # In addition try to pull a box if the action is a pull action
    possible_box_location = (player_position[0] - change[0], player_position[1] - change[1])

    if room_state[possible_box_location[0]][possible_box_location[1]] in [3, 4]:
        # Perform pull of the adjacent box
        room_state[player_position[0]][player_position[1]] = 3
        room_state[possible_box_location[0]][possible_box_location[1]] = room_structure[
            possible_box_location[0]][possible_box_location[1]]

        # Update the box mapping
        box_mapping = box_mapping.copy()
        for k in box_mapping.keys():
            if box_mapping[k] == possible_box_location:
                box_mapping[k] = player_position
                last_pull = k

    return room_state, box_mapping, last_pull


def box_displacement_score(box_mapping):
    """
    Calculates the sum of all Manhattan distances, between the boxes
    and their origin box targets.
    """
    score = 0
    for box_target, box_location in box_mapping.items():
        score += abs(box_location[0] - box_target[0]) + abs(box_location[1] - box_target[1])
    return score