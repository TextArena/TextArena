# Simple Tak

Two players take turns placing stones on a square grid; the first to connect two opposite edges with an orthogonally
connected path of their own stones wins.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `SimpleTak-v0` | `board_size=4` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SimpleTak-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("SimpleTak-v0", board_size=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 plays `O` and moves first; Player 1 plays `X`.
- On your turn, place one stone on any empty cell. Stones never move or get captured.
- A path of your stones that joins the top and bottom edges, or the left and right edges, wins immediately. Both
  players may connect in either direction.
- Stones connect only horizontally or vertically; diagonal neighbours do not count.
- If the board fills up without a path, the game is a draw.

## Actions

Reply with the number of an empty cell. Cells are numbered from 0, left to right and top to bottom; on a 4×4 board:

```
+----+----+----+----+
| 0  | 1  | 2  | 3  |
+----+----+----+----+
| 4  | 5  | 6  | 7  |
+----+----+----+----+
| 8  | 9  | 10 | 11 |
+----+----+----+----+
| 12 | 13 | 14 | 15 |
+----+----+----+----+
```

Example: `5` places a stone on row 1, column 1 of a 4×4 board.

## Observations

Each player first receives the rules and their symbol. Before every move, the acting player sees the board (empty cells
show their number) and the list of available cells. Both players see every placement.

## Rewards

| Outcome | Reward |
| --- | --- |
| Connecting path | Winner `+1`, loser `-1` |
| Full board, no path | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `board_size` (default `5`): side length of the board; a positive integer.

## Notes

- This is a placement-only reduction of [Tak](https://en.wikipedia.org/wiki/Tak_%28game%29): there are no walls,
  capstones, stacks, or moves. Because only orthogonal connections count, a full board can leave both players without a
  path, so draws are possible.
