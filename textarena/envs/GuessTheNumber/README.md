# Guess The Number

Find a hidden integer within a limited number of guesses, using the higher-or-lower hint given after every wrong
guess. It tests systematic search, since halving the remaining range with each guess finds the target fastest.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt and every game message (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `GuessTheNumber-v1` | `min_number=1`, `max_number=20`, `max_turns=10` |
| `GuessTheNumber-v1-hardcore` | `min_number=1`, `max_number=50`, `max_turns=10` |

Append `-mdp` to any ID for the state-complete variant (e.g. `GuessTheNumber-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("GuessTheNumber-v1", min_number=...)`.
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

<!-- BEGIN GENERATED: parameters -->
- `min_number` (default `1`): The smallest possible target. It must not exceed `max_number`.
- `max_number` (default `20`): The largest possible target.
- `max_turns` (default `20`): The number of valid guesses allowed. Both registered variants use `10`. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- Binary search needs at most 5 guesses for the range 1–20 and 6 for 1–50, so both registered variants can always be
  solved within their 10 guesses.
- When the guesses run out, only the last guess counts toward the reward, not the closest one.
