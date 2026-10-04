# Lights Out Environment Documentation

## Overview

**Lights Out** is a classic single-player puzzle game played on a grid of lights. Each light can be either on or off. When a player presses a light, it toggles its state and the state of its four adjacent neighbors (up, down, left, and right). The objective is to turn all the lights off. 

## Action Space

* **Format:** Submit `row col` using 0-indexed coordinates.
* **Examples:**

  * Press the light at row 2, column 3: `2 3`
  * Press the light at the top-left corner: `0 0`

## Observation Space

**Reset Observations**

The first observation contains the rules and a generated, non-solved grid. `O`
is an illuminated cell and `.` is an unlit cell. For example:

```plaintext
Current grid state (Move 0, 20 moves remaining, 0.0% complete):
   0 1 2 3 4
0: O . O . .
1: . O O . .
2: . . O . .
3: . . . . .
4: . . . . .
```

### Step Observations

After each valid press, the player receives the current grid, valid-move count,
moves remaining, and bounded completion percentage:

```plaintext
[Player 0] 2 2
Current grid state (Move 1, 19 moves remaining, 25.0% complete):
   0 1 2 3 4
0: O . O . .
1: . O . . .
2: . O . O .
3: . . O . .
4: . . . . .
```


## Gameplay

- **Players:** 1 (single-player game)
- **Initial Setup:** A square grid of lights in a random configuration.
- **Turns:** The player presses one light per turn.
- **Objective:** Turn all lights off.

## Key Rules

1. **Move Mechanics:**

   * A move consists of choosing one cell as `row col`.
   * Pressing a cell toggles the state of that cell and its four orthogonal neighbors (up, down, left, right).

2. **Valid Moves:**

   * Both coordinates must be within the grid boundaries.

3. **Winning Condition:**

   * The player wins when all lights on the grid are turned off.

4. **Loss Condition:**

   * The player loses if they fail to solve the puzzle within the maximum allowed turns.

5. **Game Termination:**

   * The game concludes when the puzzle is solved or the turn limit is reached.


## Rewards

| Outcome | Reward for Player |
| --- | --- |
| Solved | `1.0` |
| Turn limit | bounded fraction of the initially lit cells turned off |
| Invalid-move limit | the same bounded completion fraction |

## Parameters

* **`size`** (`int`, default: `5`, range: `1`–`20`):

  * **Description:** Sets the height and width of the square grid.
  * **Impact:** Larger grids exponentially increase the complexity of the puzzle.

* **`max_turns`** (`int`, default: `50`):

  * **Description:** Maximum number of turns allowed to complete the puzzle
  * **Impact:** Fewer turns increase pressure on the player to solve quickly

## Variants

| Env-id | `size` | `max_turns` |
| --- | ---: | ---: |
| `LightsOut-v0` | `5` | `20` |


