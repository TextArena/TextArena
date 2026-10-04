# Tower of Hanoi Environment Documentation

## Overview
**Tower of Hanoi** is a classic single-player puzzle game where the objective is to move a stack of disks from one tower to another following specific rules. The puzzle consists of three towers (labeled A, B, and C) and a set of disks of different sizes. Initially, all disks are stacked on tower A in descending order of size with the largest disk at the bottom. The goal is to move the entire stack to tower C while adhering to the constraint that a larger disk can never be placed on top of a smaller disk. This implementation offers configurable difficulty through the number of disks and provides move validation to ensure game rules are followed.

## Action Space

- **Format:** Submit `source target`, where source and target are tower identifiers (A, B, or C).
- **Examples:**
  - Move a disk from tower A to tower C: `A C`
  - Move a disk from tower B to tower A: `B A`

## Observation Space

**Reset Observations**
On reset, the player receives a prompt containing the initial state of the towers and the game rules. For example:

```plaintext
You are Player 0. You are playing Tower of Hanoi with 3 disks.
You have to move the disks from tower A to tower C.
To move a disk, type the source tower and the target tower (e.g., 'A C').
Note that you can only move the top disk of a tower, and that a bigger disk cannot be placed on a smaller disk.
As you play, the history of your moves will be displayed.
Here is the current state of the towers:
A: [3, 2, 1]
B: []
C: []
```

**Step Observations**
After each move, the player receives an updated view of the towers. For example:

```plaintext
[Player 0] A C
[GAME] Player 0 moved disk from A to C. Here is the current state of the towers:
A: [3, 2]
B: []
C: [1]

[Player 0] A B
[GAME] Player 0 moved disk from A to B. Here is the current state of the towers:
A: [3]
B: [2]
C: [1]
```

## Gameplay

- **Players:** 1 player (single-player game)
- **Initial Setup:** All disks stacked on tower A in descending order of size (largest at the bottom)
- **Towers:** Three towers labeled A, B, and C
- **Objective:** Move all disks from tower A to tower C following the game rules
- **Maximum Turns:** Configurable, default is 100 turns

## Key Rules

1. **Disk Movement:**
   - Only one disk can be moved at a time
   - Only the topmost disk of a tower can be moved
   - A disk can be placed on an empty tower or on top of a larger disk
   - A larger disk cannot be placed on top of a smaller disk

2. **Valid Moves:**
   - Source tower must not be empty
   - Target tower must either be empty or have a top disk larger than the disk being moved
   - Source and target towers must be valid tower identifiers (A, B, or C)

3. **Winning Condition:**
   - **Win:** All disks are moved to tower C in the correct order (largest at the bottom)
   - **Loss:** Failing to complete the puzzle within the maximum number of allowed turns

4. **Game Termination:**
   - The game concludes when either all disks are successfully moved to tower C or the maximum turn limit is reached

## Rewards

| Outcome     | Reward for Player |
|-------------|:-----------------:|
| **Win**     | `+1`              |
| **Turn limit** | fraction of disks correctly stacked from the base of tower C |
| **Invalid-move limit** | the same bounded completion fraction |

## Parameters

- `num_disks` (`int`, default: `3`):
  - **Description:** Number of disks in the puzzle
  - **Allowed range:** `1` to `20`
  - **Impact:** More disks exponentially increase the puzzle's complexity and minimum required moves

- `max_turns` (`int`, default: `100`):
  - **Description:** Maximum number of turns allowed to solve the puzzle
  - **Constraint:** Must be at least `2 ** num_disks - 1`, the optimal solution length

## Variants

| Env-id                    | num_disks | max_turns |
|---------------------------|:---------:|:---------:|
| `TowerOfHanoi-v0`         | `3`       | `14`      |
| `TowerOfHanoi-v0-medium`  | `4`       | `30`      |
| `TowerOfHanoi-v0-hard`    | `5`       | `62`      |
| `TowerOfHanoi-v0-hardcore`| `6`       | `126`     |
| `TowerOfHanoi-v0-extreme` | `7`       | `254`     |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg