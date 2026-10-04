# Colonel Blotto

Each round, two commanders secretly split the same number of units across several battlefields; whoever wins more
battlefields takes the round, and whoever wins more rounds takes the game
([background](https://en.wikipedia.org/wiki/Blotto_game)). There is no communication: players can only learn from the
allocations revealed after each round.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `ColonelBlotto-v0` | `num_fields=3`, `num_total_units=20`, `num_rounds=9` |
| `ColonelBlotto-v0-large` | `num_fields=5`, `num_total_units=50`, `num_rounds=15` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ColonelBlotto-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("ColonelBlotto-v0", num_fields=...)`.
<!-- END GENERATED: variants -->

## Rules

- Player 0 is Commander Alpha and Player 1 is Commander Beta. The battlefields are labelled `A`, `B`, `C`, … (one letter
  per field).
- Every round, both commanders allocate exactly `num_total_units` units across the fields; fields left out get 0
  units. Units do not carry over, so each round starts with the full amount.
- Allocations are sealed: Alpha submits first, then Beta, and neither sees the other's allocation until the round is
  resolved.
- A field goes to the commander with more units on it; equal units win it for nobody. The commander who wins more
  fields wins the round, and equal field counts tie the round. Because tied fields count for nobody, a round can be won
  with fewer than half of the fields.
- The game lasts up to `num_rounds` rounds. A commander who wins `num_rounds // 2 + 1` rounds (a majority of all
  rounds) wins immediately. Otherwise, after the last round the commander with more round wins wins, and equal round
  wins is a draw.

## Actions

Reply with one letter-and-number pair per field, separated by spaces or commas, e.g. `A7 B7 C6` for three fields and 20
units. Letters are case-insensitive and a colon is allowed (`a:7, b:7, c:6`). Omitted fields get 0 units, so `A20`
puts everything on field A.

The allocation is invalid if it names a field that does not exist, names a field twice, contains any other text, or
does not add up to exactly `num_total_units`.

## Observations

Each player first receives the rules, the fields, the number of units, and an example allocation that is legal for the
configuration. At the start of every round, both players see a status board with the round number, the rounds won by
each commander, the fields, the units to allocate, and the example. Your own allocation is echoed only to you. Once both commanders
have allocated, both see every field's allocation for both sides and the round winner (or that the round was tied).

## Rewards

| Outcome | Reward |
| --- | --- |
| Majority of `num_rounds` won, or more round wins after the last round | Winner `+1`, loser `-1` |
| Equal round wins after the last round | Both `0` |
| Second consecutive invalid allocation | Offender `-1`, opponent `+1` |

## Parameters

- `num_fields` (default `3`): number of battlefields, from 2 to 26.
- `num_total_units` (default `20`): units each commander allocates every round; at least `num_fields`.
- `num_rounds` (default `10`): maximum number of rounds.

## Notes

- The early win only triggers at a majority of all rounds. When tied rounds settle the result earlier (for example 4–0
  with two tied rounds out of nine), play continues until a commander reaches the majority or the last round is played.
- Reference: Émile Borel, "The Theory of Play and Integral Equations with Skew Symmetric Kernels", *Econometrica* 21(1),
  1953, pp. 97–100, [doi:10.2307/1906946](https://doi.org/10.2307/1906946).
