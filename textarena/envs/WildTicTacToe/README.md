# Wild Tic Tac Toe

Two players take turns placing either an X or an O on a 3×3 grid, and whoever completes a line of three identical
marks wins, no matter who placed the other two
([rules](https://en.wikipedia.org/wiki/Tic-tac-toe_variants#Wild_Tic-Tac-Toe)). Because both symbols are shared,
every move must avoid leaving the opponent a finishing move with either mark.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `WildTicTacToe-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `WildTicTacToe-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 moves first, and the players alternate.
- On your turn, place either an `X` or an `O` in any empty cell. Neither symbol belongs to a player.
- If your placement completes a line of three identical marks (horizontal, vertical, or diagonal), you win
  immediately, even if your opponent placed the other two.
- If all nine cells are filled without a line of three identical marks, the game is a draw.

## Actions

Reply with the mark and the number of an empty cell, separated by a space. The mark is case-insensitive. Cells are
numbered left to right, top to bottom:

```
 0 | 1 | 2
---+---+---
 3 | 4 | 5
---+---+---
 6 | 7 | 8
```

Examples: `X 4` places an X in the center cell; `o 0` places an O in the top-left cell.

## Observations

Each player first receives the rules. Before every move, the acting player sees the board (empty cells show their
number) and the list of available moves, which includes both marks for every empty cell. Both players see every
placement. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Completing a line of three identical marks | Mover `+1`, opponent `-1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |
