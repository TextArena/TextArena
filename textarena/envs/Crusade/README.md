# Crusade

Two armies of sixteen pieces that all move like chess knights try to capture as many enemy pieces as possible within
40 moves ([rules](http://games.stanford.edu/gamemaster/homepage/viewgame.php?game=crusade)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Crusade-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Crusade-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The board is 8×8. White (`W`, Player 0) fills ranks 1–2 and moves first; Black (`B`, Player 1) fills ranks 7–8.
- On your turn, move one of your pieces like a chess knight (two squares in one direction, then one square to the
  side), jumping over anything in between. It may land on an empty square or on an enemy piece, which is captured,
  but not on one of your own pieces.
- Each capture scores 1 point.
- Capturing all 16 enemy pieces wins at once. Otherwise the game ends after 40 moves in total (20 per player): the
  higher score wins, and equal scores draw.

## Actions

Reply with the source and target squares separated by a space (case-insensitive). Files `a`–`h` run left to right
and ranks `1`–`8` bottom to top, as on the printed board.

Example: `b1 c3`.

Numeric square IDs are also accepted: `0` is a8, counting left to right and top to bottom to `63` (h1), so `57 42`
is the same move as `b1 c3`.

## Observations

Each player first receives the rules and their colour. Before every move, the acting player sees the move number, the
board (`W`, `B`, and `.` for empty), both scores, the number of moves left, and the list of their legal moves. Both
players see every move, including captures.

## Rewards

| Outcome | Reward |
| --- | --- |
| Captured every enemy piece | Winner `+1`, loser `-1` |
| 40 moves played, higher score | Winner `+1`, loser `-1` |
| 40 moves played, equal scores | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Notes

- Ported from the Stanford General Game Playing game of the same name (same board, knight moves, and 40-move limit).
  There, each player's goal value grows with their own captures; here the game is zero-sum, so whoever captured more
  wins.
