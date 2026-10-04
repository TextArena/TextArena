# Sudoku

Fill a 9×9 grid so that every row, column, and 3×3 box contains each digit from 1 to 9 exactly once, one cell per
turn ([rules](https://en.wikipedia.org/wiki/Sudoku)). Every puzzle has exactly one solution, and the number of starting
digits sets the difficulty.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Sudoku-v0` | `clues=60`, `max_turns=100` |
| `Sudoku-v0-easy` | `clues=70`, `max_turns=100` |
| `Sudoku-v0-hard` | `clues=20`, `max_turns=100` |
| `Sudoku-v0-medium` | `clues=40`, `max_turns=100` |
| `Sudoku-v0-very-easy` | `clues=75`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Sudoku-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a puzzle with exactly `clues` filled cells is generated. It starts from a known 17-clue puzzle with a
  unique solution, relabels the digits, shuffles rows within and between the three horizontal bands (and columns
  within and between the three vertical stacks), then reveals random cells of the solution until `clues` cells are
  filled. The puzzle therefore always has exactly one solution.
- On your turn, write one digit into an empty cell. A digit is accepted only if it is the solution's digit for that
  cell: placements are checked against the unique solution, not just against the digits already on the board.
- Filled cells, whether given or placed by you, cannot be changed.
- A rejected move (malformed reply, a number outside 1–9, a filled cell, a digit that repeats one in its row, column,
  or box, or a digit that does not match the solution) leaves the board unchanged and does not use a turn. The
  feedback says which of these applied. Two rejected moves in a row end the game.
- You win by filling the last empty cell. Otherwise the game ends after `max_turns` accepted digits. The registered
  variants allow 100, more than the at most 61 empty cells they start with.

## Actions

Reply with `row column digit`: three numbers from 1 to 9, separated by spaces or commas. Rows are numbered top to
bottom and columns left to right, as labeled on the board.

Examples: `5 3 7` writes a 7 in row 5, column 3; `9,1,4` writes a 4 in row 9, column 1.

## Observations

The player first receives the rules, the number of empty cells, and the turn budget. Before every move, the player
sees the grid with rows and columns labeled 1–9, the 3×3 boxes outlined, and `.` in empty cells. After a rejected
move, a message explains why, for example that row 1 already contains a 1, or that a digit does not conflict with the
board but is not the solution's digit for that cell.

## Rewards

| Outcome | Reward |
| --- | --- |
| Grid completed | `1` |
| `max_turns` digits placed without completing the grid | Fraction of the initially empty cells filled (`0` to below `1`) |
| Second consecutive rejected move | Fraction of the initially empty cells filled |

Because only correct digits are accepted, the fraction filled is also the fraction solved.

## Parameters

- `clues` (default `30`): the number of filled cells at the start, from 17 to 80. Fewer clues make a harder puzzle.
- `max_turns` (default `100`): the maximum number of accepted digits.

## Notes

- Every puzzle is a relabeled and shuffled copy of the same 17-clue base puzzle with extra solution cells revealed.
  The puzzles look different, but they share one underlying logical structure, and difficulty varies only with the
  number of clues.
- Checking each digit against the solution means a wrong guess is rejected immediately instead of surfacing later as
  a contradiction. A player can therefore test a guess at the cost of one warning, as long as the next move is
  accepted.
