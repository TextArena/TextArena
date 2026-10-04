# Iterated Two-Thirds of the Average

Each round, two players simultaneously guess a number and the guess closer to two-thirds of the average of both guesses
wins the round; whoever wins more rounds wins the game
([background](https://en.wikipedia.org/wiki/Guess_2/3_of_the_average)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `IteratedTwoThirdsAverage-v0` | `num_rounds=10`, `min_guess=0.0`, `max_guess=100.0` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedTwoThirdsAverage-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Each round, both players guess a number from `min_guess` to `max_guess` (inclusive); decimals are allowed. Guesses
  are sealed: Player 0 guesses first, but neither sees the other's guess until both are in.
- The target is two-thirds of the average of the two guesses, `(2/3) × (guess₀ + guess₁) / 2`. The guess closer to the
  target wins the round; equal distances tie it.
- After `num_rounds` rounds, the player who won more rounds wins; equal round wins is a draw.

## Actions

Reply with a plain number, e.g. `42`, `33.5`, or `1e1`; a sign is allowed, so `-2` works when `min_guess` is negative.
The number must be finite and between `min_guess` and `max_guess`; anything else is invalid.

## Observations

Each player first receives the number of rounds, the allowed range, and the rules. Guesses are never echoed, not even
to the player who made them. Once both guesses are in, both players see both guesses, the target (rounded to two
decimals), the round winner or a draw, and the score after that round.

## Rewards

| Outcome | Reward |
| --- | --- |
| More round wins after `num_rounds` rounds | Winner `+1`, loser `-1` |
| Equal round wins | Both `0` |
| Second consecutive invalid guess | Offender `-1`, opponent `+1` |

## Parameters

- `num_rounds` (default `5`): number of rounds.
- `min_guess` (default `0.0`): smallest allowed guess; a finite number.
- `max_guess` (default `100.0`): largest allowed guess; a finite number not below `min_guess`.

## Notes

- With only two players, the guess closer to zero always wins: the target is a third of the sum of both guesses, so the
  smaller guess in absolute value is always closer (equal absolute values tie). With the default range, guessing `0`
  never loses a round.
