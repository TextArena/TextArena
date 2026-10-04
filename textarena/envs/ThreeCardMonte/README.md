# Three Card Monte

Track a ball hidden under one of several cups through a series of announced swaps, then name the cup it ends up under
([shell game](https://en.wikipedia.org/wiki/Shell_game)). Every swap is shown, so this is a pure test of state
tracking: perfect bookkeeping always wins.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `ThreeCardMonte-v0` | `num_cups=3`, `steps=10` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ThreeCardMonte-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("ThreeCardMonte-v0", num_cups=...)`.
<!-- END GENERATED: variants -->

## Rules

- There are `num_cups` cups numbered from 0. At reset, the ball is placed under a random cup, and its starting
  position is shown.
- The game then makes `steps` swaps. Each swap exchanges two different cups chosen at random, and the ball moves with
  its cup. Every swap is announced.
- You get one guess, which ends the game: name the cup the ball is under now.
- A reply that is not a cup number, or a number outside the range, is an invalid move. Two invalid moves in a row end
  the game.

## Actions

Reply with a cup number, e.g. `1`.

## Observations

The whole puzzle arrives in the first observation: the instructions, the starting position with the ball shown as
`[X]` (for example `Ball starts: [0] [X] [2]`), every swap (such as `Shuffle 3/10: swapped cups 1 and 2.`), and the
row of cup numbers to choose from. After the guess, the ball's final position is revealed.

## Rewards

| Outcome | Reward |
| --- | --- |
| Correct cup | `1` |
| Wrong cup | `0` |
| Second consecutive invalid move | `0` |

## Parameters

- `num_cups` (default `3`): the number of cups, at least 3.
- `steps` (default `10`): the number of swaps, 0 or more.

## Notes

- Despite the name, the game is played with cups and a ball, like the shell game, rather than with cards.
