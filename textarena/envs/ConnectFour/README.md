# Connect Four

Two players take turns dropping discs into the columns of an upright grid; the first to line up four of their own
discs horizontally, vertically, or diagonally wins ([rules](https://en.wikipedia.org/wiki/Connect_Four)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `ConnectFour-v0` | `is_open=True`, `num_rows=6`, `num_cols=7` |
| `ConnectFour-v0-blind` | `is_open=False`, `num_rows=6`, `num_cols=7` |
| `ConnectFour-v0-large` | `is_open=True`, `num_rows=12`, `num_cols=15` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ConnectFour-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `X` and moves first; Player 1 plays `O`.
- On your turn, drop one disc into a column that is not full. It falls to the lowest empty cell of that column.
- Four of your discs in a line (horizontal, vertical, or diagonal) win immediately.
- If the board fills up without a line, the game is a draw.

## Actions

Reply with a column number, optionally prefixed with `col` (case-insensitive). Columns are numbered from `0` on the
left to `num_cols - 1` on the right.

Examples: `3`, `col 3`.

## Observations

Each player first receives the rules, their symbol, and the board size. Both players see a description of every move,
such as `Player 0 dropped their disk (X) into column 3.`

- Open variants (`is_open=True`): before every move, the acting player sees the board with column numbers and the
  list of columns that still have room.
- Blind variant (`is_open=False`): the board is never shown. Players only get the move descriptions and must track the
  position themselves; dropping into a full column is an invalid move.

## Rewards

| Outcome | Reward |
| --- | --- |
| Four in a row | Winner `+1`, loser `-1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `is_open` (default `True`): show the board before every move; `False` gives the blind variant.
- `num_rows` (default `6`) and `num_cols` (default `7`): board size, positive integers. A board shorter than four
  cells in both directions can only end in a draw.
