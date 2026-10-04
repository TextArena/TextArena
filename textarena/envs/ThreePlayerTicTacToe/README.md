# Three-Player Tic Tac Toe

Three players take turns marking a 5×5 grid with their own symbol, and the first to get four in a row horizontally,
vertically, or diagonally wins. With two opponents, blocking one of them can open a line for the other.

<!-- BEGIN GENERATED: variants -->
**Players:** 3

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `ThreePlayerTicTacToe-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `ThreePlayerTicTacToe-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Players 0, 1, and 2 play `A`, `B`, and `C` and move in that order.
- On your turn, mark one empty cell with your symbol.
- Four of your symbols in a line (horizontal, vertical, or diagonal) win immediately; both other players lose.
- If all 25 cells are filled without a line of four, the game is a draw.
- Two invalid moves in a row end the game at once: the offender loses and both other players win.

## Actions

Reply with the number of an empty cell (0–24). Cells are numbered left to right, top to bottom:

```
  0 |  1 |  2 |  3 |  4
----+----+----+----+----
  5 |  6 |  7 |  8 |  9
----+----+----+----+----
 10 | 11 | 12 | 13 | 14
----+----+----+----+----
 15 | 16 | 17 | 18 | 19
----+----+----+----+----
 20 | 21 | 22 | 23 | 24
```

Example: `12` marks the center cell.

## Observations

Each player first receives the rules and their symbol. Before every move, the acting player sees the board (empty
cells show their number) and the list of available cells. Every player sees each placement, reported as a
`(row, column)` position. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Four in a row | Winner `+1`, both others `-1` |
| Full board, no line of four | All `0` |
| Second consecutive invalid move | Offender `-1`, both others `+1` |

## Notes

- The engine's default for repeated invalid moves would eliminate the offender and let the other two keep playing;
  this game instead ends immediately with a shared win for the two remaining players.
