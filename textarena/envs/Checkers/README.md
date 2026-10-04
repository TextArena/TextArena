# Checkers

Two players move pieces diagonally across an 8×8 board, capturing by jumping over opposing pieces, and win by capturing
or blocking every enemy piece ([rules](https://en.wikipedia.org/wiki/English_draughts)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Checkers-v0` | `max_turns=100` |
| `Checkers-v0-long` | `max_turns=300` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Checkers-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

This is English draughts (American checkers).

- Player 0 is Red (men `r`, kings `R`), starting on rows 5–7 and moving up; Red moves first. Player 1 is Black (men
  `b`, kings `B`), starting on rows 0–2 and moving down. Each side has 12 pieces on the squares where row + column is
  odd.
- A man moves one square diagonally forward onto an empty square. A king moves one square diagonally in any direction
  (kings do not fly).
- A capture jumps diagonally over an adjacent opposing piece onto the empty square right behind it, removing the jumped
  piece. Men capture only forward; kings capture in any diagonal direction.
- Captures are mandatory: if any capture is available, you must make one (any capture, not necessarily the longest
  sequence). After a capture, if the same piece can capture again, it must keep jumping; each jump is submitted as a
  separate move and the turn stays with you.
- A man that reaches the far row becomes a king. This ends the turn, even in the middle of a capture sequence.
- You win when your opponent has no pieces left or cannot move on their turn.
- The game is a draw after `max_turns` turns in total. Each player's move is one turn, and a whole multi-jump counts as
  one turn.

## Actions

Reply with four numbers, `rowFrom colFrom rowTo colTo`, using the row and column labels (0–7) shown on the board. For
a capture, the destination is the landing square.

```
     0  1  2  3  4  5  6  7
   +-------------------------
 0 | .  b  .  b  .  b  .  b
 1 | b  .  b  .  b  .  b  .
 2 | .  b  .  b  .  b  .  b
 3 | .  .  .  .  .  .  .  .
 4 | .  .  .  .  .  .  .  .
 5 | r  .  r  .  r  .  r  .
 6 | .  r  .  r  .  r  .  r
 7 | r  .  r  .  r  .  r  .
```

Examples: `5 0 4 1` is an opening move for Red; `2 1 3 2` is an opening move for Black; with a Black piece on `(4,3)`,
`5 2 3 4` jumps it.

## Observations

Each player first receives the rules, their symbols and direction, and the turn limit. Before every move, the acting
player sees the board; during a multi-jump, the board message names the piece that must jump again and lists its legal
jumps. Both players see every move (`Player 0 moved (5,0) -> (3,2).`) and every forced continuation. A rejected move is
answered with the reason; when it ignored a mandatory capture, the legal moves are listed too. There is no hidden
information. Otherwise legal moves are not listed.

## Rewards

| Outcome | Reward |
| --- | --- |
| Opponent has no pieces left or no legal move | Winner `+1`, loser `-1` |
| `max_turns` reached | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_turns` (default `50`): the number of turns, counting both players and treating a multi-jump as one turn, before
  the game is a draw. It must be a positive integer.

## Notes

- In official English draughts the dark pieces (Black) move first, and draws also come from agreement or repeated
  positions. Here Red moves first, and the turn limit is the only draw.
