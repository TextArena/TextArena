# Sokoban

Push every box onto a goal in a randomly generated warehouse, walking one square at a time and never pulling a box
([rules](https://en.wikipedia.org/wiki/Sokoban)). It tests planning ahead, since a box pushed into a corner or against
the wrong wall can never be recovered.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Sokoban-v0` | `dim_room=(6, 6)`, `max_turns=30`, `num_boxes=3` |
| `Sokoban-v0-medium` | `dim_room=(8, 8)`, `max_turns=50`, `num_boxes=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Sokoban-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a walled room with `num_boxes` boxes, as many goals, and the player is generated from the seed. The
  generator starts with every box on a goal and plays backwards, pulling boxes away, so every room is solvable. Every
  box starts off the goals, and every room can be solved within `max_turns` moves (and never needs more than 28).
- Each move walks one square up, down, left, or right. Walking into a box pushes it one square in the same direction,
  provided the square behind it is floor or an empty goal. You cannot pull a box or push two boxes at once.
- You win when every box is on a goal. Any box can go on any goal.
- Walking into a wall, pushing a box into a wall or another box, or a malformed reply is an invalid move. It changes
  nothing and does not count as a move. Two invalid moves in a row end the game.
- The game ends after `max_turns` valid moves. It does not detect stuck boxes, so a puzzle that can no longer be solved
  continues until then.

## Actions

Reply with one direction (case-insensitive): `up`, `down`, `left`, or `right`, or one of the aliases `w` (up), `a`
(left), `s` (down), and `d` (right).

Example: `left` (or `a`) walks one square left, pushing a box if one is there.

## Observations

The player first receives the rules, the board legend, and the move limit. Before every move, the player sees the
board and the accepted directions; after each valid move, they are told what happened, for example
`You moved up and pushed a box.`

```
# # # # # #
# # _ _ _ #
# P X O _ #
# _ O X _ #
# _ O X _ #
# # # # # #
```

| Symbol | Meaning |
| --- | --- |
| `P` | You |
| `+` | You, standing on an empty goal |
| `#` | Wall |
| `_` | Floor |
| `X` | Box |
| `O` | Empty goal |
| `√` | Box on a goal |

## Rewards

| Outcome | Reward |
| --- | --- |
| Every box on a goal | `1` |
| `max_turns` valid moves made | Fraction of boxes on goals |
| Second consecutive invalid move | Fraction of boxes on goals |

## Parameters

- `dim_room` (default `(6, 6)`): the room size as a `(rows, columns)` tuple. Both must be at least 4, with at most 400
  cells in total; the outer ring is always wall.
- `num_boxes` (default `3`): the number of boxes and goals. It must leave room for the player inside the outer walls.
- `max_turns` (default `100`): the number of valid moves allowed. Generated rooms are always solvable within it.
- `max_retries` (default `50`): the number of generation attempts (1 to 100) before `reset` gives up with
  `RuntimeError`.

## Notes

- The room generator (a random walk that carves the floor, then reverse play that pulls the boxes off their goals) is
  adapted from [gym-sokoban](https://github.com/mpSchrader/gym-sokoban). Undoing the pulls solves the room, so every
  generated room is solvable.
- Some custom settings cannot be generated, such as many boxes in a small room or a `max_turns` too small to move
  every box. `reset` then raises `RuntimeError` after `max_retries` attempts.
