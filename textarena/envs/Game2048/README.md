# 2048

Slide and merge numbered tiles on a square board to build a target tile, such as 2048
([rules](https://en.wikipedia.org/wiki/2048_%28video_game%29)). Variants change the target tile and the board size.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `2048-v0` | `target_tile=2048` |
| `2048-v0-3x3` | `target_tile=256`, `board_size=3` |
| `2048-v0-easy` | `target_tile=1024` |

Append `-mdp` to any ID for the state-complete variant (e.g. `2048-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("2048-v0", target_tile=...)`.
<!-- END GENERATED: variants -->

## Rules

- The board has `board_size` × `board_size` cells and starts with two tiles.
- Each move slides every tile as far as it can in one direction. Two equal tiles that collide merge into one tile with
  double the value, and a tile merges at most once per move. The score grows by the value of every tile created by a
  merge.
- After every move, a new tile appears in a random empty cell: a 2 nine times in ten and a 4 otherwise (only 2s when
  `target_tile` is 4).
- You win as soon as a tile reaches `target_tile`. You lose when the board is full and no merge is possible.
- A move that does not change the board, or a malformed reply, is an invalid move. It changes nothing (no tile
  appears), but two invalid moves in a row end the game.
- There is no turn limit. Every move adds a 2 or 4 to the board's total, which cannot grow forever without a win or a
  full board, so the game always ends. It can take long, though: the tiles must add up to at least the target, so
  reaching 2048 takes roughly 1,000 moves or more.

## Actions

Reply with one of `up`, `down`, `left`, or `right` (case-insensitive).

Example: `left` slides every tile toward the left edge.

## Observations

The player first receives the rules, the board size, and the target tile. Before every move, the player sees the
score, the board with `.` in empty cells, and the moves that would change the board:

```
Score: 0
+---------------------------+
|  .      .      .      .   |
|  .      .      4      .   |
|  .      .      .      .   |
|  2      .      .      .   |
+---------------------------+
Available moves: up, down, left, right
```

## Rewards

Unless you reach the target, you score the progress of your largest tile on a log scale:
`(log₂ M − log₂ M₀) / (log₂ target_tile − log₂ M₀)`, where `M` is the largest tile on the board and `M₀` the larger of
the two starting tiles. Every doubling of the largest tile earns the same share, the starting board scores `0`, and
the score stays below `1` until the target is reached. The score shown above the board does not count. For example,
with `target_tile` 2048 and a starting 2, a 256 tile scores `0.7` and a 1024 tile `0.9`.

| Outcome | Reward |
| --- | --- |
| Target tile reached | `1` |
| Board full with no merge possible | Partial credit (`0` to below `1`) |
| Second consecutive invalid move | Partial credit |

## Parameters

- `target_tile` (default `2048`): the tile that wins, a power of two from 4 to 65,536.
- `board_size` (default `4`): the board's side length, from 2 to 10.

## Notes

- A board with *n* cells can hold at most a 2<sup>*n*+1</sup> tile, even with lucky 4s, so 1024 is the largest tile
  possible on 3×3, and the 256 target of `2048-v0-3x3` can be reached.
