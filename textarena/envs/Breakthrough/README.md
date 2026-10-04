# Breakthrough

Two players race rows of pawn-like pieces across a square board; the first to reach the opponent's home row, or to
capture every opposing piece, wins ([rules](https://en.wikipedia.org/wiki/Breakthrough_%28board_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Breakthrough-v1` | `board_size=8`, `is_open=True` |
| `Breakthrough-v1-blind` | `board_size=8`, `is_open=False` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Breakthrough-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Breakthrough-v1", board_size=...)`.
<!-- END GENERATED: variants -->

## Rules

- Each side starts with its two home rows full of pieces: Player 0 is White (`W`) on rows 1 and 2 and moves up;
  Player 1 is Black (`B`) on the top two rows and moves down. White moves first.
- On your turn, move one of your pieces one square straight forward or diagonally forward.
- A straight move needs an empty square. A diagonal move goes to an empty square or captures an opposing piece there;
  pieces never capture straight ahead. Capturing is never compulsory.
- Reaching the opponent's home row (the far edge) wins immediately, and so does capturing every opposing piece.
- There are no draws. Every move advances a piece, so the game always ends, and a player with pieces always has a legal
  move: the rearmost piece can always step or capture diagonally.

## Actions

Reply with the starting square followed by the destination square, with no space: a column letter (`a` is the
leftmost) and a row number (`1` is White's home row). Input is case-insensitive. On a 5×5 board:

```
 5 | B B B B B
 4 | B B B B B
 3 | . . . . .
 2 | W W W W W
 1 | W W W W W
     a b c d e
```

Examples: `a2a3` moves White's piece straight up from `a2`; `c2b3` moves diagonally; on a 5×5 board, `a4a3` moves one
of Black's front pieces straight down.

## Observations

Each player first receives the rules, including the starting setup. In the open variants, the acting player sees the
board before every move, with rows printed from the top (Black's home row) down to row 1. Both players see every move,
for example `Player 0 moves a2a3 (W).` When `is_open` is off, no board is ever shown: players have to track the position
from the starting setup and the announced moves. Legal moves are not listed.

## Rewards

| Outcome | Reward |
| --- | --- |
| A piece reaches the opponent's home row | Winner `+1`, loser `-1` |
| All opposing pieces captured | Winner `+1`, loser `-1` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `is_open` (default `True`): Whether the acting player is shown the board before each move.
- `board_size` (default `8`): The side length of the board. Accepts an integer from 4 to 26.
<!-- END GENERATED: parameters -->

## Notes

- Breakthrough was invented by Dan Troyka in 2000.
