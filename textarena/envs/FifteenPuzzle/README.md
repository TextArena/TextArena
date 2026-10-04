# Fifteen Puzzle

Slide numbered tiles around a 4×4 board until they read 1 to 15 in order with the gap in the bottom-right corner
([rules](https://en.wikipedia.org/wiki/15_puzzle)). Every scramble is solvable within the move limit.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `FifteenPuzzle-v1` | `max_turns=200` |

Append `-mdp` to any ID for the state-complete variant (e.g. `FifteenPuzzle-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("FifteenPuzzle-v1", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, the solved board is scrambled by `min(max_turns, 100)` random slides, none of which undoes the slide before
  it. The scramble is therefore always solvable within the move limit. If the random walk happens to end on the
  solved board, one more slide is made, so the game never starts solved.
- On your turn, slide one tile next to the gap into it. The direction names the way the tile moves: `up` moves the
  tile below the gap up, `down` the tile above it down, `left` the tile to its right left, and `right` the tile to its
  left right.
- You win when tiles 1 to 15 read in order left to right, top to bottom, with the gap in the bottom-right corner.
- Every slide uses a turn, and the game ends after `max_turns` slides.
- A direction with no tile to slide (for example `up` when the gap is on the bottom row), an unknown direction, or a
  malformed reply is an invalid move. It changes nothing, but two invalid moves in a row end the game.

## Actions

Reply with one of `up`, `down`, `left`, or `right` (case-insensitive).

Example: with the gap in the bottom row, `down` slides the tile above the gap down into it.

## Observations

The player first receives the rules and the move limit. Before every move, the player sees the board, with `__`
marking the gap, followed by the list of available moves:

```
 1 15 14 12
 5 13  3  8
 6  7  4  2
 9 __ 11 10

Available Moves: 'down', 'left', 'right'
```

## Rewards

Partial credit measures net progress on the 16 positions (the gap counts as one): each position that started wrong and
is now right counts +1, each position that started right and is now wrong counts −1, and the total is divided by the
number of positions that started wrong and floored at `0`. Only a solved board reaches `1`.

| Outcome | Reward |
| --- | --- |
| Puzzle solved | `1` |
| `max_turns` slides made | Partial credit (`0` to below `1`) |
| Second consecutive invalid move | Partial credit |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_turns` (default `50`): The maximum number of slides. It also sets the scramble length, `min(max_turns, 100)`. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->
