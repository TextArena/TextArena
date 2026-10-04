# Guess The Number

Find a hidden integer within a limited number of guesses, using the higher-or-lower hint given after every wrong
guess. It tests systematic search, since halving the remaining range with each guess finds the target fastest.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `GuessTheNumber-v0` | `min_number=1`, `max_number=20`, `max_turns=10` |
| `GuessTheNumber-v0-hardcore` | `min_number=1`, `max_number=50`, `max_turns=10` |

Append `-mdp` to any ID for the state-complete variant (e.g. `GuessTheNumber-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a target is drawn uniformly at random from `min_number` to `max_number` (inclusive).
- Each turn, guess one integer in that range. A correct guess wins immediately.
- After a wrong guess, you are told whether the target is higher or lower than your guess and how many guesses you
  have left.
- A number outside the range, a number you have already guessed, or anything other than a single integer is an
  invalid move. It does not use a guess, but two invalid moves in a row end the game.
- If the target has not been found after `max_turns` guesses, the game ends.

## Actions

Reply with a single integer, e.g. `10`. A leading `+` or `-` sign is accepted.

## Observations

The player first receives the rules, including the range and the number of guesses. After each wrong guess, a message
such as `Your guess 10 is too high: the target number is lower. Guesses left: 9.` follows. The target is revealed only
when the game ends.

## Rewards

| Outcome | Reward |
| --- | --- |
| Correct guess | `1` |
| `max_turns` guesses without finding the target | `1 - d / (max_number - min_number)`, where `d` is the distance between the last guess and the target (at least `0`, below `1`) |
| Second consecutive invalid move | The same score for the last valid guess, or `0` if no valid guess was made |

## Parameters

- `min_number` (default `1`) and `max_number` (default `20`): the inclusive range of the target; any integers with
  `min_number <= max_number`.
- `max_turns` (default `20`): the number of valid guesses allowed. Both registered variants use `10`.

## Notes

- Binary search needs at most 5 guesses for the range 1–20 and 6 for 1–50, so both registered variants can always be
  solved within their 10 guesses.
- When the guesses run out, only the last guess counts toward the reward, not the closest one.
