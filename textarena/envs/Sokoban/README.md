# Sokoban

Push every box onto a goal in a randomly generated warehouse, walking one square at a time and never pulling a box
([rules](https://en.wikipedia.org/wiki/Sokoban)). It tests planning ahead, since a box pushed into a corner or against
the wrong wall can never be recovered.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Sokoban-v1` | `dim_room=(6, 6)`, `max_turns=30`, `num_boxes=3`, `max_retries=100` |
| `Sokoban-v1-medium` | `dim_room=(8, 8)`, `max_turns=50`, `num_boxes=5`, `max_retries=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Sokoban-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Sokoban-v1", dim_room=...)`.
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

<!-- BEGIN GENERATED: parameters -->
- `dim_room` (default `(6, 6)`): The room size as (rows, columns); the outer ring is always wall. Accepts two integers of at least 4 with at most 400 cells in total.
- `num_boxes` (default `3`): The number of boxes and goals. It must leave room for the player inside the walls. Accepts an integer of at least 1.
- `max_turns` (default `100`): The number of valid moves allowed. Generated rooms are always solvable within it. Accepts an integer of at least 1.
- `max_retries` (default `100`): Generation attempts before reset gives up with RuntimeError. Accepts an integer from 1 to 100.
<!-- END GENERATED: parameters -->

## Notes

- The room generator (a random walk that carves the floor, then reverse play that pulls the boxes off their goals) is
  adapted from [gym-sokoban](https://github.com/mpSchrader/gym-sokoban). Undoing the pulls solves the room, so every
  generated room is solvable.
- Some custom settings cannot be generated, and `reset` then raises `RuntimeError` after `max_retries` attempts.
  Because the reverse play is limited to 28 moves, 7 or more boxes fail in any room size (6 boxes still generate in
  10×10 and 12×12 rooms). A small room with many boxes or a `max_turns` too small to move every box also fails.
- Only about one generation attempt in five succeeds, so the registered variants use the maximum of 100 attempts;
  with 50, about 1 seed in 30,000 to 200,000 failed.
