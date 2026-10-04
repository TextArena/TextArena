# Quantum Tic-Tac-Toe

Tic-tac-toe in which every move places a pair of entangled "spooky" marks that only turn into ordinary marks when a
cycle of entanglements collapses ([rules](https://en.wikipedia.org/wiki/Quantum_tic-tac-toe)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `QuantumTicTacToe-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `QuantumTicTacToe-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `O` and moves first; Player 1 plays `X`. Marks are numbered by move, so `O` always has odd numbers
  (`O1`, `O3`, …) and `X` even ones (`X2`, `X4`, …).
- On your turn, place one spooky mark in two different open cells (cells that have not collapsed). The two cells are
  entangled. A cell can hold any number of spooky marks.
- When a move closes a cycle of entangled cells (for example, a second mark in the same two cells), the cycle collapses
  at once. The mark just placed becomes a classical mark in the lower-numbered of its two cells. Every other spooky
  mark in a collapsing cell is pushed into its other cell, and so on, until every mark connected to the cycle is
  classical. Collapsed cells are permanent.
- If a collapse leaves exactly one open cell, that cell is filled with the next player's classical mark.
- Three classical marks of your symbol in a row, column, or diagonal win. If one collapse completes lines for both
  players, the player whose line has the lower highest move number wins. A full board without a line is a draw.

## Actions

Reply with two different open cells separated by a comma. Cells are numbered left to right, top to bottom:

```
 0 | 1 | 2
---+---+---
 3 | 4 | 5
---+---+---
 6 | 7 | 8
```

Example: `0,4` places a spooky mark in cells 0 and 4. Spaces around the comma are fine, and the order of the two
cells does not matter.

## Observations

Each player first receives the rules and their symbol. Before every move, the acting player sees the board, with
classical marks such as `X6` in the grid and open cells shown by their number, followed by every spooky mark and its
two cells (for example `O1 in cells 0 and 4`) and the list of open cells. Both players see every placement and every
collapse, reported with the same cell numbers.

## Rewards

| Outcome | Reward |
| --- | --- |
| Three classical marks in a row | Winner `+1`, loser `-1` |
| One collapse completes lines for both players | Lower highest move number `+1`, other `-1` |
| Full board, no line | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

Every game ends within nine moves, so the 25-turn limit (a draw) is never reached.

## Notes

- In Allan Goff's original game, the player who did *not* close a cycle chooses which of its two possible collapses
  happens, and when both players complete a line the earlier line scores 1 point and the later ½. Here the collapse
  is automatic, as described above, and the earlier line is simply a win.
