# BabyAI-Text Environment

## Overview
**BabyAI-Text** is the text-only version of [BabyAI](https://github.com/flowersteam/Grounding_LLMs_with_online_RL/tree/main/babyai-text/babyai) game. It's a one-player game where a goal is assigned to 
the player like "go to a yellow box". Player is in a grid (normally 8x8) containing some objects and the grid is 
described in text only. In each step only 6 actions are available.

## Action Space
- **Format:** Actions are strings each of which representing as below:
  - turn left: Turn agent direction 90 degrees to the left
  - turn right: Turn agent direction 90 degrees to the right
  - go forward: Go forward one cell
  - pick up: Pick up the item in the front cell
  - drop: Drop off the item into the front cell
  - toggle: Toggle or use they key for opening a door
- **Example:** 
    - `"[GAME] You are playing 'BabyAI-Text'.
Your goal is to go to a yellow box.
Available actions are turn left, turn right, go forward, pick up, drop, toggle.
... You see a yellow box 2 steps right. ... 
On your turn, simply type your selected action."`
    - `"[Player 1] turn right"`

## Observation Space

### Observations
The player receives a textual description of the game board, including their assigned goal and position of objects
relative to the position and direction of player in the board.

**Initial Observation:**
```plaintext
You are playing 'BabyAI-Text'.
Your goal is to {goal}.
Available actions are turn left, turn right, go forward, pick up, drop, toggle.
{Description of the board}.
On your turn, simply type your selected action.
```

**Turn Observation:**
After each step, players receive the updated description of the world. For example, after the first action in the
above game:
```plaintext
[GAME]: ... You see a yellow box 1 steps right. ...
```

**Board View**
<pre>
 ┌─── Game Board ───┐                              
 │ WQWQWQWQWQWQWQWQ │                              
 │ WQBB  KGAY    WQ │                              
 │ WQ    BG  AY  WQ │                              
 │ WQ    KP      WQ │                              
 │ WQ            WQ │                              
 │ WQKPBY<<      WQ │                              
 │ WQ          BGWQ │                              
 │ WQWQWQWQWQWQWQWQ │                              
 └──────────────────┘  
You see a wall 2 steps left. You see a purple key 2 steps forward. You see a yellow box 1 step forward. You see a purple key 2 steps right. You see a green box 3 steps right
</pre>
Each letter in the board is presenting some object or color according to the list below:
- W: Wall
- K: Key
- B: Box
- A: ball
- L: door
- Q: gray
- P: Purple
- Y: Yellow
- G: Green
- <<: Player (faced towards left)
## Gameplay
- **Players**: 1
- **Turns**: There's a limit of 20 on the number of turns the player can play.
- **Goal Assignment**: A goal is randomly selected at the start.
- **Position Assignment**: The player is randomly positioned in a cell with a random direction.
- **Objective**: Achieve the goal which is things like putting a ball next to a box.

## Key Rules
1. One-step Move:
    - In each step the player can move only one cell.
2. Inventory:
    - The player can pick up and carry only one object at a time.
3. Winning Conditions:
   - **Win:** Achieve the goal.
   - **Loss:** Failed to achieve the goal within the allowed max turns. 
4. Game Termination:
    - The game ends when player achieves the goal or after reaching the maximum allowed turns.



## Rewards
| Outcome          | Reward for Player | 
|------------------|:-----------------:|
| **Win**          | `+1`              | 
| **Lose**         | `-1`              | 
| **Draw**         | `0`               | 

## Parameters
- `max_turns` (`int`):
    - **Description**: Number of turns per player
    - **Impact**: Determines the number of the actions the player can perform.


## Variants

| Env-id             | max_turns |
|--------------------|:---------:|
| `BabyAiText-v0`    |   `20`    |


### Contact
If you have questions or face issues with this specific environment, please reach out to mr.hrezaei@gmail.com
