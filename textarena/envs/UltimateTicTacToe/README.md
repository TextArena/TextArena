# Ultimate Tic Tac Toe Environment Documentation

## Overview
**Ultimate Tic Tac Toe** is a strategic two-player game that combines the classic Tic Tac Toe with an added layer of complexity. Players aim to win three micro boards in a row (horizontally, vertically, or diagonally) on the macro board, which tracks the outcomes of individual micro boards. Each move influences the opponent's next playable micro board, creating dynamic and strategic gameplay. This environment implements the full rules of Ultimate Tic Tac Toe, including valid move enforcement, micro board and macro board win detection, and a clear rendering of the board state for agent-based gameplay and experimentation.

## Action Space
- **Format:** Submit `macro micro`, where both values are indices from 0-8.
- **Example:**
    - Choosing macro board 0 and marking its cell 3 (row 1, column 0): `0 3`
    - Choosing macro board 3 and marking its cell 2 (row 0, column 2): `3 2`

## Observation Space
**Reset Observation**
On reset, each player receives a prompt containing their beginning game instructions. For example:
```plaintext
[GAME] You are Player 0. You are playing Ultimate Tic Tac Toe.
Your goal is to win three micro boards in a row (horizontally, vertically, or diagonally) on the macro board.
Each micro board is a 3x3 Tic Tac Toe grid, and the macro board tracks which player has won each micro board.
On your turn, you can mark an empty cell in a micro board. The position of your move determines which micro board
your opponent must play in next.

Rules to remember:
1. A move must be made in the micro board specified by the previous move.
   For example, if the last move was in the top-left corner of a micro board, the opponent must play in the top-left micro board.
2. If the directed micro board is already won or full, you are free to play in any available micro board.
3. You win a micro board by completing a row, column, or diagonal within that board.
4. You win the game by completing three micro boards in a row on the macro board.
5. The game ends in a draw if all micro boards are filled, and no player has three in a row on the macro board.
6. Submit `macro micro`, where macro is the micro-board index (0-8), and micro is the cell index within that board (0-8).
For example, to play in the center cell of the top-left micro board, submit `0 4`.

As Player 0, you will be 'X', whereas your opponent is 'O'.
Below is the current state of the macro board (tracking micro board wins):
      |       |      
      |       |      
      |       |      
-----------------------
      |       |      
      |       |      
      |       |      
-----------------------
      |       |      
      |       |      
      |       |      
-----------------------
```

**Step Observation**
After each step, the players will receive the latest message from the game environment. For example, here's player 0 making its first move and the environment responds back:
```plaintext
[Player 0] 4 4
[GAME] Player 0 made a move in micro board 4 at cell 4 (row 1, col 1). Player 1 must play in micro board 4. New state of the board:
      |       |      
      |       |      
      |       |      
-----------------------
      |       |      
      |   X   |      
      |       |      
-----------------------
      |       |      
      |       |      
      |       |      
-----------------------
```

## Gameplay
- **Players:** 2
- **Turns:** Players take turns placing their mark ('X' or 'O') in a specific cell of a micro board. Each turn determines the micro board their opponent must play in.
- **Board:** The game features a macro board (3x3 grid) representing the outcomes of nine micro boards (each a 3x3 Tic Tac Toe grid). The macro board is updated as players win micro boards.
- **Objective:** Win the game by completing three micro boards in a row (horizontally, vertically, or diagonally) on the macro board.
- **Winning Condition:** The first player to achieve three micro boards in a row on the macro board wins the game. If all micro boards are filled without a winner on the macro board, the game ends in a draw.

## Key Rules
### Gameplay Mechanics
1. Moves:
- Players select a cell in one of the nine micro boards.
- The selected cell determines the next micro board the opponent must play in.
- If the specified micro board is full or already won, the opponent can play in any available micro board.

2. Micro Board Wins:
- A micro board is won by completing a row, column, or diagonal within that board.
- The winning player's mark ('X' or 'O') is placed in the corresponding cell of the macro board.

3. Macro Board Wins:
- The game is won by completing three micro boards in a row on the macro board (horizontally, vertically, or diagonally).

4. Draws:
- The game ends in a draw if all cells on the macro board are filled and no player achieves three in a row.

### Phases of a Turn

1. Move Phase:
- The current player places their mark in an empty cell of the assigned micro board.
- If the directed micro board is unavailable, the player can choose any available micro board.

2. Board Update Phase:
- The game checks if the current move wins the micro board and updates the macro board accordingly.
- The game also evaluates the macro board to determine if a player has won or if the game is a draw.

3. Observation Phase:
- After the move, the game renders the updated board state (both macro and micro boards) for players to review and strategize.

## Rewards

| Outcome          | Reward for Player | Reward for Opponent |
|------------------|:-----------------:|:-------------------:|
| **Win**          | `+1`              | `-1`                |
| **Lose**         | `-1`              | `+1`                |
| **Invalid**      | `-1`              | `0`                 |

## Variants

| Env-id                  |
|-------------------------|
| `UltimateTicTacToe-v0`  |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg