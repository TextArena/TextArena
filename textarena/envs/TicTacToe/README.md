# Tic Tac Toe

Two players take turns marking cells of a 3×3 grid; the first to complete a row, column, or diagonal of their
own marks wins ([rules](https://en.wikipedia.org/wiki/Tic-tac-toe)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `TicTacToe-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `TicTacToe-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `O` and moves first; Player 1 plays `X`.
- On your turn, mark one empty cell.
- Three of your marks in a line (horizontal, vertical, or diagonal) wins immediately.
- If all nine cells are filled without a line, the game is a draw.

## Actions

Reply with the number of an empty cell. Cells are numbered left to right, top to bottom:

```
 0 | 1 | 2
---+---+---
 3 | 4 | 5
---+---+---
 6 | 7 | 8
```

Example: `4` marks the center cell.

## Observations

Each player first receives the rules and their symbol. Before every move, the acting player sees the board
(empty cells show their number) and the list of available cells. Both players see every placement.

## Rewards

| Outcome | Reward |
| --- | --- |
| Three in a row | Winner `+1`, loser `-1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
