# Bomberman

A turn-based two-player Bomberman: move around a walled arena, drop bombs that explode after a fixed number of
moves, and be the last player standing ([background](https://en.wikipedia.org/wiki/Bomberman)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Bomberman-v0` | `grid_size=10`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Bomberman-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The square arena is ringed by an indestructible wall (`#`) and has indestructible pillars wherever a cell's
  distances to the nearest outer wall are even in both directions (the classic every-second-cell lattice on odd
  sizes, mirrored on even sizes). Each remaining cell starts as a destructible wall (`+`) with probability
  `wall_density`. The arena is point-symmetric, and the 3×3 pocket around each spawn is clear.
- Player 0 starts at `(1, 1)`, Player 1 in the opposite corner. Players alternate moves, Player 0 first; a round is
  one move by each player.
- A move is one step up, down, left or right, staying put, or dropping a bomb on your own cell. You cannot step into
  a wall, a bomb or the other player, but you can walk off a bomb you are standing on. A blocked move is invalid and
  changes nothing.
- Bombs tick at the end of every move by either player. Counting the move that dropped it as move 1, a bomb explodes
  at the end of move `bomb_timer`. With the default fuse of 6, the player who dropped it gets 2 more moves to get
  clear and the opponent gets 3.
- A blast covers the bomb's cell and up to `bomb_radius` cells in each of the four directions. Indestructible walls
  stop it; a destructible wall in range is destroyed and also stops it. Blasts pass over other bombs without setting
  them off. Bombs that explode on the same move are resolved together against the walls as they stood before it.
- A player on a blast cell when it explodes is eliminated. Blast cells stay marked `*` for two moves so both players
  see them; the marks themselves are harmless.
- The last player standing wins. If both players are caught in the same explosion, or both are alive after
  `max_turns` rounds, the game is a draw.

## Actions

Reply with exactly one bare command (case-insensitive): `up`, `down`, `left`, `right`, `stay` or `bomb`. Positions
are `(x, y)`, where `x` is the column and `y` the row, so `up` decreases `y`.

## Observations

Each player first receives the rules. Before every move, the acting player sees the round counter, the board with
row and column numbers, both positions, and every bomb with the number of moves left until it explodes. Both
players see every move and explosion.

## Rewards

| Outcome | Reward |
| --- | --- |
| Opponent caught in an explosion | Winner `+1`, loser `-1` |
| Both players caught in the same explosion | Both `0` |
| `max_turns` rounds reached | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `grid_size` (default `10`): side length of the square arena, including the outer wall; an integer of at least 5.
- `max_turns` (default `100`): number of rounds (one move by each player) before the game is drawn.
- `bomb_timer` (default `6`): fuse length in moves, counting the move that drops the bomb.
- `bomb_radius` (default `2`): how far a blast reaches in each direction.
- `wall_density` (default `0.3`): probability, between 0 and 1, that a free cell starts as a destructible wall.
