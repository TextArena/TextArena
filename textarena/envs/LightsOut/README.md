# Lights Out

Turn off every light on a square grid, where pressing a light toggles it and its four orthogonal neighbors
([rules](https://en.wikipedia.org/wiki/Lights_Out_%28game%29)). It tests reasoning about interacting toggles: the
order of presses does not matter, and pressing a light twice undoes it.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LightsOut-v0` | `size=5`, `max_turns=20` |

Append `-mdp` to any ID for the state-complete variant (e.g. `LightsOut-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("LightsOut-v0", size=...)`.
<!-- END GENERATED: variants -->

## Rules

- The grid is `size` × `size`. At reset, all lights start off and between 1 and `min(15, max_turns)` random presses
  are applied (plus one more if they happen to cancel out), so every puzzle can be solved within `max_turns` presses.
- Each move presses one light, which toggles it and the lights directly above, below, left, and right of it (fewer at
  edges and corners).
- You win when every light is off.
- A cell outside the grid or a malformed reply is an invalid move. It changes nothing and does not count as a move.
  Two invalid moves in a row end the game.
- The game ends after `max_turns` valid presses.

## Actions

Reply with `row col`: two 0-indexed numbers separated by a space or a comma.

Examples: `2 3` presses the light in row 2, column 3; `0 0` presses the top-left light.

## Observations

The player first receives the rules, the grid size, and the move limit. Before every press, the player sees the grid
with row and column labels (`O` is on, `.` is off), the number of presses made and remaining, and the completion
percentage:

```
Current grid state (Move 1, 19 moves remaining, 9.1% complete):
   0 1 2 3 4
0: . . O . .
1: . O O . .
2: . . . O O
3: O . . . O
4: O O O . .
```

## Rewards

Unless you solve the puzzle, you score your completion: the number of lights that were on at the start minus the
number on now, divided by the number on at the start, clamped between `0` and `1`.

| Outcome | Reward |
| --- | --- |
| All lights off | `1` |
| `max_turns` valid presses made | Completion, from `0` to below `1` |
| Second consecutive invalid move | Completion, from `0` to below `1` |

## Parameters

- `size` (default `5`): the width and height of the grid, from 1 to 20.
- `max_turns` (default `50`): the number of valid presses allowed. It also caps the number of scrambling presses at
  reset, so the puzzle stays solvable within the limit.

## Notes

- Completion measures how many fewer lights are on than at the start, not how close the grid is to a solution. A
  necessary press that turns more lights on lowers it, and it never goes below `0`.
