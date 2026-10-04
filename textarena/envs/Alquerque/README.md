# Alquerque

A checkers ancestor on a 5×5 grid of points where pieces step forward along the lines and capture by jumping, and the
player who captures more within 60 moves wins ([rules](http://games.stanford.edu/gamemaster/homepage/viewgame.php?game=alquerque)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Alquerque-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Alquerque-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The board is a 5×5 grid of points. Lines join neighbouring points horizontally and vertically everywhere, and
  diagonally only through a1, c1, e1, b2, d2, a3, c3, e3, b4, d4, a5, c5, and e5 (the two long diagonals and the
  diamond through the edge midpoints).
- Red (`R`, Player 0) fills ranks 1–2 and moves first; Black (`B`, Player 1) fills ranks 4–5. Each side has 10
  pieces, and the middle rank starts empty.
- A normal move is one step forward along a line to an adjacent empty point: straight ahead, or diagonally ahead where
  a diagonal line exists. Forward is toward rank 5 for Red and toward rank 1 for Black; pieces never step sideways or
  backward.
- A capture jumps over an adjacent enemy piece along a line, in any direction, onto the empty point directly beyond,
  and removes the jumped piece. Captures are mandatory, and a piece that can capture again from where it lands must
  continue in the same move. You may choose among different capture sequences.
- Each captured piece scores 10 points.
- You lose at once if, on your turn, you have no pieces or no legal move. Otherwise the game ends after 60 moves in
  total (30 per player): the higher score wins, and equal scores draw.

## Actions

Reply with every point the piece visits, separated by spaces or `->` (case-insensitive): the start point, then each
landing point. Files `a`–`e` run left to right and ranks `1`–`5` bottom to top, as on the printed board.

Examples: `c2 c3` (a step), `c3 a3` (one capture), `c3 a3 c1` (two captures in one move).

Numeric point IDs are also accepted: `0` is a5, counting left to right and top to bottom to `24` (e1).

## Observations

Each player first receives the rules and their colour. Before every move, the acting player sees the move number, the
board (`R`, `B`, and `.` for empty), both scores, the number of moves left, and the list of their legal moves (only
complete capture sequences when a capture is available). Both players see every move, with the points visited and the
pieces captured.

## Rewards

| Outcome | Reward |
| --- | --- |
| Opponent has no pieces or no legal move on their turn | Winner `+1`, loser `-1` |
| 60 moves played, higher score | Winner `+1`, loser `-1` |
| 60 moves played, equal scores | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Notes

- Adapted from the Stanford General Game Playing version: 10 pieces each with an empty middle rank, forward steps, and
  10 points per capture. Captures are mandatory and chain as in traditional
  [Alquerque](https://en.wikipedia.org/wiki/Alquerque), where each side instead starts with 12 pieces and only the
  centre point is empty.
