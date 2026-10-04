# Minesweeper Environment Documentation

## Overview
**Minesweeper** is a classic single-player puzzle game where the objective is to reveal every safe cell without selecting a mine. Adjacent numbers indicate how many neighboring mines surround a cell, and the first move is guaranteed to be safe.

## Action Space

- **Format:** Submit `row column` to reveal a cell.
- **Example:** `3 2` reveals the cell at row 3, column 2.

## Observation Space

**Reset Observations**
On reset, the player receives a prompt containing the game instructions and the initial board state. For example:

```plaintext
You are Player 0. You are playing the Minesweeper game.
The objective of the game is to reveal all cells that do not contain mines.
Reply with the row and column coordinates you want to reveal, in the format 'row col'.
For example, '3 2' reveals the cell in Row 3, Column 2.
On your first move, you will reveal an area around the cell you choose to ensure a safe start.
The current board layout is shown below. Unrevealed cells are dots, and revealed numbers show the count of adjacent mines.
Use logic and deduction to avoid revealing cells with mines!
Do not choose a cell that has already been revealed.
Here is the current board layout:

   0  1  2  3  4  5  6  7
 0  .  .  .  .  .  .  .  .
 1  .  .  .  .  .  .  .  .
 2  .  .  .  .  .  .  .  .
 3  .  .  .  .  .  .  .  .
 4  .  .  .  .  .  .  .  .
 5  .  .  .  .  .  .  .  .
 6  .  .  .  .  .  .  .  .
 7  .  .  .  .  .  .  .  .
```

**Step Observations**
After each move, the player receives an updated view of the board. For example:

```plaintext
[Player 0] 4 4
[GAME] Game Board:
   0  1  2  3  4  5  6  7
 0  .  .  .  .  .  .  .  .
 1  .  .  .  .  .  .  .  .
 2  .  .  .  1  1  1  .  .
 3  .  .  1  1  0  1  1  .
 4  .  .  1  0  0  0  1  .
 5  .  .  1  0  0  0  1  .
 6  .  .  1  1  1  1  1  .
 7  .  .  .  .  .  .  .  .
```

## Gameplay

- **Players:** 1 player (single-player game)
- **Initial Setup:** A rectangular grid with hidden mines is created
- **Turns:** The player reveals one cell per turn
- **Objective:** Reveal all cells that do not contain mines
- **Maximum Turns:** Configurable, default is 100 turns

## Key Rules

1. **Board Generation:**
   - The game board is a rectangular grid (default: 8×8) containing a specified number of randomly placed mines (default: 10)
   - The first move is guaranteed to be safe, with no mines in the 3×3 area around the first revealed cell

2. **Cell Revealing:**
   - When a cell is revealed, it shows either a number (indicating the count of adjacent mines) or remains empty (if no adjacent mines)
   - If a cell with no adjacent mines is revealed, all neighboring cells are automatically revealed in a cascade
   - Revealing a cell containing a mine results in immediate game over

3. **Valid Moves:**
   - Players can reveal cells within the grid bounds
   - Players cannot reveal cells that are already revealed

4. **Winning Conditions:**
   - **Win:** The player reveals all safe cells
   - **Loss:** The player reveals a cell containing a mine

5. **Game Termination:**
   - The game concludes when all safe cells are revealed or the turn limit is reached

## Rewards

| Outcome     | Reward for Player |
|-------------|:-----------------:|
| **Win**     | `+1`              |
| **Loss**    | `self._get_percentage_completion()`              |
| **Invalid** | `self._get_percentage_completion()`              |

## Parameters

- `rows` (`int`, default: `8`):
  - **Description:** Sets the number of rows in the grid
  - **Impact:** Larger grid increases difficulty by expanding the playing area

- `cols` (`int`, default: `8`):
  - **Description:** Sets the number of columns in the grid
  - **Impact:** Larger grid increases difficulty by expanding the playing area

- `num_mines` (`int`, default: `10`):
  - **Description:** Sets the number of mines in the grid
  - **Impact:** More mines increase difficulty by making it harder to find safe paths

- `max_turns` (`int`, default: `100`):
  - **Description:** Sets the maximum number of turns allowed
  - **Impact:** Fewer turns make the game more challenging by limiting attempts

## Variants

| Env-id                  | rows | cols | num_mines | max_turns |
|-------------------------|:----:|:----:|:---------:|:---------:|
| `Minesweeper-v0`        | `8`  | `8`  | `10`      | `100`     |
| 'Minesweeper-v0-small   | `5`  | `5`  | `5`       | `100`     |
| `Minesweeper-v0-medium` | `10` | `10` | `20`      | `100`     |
| `Minesweeper-v0-hard`   | `12` | `12` | `30`      | `100`     |

### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg