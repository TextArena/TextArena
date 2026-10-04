# Stratego Environment Documentation

## Overview
**Stratego** is a two-player strategy board game where players aim to capture their opponent's Flag or eliminate all of their movable pieces. Each player strategically places their army, consisting of pieces of varying ranks, on a 10x10 grid, with special rules for movement and battle. Bombs act as immovable traps, while Scouts can move multiple spaces in a straight line. The game involves hidden information, where a player's pieces are unknown to their opponent until revealed in battle. This environment simulates the full rules of Stratego, including strategic placement, battle resolution, and dynamic board rendering, providing a robust setup for agent-based gameplay and experimentation.

## Action Space
- **Format:** Actions are strings representing the player's choice. For example:
- **Example:**
    - Move a piece from row 4, column 0 to an empty cell at row 5, column 0: `D0 E0`
    - Move a piece from row 5, column 8 into a battle with an opponent piece in row 5, column 9: `E8 E9`

## Observation Space
**Reset Observations**
On reset, each player receives a prompt containing their beginning game instructions. For example:
```plaintext
[GAME] You are Player 0. You are playing the Stratego game.
Your goal is to capture your opponent's Flag or eliminate all of their movable pieces.
At the start of the game, you have placed your army on the board, including your Flag, Bombs, and other pieces of varying ranks.

### Gameplay Instructions
1. **Movement Rules:**
   - On your turn, you can move one piece by one step to an adjacent square (up, down, left, or right).
   - Example: A piece can move from A1 to B1 or A1 to A2.
   - If the selected piece is a Bomb or a Flag, it cannot be moved.
   - **Scout Movement:** Scouts can move multiple steps in a straight line (horizontally or vertically).
       - Scouts cannot jump over any piece (your own or your opponent's).
       - Example: If there is a piece between the Scout and its destination, the Scout cannot move to the destination.
2. **Battles:**
   - If you move onto a square occupied by an opponent's piece, a battle will occur:
     - The piece with the higher rank wins and eliminates the opponent's piece.
     - If the ranks are equal, both pieces are removed from the board.
     - **Special Cases:**
       - Bombs eliminate most attacking pieces except Miners, which defuse Bombs.
       - Spies can defeat the Marshal if the Spy attacks first but lose to all other pieces.
3. **Strategic Goals:**
   - Identify your opponent's pieces through their movements and battles.
   - Protect your Flag while attempting to capture your opponent's Flag.
   - Use Scouts strategically to gain information about your opponent's pieces and attack weak ones.

### How to Make a Move:
1. Specify the coordinates of the piece you want to move and its destination.
2. Use the format `A0 B0`, where A0 is the source position and B0 is the destination.
   - Example: To move a piece from row 0, column 0 to row 1, column 0, input `A0 B0`.
3. Ensure the destination is valid according to the movement rules above.

### Important Notes:
- The board will show your pieces and their positions.
- The board will also show known positions of your opponent's pieces without revealing their ranks.
- Invalid moves will not be allowed. Plan carefully!

Here is the current board state:
     0   1   2   3   4   5   6   7   8   9
A   SG  SG  SC  LT  GN  LT  SC  LT  BM  MS 
B   MJ  LT  SC  MN  CP  MN  SG  BM  FL  BM 
C   MN  CP  CP  MN  SG  MN  SC  SP  BM  BM 
D   MJ  CL  SC  SC  SC  SC  MJ  CP  BM  CL 
E    .   .   ~   ~   .   .   ~   ~   .   . 
F    .   .   ~   ~   .   .   ~   ~   .   . 
G    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
H    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
I    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
J    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
```

**Step Observation**
After each step, the players receive the latest message from the game environment. For example, here's player 0 making its first move and the environment responds back:
```plaintext
[Player 0] D0 E0
[GAME] You have moved your piece from D0 to E0. Here is the updated board state:
     0   1   2   3   4   5   6   7   8   9
A   SG  SG  SC  LT  GN  LT  SC  LT  BM  MS 
B   MJ  LT  SC  MN  CP  MN  SG  BM  FL  BM 
C   MN  CP  CP  MN  SG  MN  SC  SP  BM  BM 
D    .  CL  SC  SC  SC  SC  MJ  CP  BM  CL 
E   MJ   .   ~   ~   .   .   ~   ~   .   . 
F    .   .   ~   ~   .   .   ~   ~   .   . 
G    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
H    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
I    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
J    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
```

And when player 0 made its move, the environment also informs player 1.
```plaintext
[GAME] Player 0 has moved a piece from D0 to E0. Here is the updated board state:
     0   1   2   3   4   5   6   7   8   9
A    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
B    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
C    ?   ?   ?   ?   ?   ?   ?   ?   ?   ? 
D    .   ?   ?   ?   ?   ?   ?   ?   ?   ? 
E    ?   .   ~   ~   .   .   ~   ~   .   . 
F    .   .   ~   ~   .   .   ~   ~   .   . 
G   SC  CL  MJ  SG  MN  MN  MS  MJ  LT  CP 
H   BM  SG  MJ  GN  BM  SC  SG  SC  SC  MN 
I   SC  SC  CL  LT  BM  SC  SP  CP  BM  LT 
J   LT  MN  SC  BM  FL  BM  SG  CP  CP  MN 
```

## Gameplay

- **Players**: 2  
- **Turns**: Players take turns moving one of their pieces or engaging in battles by moving onto a square occupied by an opponent's piece. Turns switch after the player completes their move or battle. Players must carefully strategize to protect their Flag and outwit their opponent.  

### Phases of a Turn

1. **Movement Phase**  
   - A player moves one piece to an adjacent square (up, down, left, or right).  
   - **Scouts** can move multiple squares in a straight line but cannot jump over other pieces or move diagonally.  
   - **Flags** and **Bombs** cannot move.  

2. **Battle Phase**  
   - If a player moves onto a square occupied by an opponent’s piece, a battle occurs:  
     - The higher-ranked piece wins and eliminates the opponent’s piece.  
     - If both pieces have the same rank, both are removed.  
     - **Special Rules**:
       - **Bombs** defeat all attackers except **Miners**, which can neutralize Bombs.  
       - **Spies** defeat the Marshal if they attack first but lose to all other pieces.  
   - The result of the battle is revealed to both players, and the ranks of the involved pieces are made known.  

3. **Observation Phase**  
   - After completing the turn, players assess revealed ranks and adjust their strategies for the next move.  

## Key Rules

- **Objective**:
  - The game is won by either:
    - Capturing the opponent’s **Flag**, or  
    - Eliminating all of the opponent's movable pieces, leaving them unable to make any moves.  

- **Piece Behavior**:
  - **Flag**: Cannot move and must be protected at all costs. Losing it results in defeat.  
  - **Bomb**: Cannot move and remains in place unless neutralized by a **Miner**. Acts as a defensive trap.  
  - **Scout**: Can move multiple squares in a straight line but cannot jump over other pieces. Ideal for reconnaissance and swift attacks.  
  - **Spy**: Specifically designed to defeat the Marshal but is vulnerable to all other pieces.  
  - **Other Pieces**: Ranked based on strength; higher-ranked pieces dominate in battles.  

- **Special Cases in Battles**:
  - **Bombs**: Automatically defeat attacking pieces unless the attacker is a **Miner**, which neutralizes the Bomb.  
  - **Spies vs. Marshal**: If a Spy attacks a Marshal, the Spy wins. However, the Spy loses if it is attacked by the Marshal.  

- **Winning Condition**:
  - **Win**: Capture the opponent's Flag or eliminate all their movable pieces.  
  - **Loss**: Lose your Flag or have no movable pieces left on the board. 

## Rewards

| Outcome          | Reward for Player | Reward for Opponent |
|------------------|:-----------------:|:-------------------:|
| **Win**          | `+1`              | `-1`                |
| **Lose**         | `-1`              | `+1`                |
| **Invalid**      | `-1`              | `0`                 |

## Variants

| Env-id                  |
|-------------------------|
| `Stratego-v0`           |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg