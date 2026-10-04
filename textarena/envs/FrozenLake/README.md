# Frozen Lake

Walk from one corner of a frozen grid to the goal in the opposite corner without falling into a hole
([Gymnasium version](https://gymnasium.farama.org/environments/toy_text/frozen_lake/)). Unlike the Gymnasium version,
the ice is not slippery: every move goes exactly where you choose, so the challenge is reading the grid and planning a
safe route.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `FrozenLake-v0` | `size=4`, `num_holes=3`, `randomize_start_goal=False` |
| `FrozenLake-v0-hardcore` | `size=5`, `num_holes=6`, `randomize_start_goal=False` |
| `FrozenLake-v0-random` | `size=4`, `num_holes=3`, `randomize_start_goal=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `FrozenLake-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The lake is a `size` × `size` grid. You start in the top-left corner and the goal is in the bottom-right corner.
  With `randomize_start_goal=True`, you start in a random corner and the goal is in the diagonally opposite one.
- At reset, exactly `num_holes` holes are placed at random, but never on one randomly chosen shortest route from the
  start to the goal, so every grid can be crossed in the minimum `2 × (size − 1)` moves.
- Each move takes you one cell up, down, left, or right.
- Reaching the goal wins. Stepping onto a hole ends the game.
- Moving off the grid or a malformed reply is an invalid move: you stay where you are and it does not count as a
  move. Two invalid moves in a row end the game.
- The game ends after `max_turns` valid moves.

## Actions

Reply with one direction (case-insensitive): `up`, `down`, `left`, or `right`, or one of the aliases `w` (up), `a`
(left), `s` (down), and `d` (right).

Example: `down` (or `s`) moves you one row down.

## Observations

The player first receives the rules, the start and goal coordinates as `(row, column)`, and the move limit. Before
every move, the player sees the grid and the list of accepted commands. `P` marks you, `H` a hole, `G` the goal, and
an empty cell is safe ice:

```
+-----+-----+-----+-----+
|  P  |  H  |  H  |     |
+-----+-----+-----+-----+
|     |     |     |     |
+-----+-----+-----+-----+
|     |     |     |     |
+-----+-----+-----+-----+
|  H  |     |     |  G  |
+-----+-----+-----+-----+
```

After each move, the player is told their new position, for example `You moved down to position (1, 0).` The
holes are always visible.

## Rewards

Unless you reach the goal, you score your progress: `1 − d / D`, where `D = 2 × (size − 1)` is the length of the
shortest route from the start to the goal, and `d` is the number of steps from where you ended (including a hole)
to the goal, ignoring holes. Progress is capped at `0.95`.

| Outcome | Reward |
| --- | --- |
| Reach the goal | `1` |
| Fall into a hole | Progress, from `0` to `0.95` |
| `max_turns` valid moves made | Progress, from `0` to `0.95` |
| Second consecutive invalid move | Progress, from `0` to `0.95` |

## Parameters

- `size` (default `4`): the width and height of the grid, from 2 to 100.
- `num_holes` (default `3`): the exact number of holes, from 0 to `(size − 1)²`, which fills every cell off the safe
  route.
- `randomize_start_goal` (default `False`): start in a random corner instead of the top-left one, with the goal in the
  opposite corner.
- `max_turns` (default `100`): the number of valid moves allowed. It must be at least `2 × (size − 1)`, the length of
  the shortest route, so grids larger than 51 × 51 need a higher limit.

## Notes

- Falling into a hole is scored like stopping on that cell, so a hole next to the goal is worth more than a safe
  position far from it.
