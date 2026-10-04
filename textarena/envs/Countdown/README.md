# Countdown

Combine a handful of numbers with addition, subtraction, multiplication, and exact division to make a target, as in
the numbers round of the British game show Countdown
([rules](https://en.wikipedia.org/wiki/Countdown_%28game_show%29#Numbers_round)). It tests arithmetic search and
planning with a shrinking set of numbers.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Countdown-v0` | `numbers=[100, 75, 6, 4, 3, 2]`, `target=532` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Countdown-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Countdown-v0", numbers=...)`.
<!-- END GENERATED: variants -->

## Rules

- The registered `Countdown-v0` always uses the numbers `100 75 6 4 3 2` and the target 532. Without configured
  `numbers`, six are drawn at reset: two "large" numbers from 25, 50, 75, and 100, and four "small" numbers from two
  cards each of 1–10. Without a configured `target`, it is drawn from 100–999 and redrawn if it equals a starting
  number.
- Each move combines two different numbers on the board with `+`, `-`, `*`, or `/`. Both numbers are removed and the
  result is appended to the end of the list, so the list shrinks by one and the indices shift.
- Division must give a whole number. Unlike on the show, subtraction may produce zero or a negative number. Results
  must stay between −1,000,000 and 1,000,000.
- You win as soon as an operation produces the target. You do not have to use every number.
- The game also ends when only one number is left, which is after five moves with six numbers, or after `max_turns`
  valid moves.
- An index that is not on the board, the same index twice, division by zero, inexact division, a result out of range,
  or a malformed reply is an invalid move. It changes nothing and does not count as a move. Two invalid moves in a row
  end the game.

## Actions

Reply with `i j op`: the indices of two numbers on the board and one operator, separated by spaces (the operator may
follow the second index directly). It computes `(number i) op (number j)`, so the order matters for `-` and `/`.

Examples: `0 1 +` adds numbers 0 and 1; `4 2 -` subtracts number 2 from number 4.

## Observations

The player first receives the rules, the target, and the move limit. Before every move, the player sees the target,
the numbers with their indices and the expression each one came from, the best value so far and its expression, the
history of moves, and the current progress score:

```
TARGET: 532

Available numbers:
  [0] 6   (from: 6)
  [1] 4   (from: 4)
  [2] 3   (from: 3)
  [3] 2   (from: 2)
  [4] 175   (from: (100 + 75))

Best so far: 175 (distance: 357)
Best expression: (100 + 75)

Move history:
  1. 100 + 75 = 175
Current progress score: 0.174
```

## Rewards

Unless you make the target, you score the fraction of the starting gap you closed: `(d₀ − d) / d₀`, where `d₀` is
the distance from the target to the closest starting number and `d` is the distance from the target to `best`, the
value closest to the target that was ever on the board. Since `best` can be a starting number, the score is never
negative; it is `0` until a result gets closer than every starting number, and below `1` unless the target is made.

| Outcome | Reward |
| --- | --- |
| Target made | `1` |
| One number left without making the target | Progress, from `0` to below `1` |
| `max_turns` valid moves made | Progress, from `0` to below `1` |
| Second consecutive invalid move | Progress, from `0` to below `1` |

## Parameters

- `numbers` (default `None`): the starting numbers, 2 to 100 positive integers up to 1,000,000. `None` draws two large
  and four small numbers at reset.
- `target` (default `None`): a positive integer up to 1,000,000 that is not one of `numbers`. `None` draws a target
  from 100–999 at reset.
- `max_turns` (default `12`): the number of valid moves allowed. Each move uses up a number, so with six numbers the
  game always ends within five moves and the default limit is never reached.

## Notes

- Progress is measured against the starting numbers. In `Countdown-v0`, 100 is the closest starting number, 432 away
  from 532, so making 525 (7 away) scores `(432 − 7) / 432 ≈ 0.984`, and making no move scores `0`.
- Not every target can be made with the drawn numbers, as on the show.
