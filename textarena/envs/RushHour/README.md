# Rush Hour

Slide cars and trucks around a 6×6 parking lot to clear a path for the red car `X` and drive it out of the exit on the
right ([rules](https://en.wikipedia.org/wiki/Rush_Hour_%28puzzle%29)). Vehicles move one square per action, so it tests
planning a sequence of moves in a crowded grid.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `RushHour-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `RushHour-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, the red car `X` (two squares long, horizontal) is placed in the third row with a clear path to the exit,
  and up to seven other vehicles are placed around it: cars two squares long and trucks three squares long, each
  either horizontal or vertical. Random legal moves then scramble the lot: 12, 20, or 35 of them for `easy`,
  `medium`, or `hard`. Every move can be undone, so every puzzle is solvable.
- Each action slides one vehicle by one square along its own direction: horizontal vehicles move left or right,
  vertical vehicles up or down. Vehicles cannot overlap or leave the board, except that `X` leaves through the exit.
- You win when `X` drives through the exit: once `X` touches the exit, one more `X+` solves the puzzle.
- A letter that is not on the board, a blocked move, or a malformed reply is an invalid move. It changes nothing and
  does not count as a move. Two invalid moves in a row end the game.
- The game ends after `max_turns` valid moves.

## Actions

Reply with a vehicle letter followed by `+` or `-` (case-insensitive). `+` moves a horizontal vehicle right or a
vertical vehicle down; `-` moves it left or up.

Examples: `X+` moves the red car one square toward the exit; `C-` moves vehicle C one square left (if horizontal) or
up (if vertical).

## Observations

The player first receives the rules, including what `+` and `-` mean and the move limit. Before every move, the player
sees the board: each vehicle fills its squares with its letter, `.` is an empty square, and `>` marks the exit at the
right end of the third row. The board has no coordinates, since actions name vehicles.

```
A . . . . .
A . . . . .
. X X . . . >
. D D . . C
F F H H . C
. . . J J .
```

## Rewards

Unless you solve the puzzle, you score the share of the solution you have completed, counted in moves:
`(D − d) / D`, where `D` is the fewest moves that solve the starting position and `d` is the fewest that solve the
position you end in, both counting single-square moves and the final `X+` through the exit, and both found by an exact
search. The starting position scores `0`, and so does any position that is no closer to a solution, so moving a
vehicle back and forth earns nothing.

| Outcome | Reward |
| --- | --- |
| `X` drives out | `1` |
| `max_turns` valid moves made | Share of the solution completed, from `0` to below `1` |
| Second consecutive invalid move | Share of the solution completed, from `0` to below `1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `difficulty` (default `"medium"`): How scrambled the lot is: easy, medium and hard apply 12, 20 and 35 random moves. Accepts one of 'easy', 'medium', 'hard'.
- `max_turns` (default `100`): The number of valid moves allowed. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- Difficulty barely changes how hard the puzzles are. In a sample of 300 seeds per level, the shortest solutions took
  1 to 8 single-square moves at every level, and about one puzzle in ten could be solved in a single move, because the
  random scramble often undoes itself.
- Progress depends on what blocks `X`, not on how far right it is. With `X` one square from the exit and a vertical
  truck in the top three squares of the last column, `D = 5` (the truck drives down three squares, then two `X+`), and
  backing `X` up only makes `d` larger.
- On a puzzle that can be solved in a single move, any unfinished game scores `0`.
