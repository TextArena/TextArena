# JoJoJoin

Two players take turns placing marks on a 5×5 board; the first to get four of their own marks in a row
horizontally, vertically or diagonally wins.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `JoJoJoin-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `JoJoJoin-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `■` and moves first; Player 1 plays `▲`.
- On your turn, place your mark on any empty cell. There is no gravity, and edges do not wrap.
- Four consecutive marks of yours in a row, column or diagonal win immediately.
- If all 25 cells fill up without a line of four, the game is a draw.

Random self-play wins about 52% of games for the first player, 41% for the second and draws 7%, so alternate seats
when evaluating.

## Actions

Reply with the number of an empty cell. Cells are numbered left to right, top to bottom:

```
  0 |  1 |  2 |  3 |  4
  5 |  6 |  7 |  8 |  9
 10 | 11 | 12 | 13 | 14
 15 | 16 | 17 | 18 | 19
 20 | 21 | 22 | 23 | 24
```

Example: `12` marks the centre cell.

## Observations

Each player first receives the rules and their symbol. Before every move, the acting player sees the board (empty
cells show their number) and the list of available cells. Both players see every placement.

## Rewards

| Outcome | Reward |
| --- | --- |
| Four in a row | Winner `+1`, loser `-1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
