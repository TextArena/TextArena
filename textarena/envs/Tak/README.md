# Tak

Two players place and stack stones on a square board, racing to build a road of their own pieces that connects two
opposite edges ([rules](https://en.wikipedia.org/wiki/Tak_%28game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Tak-v0` | `board_size=4`, `stones=15`, `capstones=1`, `max_turns=100` |
| `Tak-v0-hard` | `board_size=6`, `stones=30`, `capstones=1`, `max_turns=200` |
| `Tak-v0-medium` | `board_size=5`, `stones=21`, `capstones=1`, `max_turns=150` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Tak-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The board is `board_size` × `board_size`. Each player has a reserve of `stones` stones and `capstones` capstones.
  Player 0 moves first.
- Pieces are written as a letter plus the owner's player id: a **flat stone** (`F0`, `F1`), a **wall** or standing
  stone (`W0`, `W1`), and a **capstone** (`C0`, `C1`). Every stone is placed either as a flat stone or as a wall.
- **Opening:** on each of the first two turns, the player places one of the *opponent's* flat stones (taken from the
  opponent's reserve) on an empty square. No stack may move during the opening.
- After that, on your turn you either:
  - **place** one of your pieces from your reserve on an empty square, or
  - **move** a stack whose top piece is yours: pick up 1 to `board_size` pieces from the top of the stack, travel in
    a straight line (up, down, left, or right), and drop at least one piece on every square you enter, starting next
    to the source. Pieces leave the bottom of the carried pile first, so the topmost carried piece ends up on the
    last square.
- Nothing can be stacked on a wall or a capstone, with one exception: a capstone dropped alone as the last piece of a
  move flattens a wall (of either player) into a flat stone. The top piece of a stack decides who controls it.
- **Road win:** a road is a path of orthogonally adjacent squares topped by your flat stones or capstones that joins
  the top and bottom edges or the left and right edges. A move that completes a road wins immediately. If one move
  completes roads for both players, the player who moved wins; if it completes only the opponent's road, the opponent
  wins.
- **Flat win:** otherwise, the game ends when the board is full or either player has no stones and capstones left in
  reserve. The player with more flat stones on top of stacks wins (walls, capstones, and covered pieces do not
  count); a tied count is a draw.
- **Turn limit:** after `max_turns` turns in total (every move by either player counts), the flat count decides the
  game the same way.

## Actions

Reply with one command (keywords and piece letters are case-insensitive). Squares are `(row,col)` pairs numbered from
0, with `(0,0)` in the top-left corner.

- `place () {(row,col): [piece]}` places one piece. During the opening the piece must be the opponent's flat stone.
- `move (row,col) {(row,col): [pieces], (row,col): [pieces], ...}` moves a stack. List the squares in travel order and,
  for each, the pieces dropped there from bottom to top. Read in order, the dropped pieces must equal the top of the
  source stack from bottom to top.

Examples for Player 0:

- `place () {(0,0): [F1]}` is a legal opening move (Player 1's flat stone on the top-left corner).
- `place () {(1,2): [W0]}` places a wall on row 1, column 2.
- `move (2,0) {(1,0): [F1], (0,0): [F0]}` carries the stack `F1/F0` (bottom to top) upward, dropping `F1` on `(1,0)`
  and `F0` on `(0,0)`.
- `move (0,2) {(0,1): [C0]}` carries only the capstone from `(0,2)` onto `(0,1)`; a wall standing there is flattened.

## Observations

Each player first receives the rules, including the board size, reserves, carry limit, and turn limit. Before every
move, the acting player sees the board, both players' remaining reserves, the number of turns played, and during the
opening which flat stone to place. Each square shows its stack height followed by its pieces from bottom to top, so
`(2) F1/W0` is a wall `W0` standing on a flat stone `F1`:

```
        0        1        2
     --------------------------
  0 | (1) F1 | (1) W0 |        |
     --------------------------
  1 |        |        |        |
     --------------------------
  2 |        |        | (1) F0 |
     --------------------------
```

Both players see every action and a description of it, such as
`Player 1 moved 2 pieces from (1,0): F1 to (1,1); C1 to (1,2), flattening the wall W0.` A rejected move is answered
with the reason, such as the opening rule, the carry limit, or a blocking wall. There is no hidden information. Legal
moves are not listed.

## Rewards

| Outcome | Reward |
| --- | --- |
| Road completed | Road owner `+1`, other player `-1` |
| Board full, a reserve empty, or `max_turns` reached | More flat stones on top `+1`, fewer `-1`; tied count both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `board_size`: side length of the board, from 3 to 8. It is also the carry limit.
- `stones`: stones per player (each placed as a flat stone or a wall); a positive integer.
- `capstones`: capstones per player; a non-negative integer.
- `max_turns` (default `100`): safeguard on the total number of turns, after which the flat count decides the game. It
  must be a positive integer.

## Notes

- Tak was designed by James Ernest and Patrick Rothfuss. Official piece counts are 10 stones on 3×3, 15 on 4×4, 21 plus
  1 capstone on 5×5, 30 plus 1 capstone on 6×6, 40 plus 2 capstones on 7×7, and 50 plus 2 capstones on 8×8. Official
  3×3 and 4×4 games use no capstone, so pass `capstones=0` for the standard small-board sets.
- Real Tak has no turn limit, and competitive play often adds komi (bonus flat-count points for the second player);
  this implementation has the turn limit and no komi.
