# Reverse Tic Tac Toe

Two players take turns marking cells of a 3×3 grid, and the first to complete a row, column, or diagonal of their own
marks loses ([misère tic-tac-toe](https://en.wikipedia.org/wiki/Tic-tac-toe_variants#Misere_Tic-tac-toe)). With
perfect play the game is a draw, so the challenge is to avoid lines yourself while running your opponent out of safe
cells.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `ReverseTicTacToe-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `ReverseTicTacToe-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `O` and moves first; Player 1 plays `X`.
- On your turn, mark one empty cell with your symbol.
- Completing three of your own marks in a line (horizontal, vertical, or diagonal) loses immediately, and your
  opponent wins. This is checked before the full-board rule, so a ninth move that completes a line still loses.
- If all nine cells are filled without anyone completing a line, the game is a draw.

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

Each player first receives the rules and their symbol. Before every move, the acting player sees the board (empty
cells show their number) and the list of available cells. Both players see every placement. There is no hidden
information.

## Rewards

| Outcome | Reward |
| --- | --- |
| A player completes a line of their own marks | That player `-1`, opponent `+1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
