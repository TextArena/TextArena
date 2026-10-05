# Minesweeper

Reveal every safe cell of a hidden minefield, using the count of neighboring mines shown on each revealed cell to work
out where the mines are ([rules](https://en.wikipedia.org/wiki/Minesweeper_%28video_game%29)). The first reveal is
always safe.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Minesweeper-v1` | `rows=8`, `cols=8`, `num_mines=10`, `max_turns=100` |
| `Minesweeper-v1-hard` | `rows=12`, `cols=12`, `num_mines=30`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Minesweeper-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Minesweeper-v1", rows=...)`.
<!-- END GENERATED: variants -->

## Rules

- The board has `rows` × `cols` cells and `num_mines` mines. The mines are placed when you make your first reveal,
  never on or next to the chosen cell, so the first reveal always opens a mine-free area.
- On your turn, reveal one hidden cell. A revealed cell shows how many of its eight neighbors contain mines. Revealing
  a `0` automatically reveals all of its neighbors, cascading through connected zeros.
- Revealing a mine ends the game.
- You win once every cell without a mine is revealed.
- Every reveal uses a turn, and the game ends after `max_turns` reveals. The registered limit of 100 is far more than a
  good player needs, since one `0` can open a whole region. Revealing numbered cells one at a time can still run out
  of turns on the 12×12 board, which has 114 safe cells.
- A cell outside the board, an already revealed cell, or a malformed reply is an invalid move. It changes nothing and
  does not use a turn, but two invalid moves in a row end the game.

## Actions

Reply with `row col`: the 0-indexed row and column of a hidden cell (as labeled on the board), separated by a space or
a comma.

Examples: `4 4` reveals the cell in row 4, column 4; `0,7` reveals the top-right cell of an 8×8 board.

## Observations

The player first receives the rules, the board size, the number of mines, and the turn limit. Before every move, the
player sees the board with rows and columns numbered from 0: `.` is a hidden cell and a digit is a revealed cell's
count of neighboring mines. A mine that ends the game is shown as `*` on the final board. After every reveal, a
message confirms the cell (`You revealed the cell at (4, 4).`) or reports the mine.

## Rewards

Partial credit is the fraction of safe cells revealed, not counting the area opened by the first reveal.

| Outcome | Reward |
| --- | --- |
| Every safe cell revealed | `1` |
| Mine revealed | Partial credit (`0` to below `1`) |
| `max_turns` reveals made | Partial credit |
| Second consecutive invalid move | Partial credit (`0` before the first reveal) |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `rows` (default `8`): The number of rows. The board can have at most 10,000 cells. Accepts an integer of at least 1.
- `cols` (default `8`): The number of columns. Accepts an integer of at least 1.
- `num_mines` (default `10`): The number of mines. It must leave room for the mine-free area around the first reveal, so it can be at most `rows × cols − 9` on boards of at least 3×3. Accepts an integer of at least 0.
- `max_turns` (default `100`): The maximum number of reveals. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- As in classic Minesweeper, a board can require guessing; the generator does not guarantee a board that logic alone
  can solve.
- There is no flag command. Flags are only a memory aid in Minesweeper, so they are not needed to win.
