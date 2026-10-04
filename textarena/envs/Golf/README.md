# Golf Environment Documentation

## Overview
**Golf** simulates the 6-card version of the classic card game *Golf*. Players are each dealt a 2×3 grid of face-down cards, and take turns drawing from the deck or discard pile to swap and reveal cards in their grid. The objective is to minimize your score by forming low-value combinations and vertical pairs (which cancel out).

The game ends when all players have all 6 of their cards revealed. The player with the lowest total score wins the round.

## Gameplay

- **Players:** 2 to 4 (supports both two-player and multi-player modes)
- **Initial Setup:** Each player is dealt 6 cards in a 2×3 grid, with 2 of those cards revealed at a random order.
- **Objective:** Minimize your total score by revealing and swapping cards strategically. Vertical pairs (same value in the same column) cancel to 0 points.

## Card Values

| Card       | Value  |
|------------|--------|
| Ace (A)    | 1      |
| 2–10       | Face value |
| Jack (J)   | 10     |
| Queen (Q)  | 10     |
| King (K)   | 0      |

## Actions

Submit exactly one bare command:

- **Draw Phase (must choose one of):**
  - `draw` — Draw a face-down card from the deck.
  - `take` — Take the top card from the discard pile.

- **Action Phase (after drawing a card):**
  - `swap X Y` — Swap the drawn card into position at **row X, column Y**.
  - `discard` — Discard the drawn card instead of swapping it (*only allowed if drawn from deck*).

- **Optional:**
  - `peek X Y` — Peek at a face-down card at position (X, Y).
  - `knock` — Declare the final round. Each opponent gets one more turn.

**Note:** Players may not see the value of face-down cards before swapping.

## Grid Reference

Each player's grid is displayed as a 2×3 layout:

```python
  Col:  1  2  3
Row 1:  ?  4♠ ?
Row 2:  ?  K♣ ?
```

Cards marked `?` are faced-down. You must use coordinates (row, column) when swapping. 

## End Condition
- If a player finished revealing all 6 cards first, then the other players get one final turn. 

## Rewards

| Outcome                        | Reward for Player |
|--------------------------------|-------------------|
| **Win (lowest score)**         | `+1`              |
| **Lose**                       | `-1`               |
| **Invalid Move**               | `-1`              |

## Observation Space

- Players receive prompts indicating available actions and the current board.
- Prompts include the visible portion of the player's hand, discard pile, and any drawn card they must act on.

## Example Moves

- `draw` → Draw a card from the deck.
- `take` → Take the top discard.
- `swap 2 1` → Place the drawn card at Row 2, Column 1.
- `discard` → Discard the drawn card (if drawn from deck).

## Available Environments

| Env-id           | Mode          |
|------------------|---------------|
| `Golf-v0`        | 2 players     |

## Contact

For issues or feedback related to this environment, contact `chengxy@i2r.a-star.edu.sg`.
