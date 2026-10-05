# Memory Game

Two players take turns turning over two face-down cards, keeping matching pairs and moving again after each match,
and whoever collects more pairs wins ([rules](https://en.wikipedia.org/wiki/Concentration_%28card_game%29)). Also
known as Concentration, it tests remembering every card that has been revealed, by either player.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `MemoryGame-v1` | `grid_size=4`, `max_turns=30` |
| `MemoryGame-v1-hard` | `grid_size=8`, `max_turns=80` |

Append `-mdp` to any ID for the state-complete variant (e.g. `MemoryGame-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("MemoryGame-v1", grid_size=...)`.
<!-- END GENERATED: variants -->

## Rules

- The board is a `grid_size`×`grid_size` grid of face-down cards in which every symbol appears exactly twice. Symbols
  are letters: `A` to `Z`, then `AA`, `AB`, and so on for larger grids.
- Player 0 goes first. On your turn, name two different face-down cards.
- If they match, you score a point, the pair stays face up, and you take another turn.
- If they do not match, both players are told the two symbols, the cards are turned face down again, and the turn
  passes to your opponent.
- Naming a face-up card, the same card twice, or a position outside the grid is an invalid move.
- When the last pair is matched, the player with more pairs wins; equal scores are a draw.
- Every attempt counts as a turn, including the extra turns earned by matching. After `max_turns` attempts in total
  (both players combined), the game ends and is decided by the current scores in the same way.

## Actions

Reply with `r1 c1 r2 c2`: the row and column of the first card, then of the second card, separated by spaces. Rows and
columns are numbered from 0.

Example: `0 1 1 0` turns over the card in row 0, column 1 and the card in row 1, column 0.

## Observations

Each player first receives the rules, including the turn limit. Before every turn, the acting player sees the board
(`.` for face-down cards, symbols for matched pairs), both scores, and, when there is a turn limit, the number of
turns played out of `max_turns`. The result of every attempt is announced to both players: which positions matched,
or, for a miss, the two positions and their symbols. Cards that have not been turned over are hidden from both
players.

## Rewards

| Outcome | Reward |
| --- | --- |
| All pairs matched, unequal scores | More pairs `+1`, fewer pairs `-1` |
| All pairs matched, equal scores | Both `0` |
| `max_turns` reached, unequal scores | Higher score `+1`, lower score `-1` |
| `max_turns` reached, equal scores | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `grid_size` (default `4`): The side length of the board, giving `grid_size² / 2` pairs. Accepts an even integer from 2 to 20.
- `max_turns` (default `100`): The total number of attempts by both players before the game is decided by score. `None` removes the limit, so the game only ends when every pair is matched. Accepts an integer of at least 1 or None.
<!-- END GENERATED: parameters -->

## Notes

- Both cards are named at once. Unlike the tabletop game, you cannot turn over one card, look at it, and then choose
  its partner.
