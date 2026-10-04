# Stratego

Two armies whose ranks are hidden from each other battle on a 10×10 board; capture the enemy Flag, or leave the opponent
without a legal move, to win ([rules](https://en.wikipedia.org/wiki/Stratego)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Stratego-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Stratego-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Each player has 40 pieces:

  | Piece | Board code | Rank | Count |
  | --- | --- | --- | --- |
  | Marshal | `MS` | 10 | 1 |
  | General | `GN` | 9 | 1 |
  | Colonel | `CL` | 8 | 2 |
  | Major | `MJ` | 7 | 3 |
  | Captain | `CP` | 6 | 4 |
  | Lieutenant | `LT` | 5 | 4 |
  | Sergeant | `SG` | 4 | 4 |
  | Miner | `MN` | 3 | 5 |
  | Scout | `SC` | 2 | 8 |
  | Spy | `SP` | 1 | 1 |
  | Bomb | `BM` | – | 6 |
  | Flag | `FL` | – | 1 |

- Armies are deployed automatically from the seed: Player 0 fills rows A–D and Player 1 rows G–J. The Flag goes on one
  of the two back rows with Bombs on its free orthogonally adjacent squares, the remaining Bombs go on the two front
  rows, and the other pieces are placed at random.
- Two 2×2 lakes in rows E–F (columns 2–3 and 6–7) can never be entered or crossed.
- Player 0 moves first. On your turn, move one piece one square up, down, left, or right onto an empty square or an
  enemy piece. A Scout may instead move any number of empty squares in a straight line, and may attack the first enemy
  piece in that line. Bombs and the Flag never move.
- A piece may not move back and forth between the same two squares more than three turns in a row; moving one of your
  other pieces resets the count.
- Moving onto an enemy piece starts a battle, and both ranks are revealed to both players. The higher rank wins and
  stays; equal ranks remove both pieces. Any piece attacking a Bomb is removed, except a Miner, which defuses it and
  takes its square. A Spy defeats the Marshal, but only when the Spy attacks. Attacking the Flag captures it and wins
  the game.
- A player who has no movable piece left, or no legal move on their turn, loses. If neither player has a movable piece
  left, the game is a draw.
- The game is a draw after `max_turns` turns in total (each player's move is one turn).

## Actions

Reply with the starting square and the destination square separated by a space. Squares are a row letter `A`–`J` (top
to bottom) followed by a column number `0`–`9` (left to right); input is case-insensitive.

Examples: `D4 E4` moves Player 0's piece on D4 one row down; `D5 G5` would be a Scout running through two empty squares
to attack the piece on G5.

## Observations

Each player first receives the rules, including the rank table. Before every move, the acting player sees the board
from their own side and the list of available moves: their pieces by code, opponent pieces as `?`, lakes as `~`, and
empty squares as `.`.

```
     0   1   2   3   4   5   6   7   8   9
A   CP  SC  CP  MN  MJ  SC  BM  CP  GN  SG
B   LT  SC  LT  MN  SC  BM  FL  BM  SC  SG
C   MN  SG  MS  CP  BM  CL  BM  SP  SC  SC
D   MN  SG  MJ  MJ  CL  SC  BM  MN  LT  LT
E    .   .   ~   ~   .   .   ~   ~   .   .
F    .   .   ~   ~   .   .   ~   ~   .   .
G    ?   ?   ?   ?   ?   ?   ?   ?   ?   ?
H    ?   ?   ?   ?   ?   ?   ?   ?   ?   ?
I    ?   ?   ?   ?   ?   ?   ?   ?   ?   ?
J    ?   ?   ?   ?   ?   ?   ?   ?   ?   ?

Available Moves: D0 E0, D1 E1, D4 E4, D5 E5, D5 F5, D5 G5, D8 E8, D9 E9
```

The opponent is told which squares a piece moved between, and battle results name both ranks; nothing else about hidden
pieces is revealed, and raw actions are echoed only to their author. A piece whose rank was revealed in battle is still
shown as `?` afterwards, so players have to remember it. When the game ends, the full board is revealed, with Player 0's
pieces in lowercase and Player 1's in uppercase.

## Rewards

| Outcome | Reward |
| --- | --- |
| Flag captured | Winner `+1`, loser `-1` |
| Opponent has no movable piece or no legal move | Winner `+1`, loser `-1` |
| Neither player has a movable piece | Both `0` |
| `max_turns` reached | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_turns` (default `1000`): total turns, counting both players, before the game is a draw. It must be a positive
  integer.

## Notes

- The rules follow classic Stratego; the draw when neither side can move comes from the International Stratego
  Federation rules.
- Not implemented: choosing your own deployment, and the more-squares (chasing) rule. For Scouts, the two-square rule
  only compares a move's start and end squares.
