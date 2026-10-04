# Slitherlink

Draw a single closed loop along the edges of a dot grid so that every numbered cell has exactly that many of its sides
on the loop ([rules](https://en.wikipedia.org/wiki/Slitherlink)). Edges are toggled one at a time by their dot
coordinates.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Slitherlink-v0` | `rows=4`, `cols=4`, `max_turns=200` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Slitherlink-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Slitherlink-v0", rows=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, a hidden solution loop is drawn: the outline of a random rectangle 2 to 4 cells wide and 2 to 4 cells tall.
  Each cell then shows, with probability 60%, how many of its four sides lie on that loop. At least one clue is always
  shown.
- Each move toggles one edge between two neighboring dots, drawing it if absent and erasing it if present.
- You win when every clue is satisfied and the drawn edges form exactly one closed loop: every dot touches zero or two
  drawn edges, and all drawn edges are connected. Any loop that meets the clues wins, not only the hidden rectangle.
- Every toggle uses a turn, and the game ends after `max_turns` toggles.
- An edge outside the board or a malformed reply is an invalid move. It changes nothing, but two invalid moves in a row
  end the game.

## Actions

Dots are numbered by row `0` to `rows` and column `0` to `cols`; cell `(r, c)` is the square whose top-left corner is
dot `(r, c)`.

- `h r c` toggles the horizontal edge from dot `(r, c)` to dot `(r, c+1)`, the top side of cell `(r, c)`, with `r` from
  0 to `rows` and `c` from 0 to `cols − 1`.
- `v r c` toggles the vertical edge from dot `(r, c)` to dot `(r+1, c)`, the left side of cell `(r, c)`, with `r` from
  0 to `rows − 1` and `c` from 0 to `cols`.

Examples on the 4×4 board: `h 0 0` toggles the top side of the top-left cell; `v 3 4` toggles the right side of the
bottom-right cell.

## Observations

The player first receives the rules, the coordinate scheme with the valid ranges, and the move limit. Before every
move, the player sees the board, with dot rows and columns labeled, `+` for dots, `───` and `│` for drawn edges, the
clue digits inside the cells, and `·` for cells without a clue. A line underneath shows the share of clues currently
satisfied (clues of `0` are satisfied by an empty board; this is not the partial credit):

```
    0   1   2   3   4

 0: +───+   +   +   +
      ·   2   ·   ·
 1: +   +   +   +   +
      ·   1   ·   1
 2: +   +   +   +   +
      1   2   1   ·
 3: +   +   +   +   +
      ·   1   ·   ·
 4: +   +   +   +   +

Clues satisfied: 0%
```

## Rewards

Unless you solve the puzzle, partial credit compares your edges with the hidden loop the puzzle was generated from:
`max(0, on − off) / L`, where `on` is the number of drawn edges on that loop, `off` the number of drawn edges not on
it, and `L` the loop's length. An empty board scores `0`, every wrong edge cancels a right one (so toggling edges at
random or drawing every edge earns nothing), and only a solved puzzle reaches `1`. The credit is computed when the game
ends and is never shown during play, since it would reveal the hidden loop.

| Outcome | Reward |
| --- | --- |
| A single loop satisfying every clue | `1` |
| `max_turns` toggles made | Partial credit (`0` to below `1`) |
| Second consecutive invalid move | Partial credit |

## Parameters

- `rows`, `cols` (defaults `4`, `4`): the grid size in cells, each at least 2, at most 10,000 cells in total.
- `max_turns` (default `200`): the maximum number of toggles.

## Notes

- Puzzles are not guaranteed to have a unique solution, and the hidden loop is always a rectangle. In a sample of 200
  seeds on the default 4×4 board, about half of the puzzles had more than one solution. Drawing any of them wins, but
  partial credit is measured against the hidden rectangle only, so an unfinished loop that follows a different
  solution can score less than its progress deserves.
