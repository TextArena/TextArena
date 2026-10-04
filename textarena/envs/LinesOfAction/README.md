# Lines of Action

Claude Soucie's connection game: each piece moves exactly as far as there are pieces on its line, and the first
player to join all of their pieces into one connected group wins ([rules](https://en.wikipedia.org/wiki/Lines_of_Action)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LinesOfAction-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `LinesOfAction-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The board is 8×8. Player 0 (`O`) starts with six pieces on rank 8 and six on rank 1 (files b–g) and moves first;
  Player 1 (`X`) starts with six pieces on file a and six on file h (ranks 2–7). The corners start empty.
- On your turn, move one piece in a straight line (horizontally, vertically, or diagonally) exactly as many squares as
  there are pieces of either colour on that entire line, the moving piece included.
- You may jump over your own pieces but not over enemy pieces. You may not land on your own piece; landing on an
  enemy piece captures it.
- You win when all of your pieces form one group in which pieces touch horizontally, vertically, or diagonally. A
  player reduced to a single piece is connected. If a capture leaves both players connected, the player who moved
  wins; if it leaves only the opponent connected, the opponent wins.
- If you have no legal move, you must pass.
- The game is a draw after 60 consecutive moves (both players and passes counted) without a capture, or when the same
  position occurs for the third time with the same player to move.

## Actions

Reply with the from-square followed by the to-square, such as `b1b3` (case-insensitive). A space, `-`, `>`, or `->`
between the squares is also accepted (`b1 b3`, `b1-b3`). Files `a`–`h` run left to right and ranks `1`–`8` bottom
to top, as on the printed board. Reply `pass` only when you have no legal move.

## Observations

Each player first receives the rules and their piece symbol. Before every move, the acting player sees the board with
file and rank labels and the list of their legal moves (just `pass` when they have none). Both players see every move
and capture.

## Rewards

| Outcome | Reward |
| --- | --- |
| All your pieces connected | Winner `+1`, loser `-1` |
| 60 moves without a capture, or a position repeated three times | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Notes

- A simultaneous connection is a win for the player who moved, as in the second edition of Sid Sackson's *A Gamut of
  Games*; many tournaments score it as a draw instead.
- The 60-move and repetition draws are not part of the original rules; they guarantee that every game ends.
