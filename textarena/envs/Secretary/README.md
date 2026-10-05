# Secretary

See hidden values one at a time and decide on the spot whether to accept each one, winning only if you accept the
largest of them all ([secretary problem](https://en.wikipedia.org/wiki/Secretary_problem)). It tests optimal
stopping: the classic strategy skips the first `N/e` values (about 37%) and then accepts the first one that beats
everything seen so far.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt and the full transcript including every player action

| Env ID | Parameters |
| --- | --- |
| `Secretary-v1` | `N=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Secretary-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Secretary-v1", N=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, `N` values are drawn independently and uniformly between 0 and 1 and rounded to four decimals. They are
  revealed in order, one per turn, starting with the first.
- After each value is revealed, you either accept it, which ends the game, or continue to the next value. A skipped
  value cannot be recalled.
- When the last value is revealed, it is yours whichever reply you give.
- You win if the value you accept is the largest of all `N` values (a tie for the largest also wins).
- A malformed reply is an invalid move and does not count. Two invalid moves in a row end the game.
- There is no turn limit: the game always ends after at most `N` valid replies.

## Actions

Reply with `accept` or `continue` (case-insensitive).

## Observations

The player first receives the rules and the number of values. Each value is announced with its position, for example
`The current value (2 of 5) is 0.5442.`, and the last one adds that it will be taken whatever the reply. The player
sees only the values revealed so far and is not told how they are drawn. At the end, the result reveals the accepted
value and the largest value overall.

## Rewards

| Outcome | Reward |
| --- | --- |
| Accepted value is the largest (including the forced last value) | `1` |
| Accepted value is not the largest | `0` |
| Second consecutive invalid move | `0` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `N` (default `20`): The number of values. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- The values themselves make it easy to infer that they are uniform between 0 and 1, so a threshold strategy that
  uses the actual values can beat the classic rank-based `1/e` rule.
