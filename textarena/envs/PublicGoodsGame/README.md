# Public Goods Game

Each round, players exchange public messages and then simultaneously decide how many tokens to put into a shared pot
that is multiplied and split equally; the highest total payoff after all rounds wins
([background](https://en.wikipedia.org/wiki/Public_goods_game)). It tests cooperation, free-riding, and persuasion over
repeated rounds.

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `PublicGoodsGame-v0` | `num_rounds=3`, `communication_turns=3`, `endowment=20`, `multiplication_factor=1.5`, `num_players=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `PublicGoodsGame-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("PublicGoodsGame-v0", num_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The game lasts `num_rounds` rounds. Each round has `communication_turns` communication turns followed by one decision
  turn, and in every turn each active player acts once, in player order.
- **Communication is simultaneous:** the public messages of a turn are revealed together once every player has
  submitted.
- **Contributions are simultaneous:** every round, each player receives `endowment` tokens and chooses how many of them
  (0 to `endowment`) to contribute. The amounts are revealed together once everyone has decided.
- The pot is multiplied by `multiplication_factor` and split equally among the active players. A player's round payoff
  is the tokens they kept plus their share of the pot.
- Round payoffs add up to a running total. After the last round, the highest total wins.

## Actions

During a communication turn, reply with any text; only the parts inside curly braces are shown to the other players,
e.g. `Cooperation pays if everyone joins in. {Let's all contribute 15 tokens this round.}` A reply without braces counts
as remaining silent. Every reply is valid during communication.

During the decision turn, reply with just the number of tokens you contribute, e.g. `15`. Anything else, including
numbers above `endowment`, is invalid.

## Observations

Each player first receives the rules, the payoff formula, and a worked example for the actual number of players.
After each communication turn, every player sees what each player said publicly, or that they remained silent. Raw
replies are never shown to other players. The start of every decision phase and of every new round is announced. After
each decision turn, everyone sees every contribution, the size of the pot and of each share, and each player's payoff
and running total. The final scores are announced at the end.

## Rewards

| Outcome | Reward |
| --- | --- |
| Single highest total payoff | Winner `+1`, everyone else `-1` |
| Several, but not all, players tie for the highest total | Each tied leader `+1`, everyone else `-1` |
| All players tie (nobody eliminated) | Everyone `0` |
| Third consecutive invalid contribution | Offender is eliminated, takes no further part, and receives `-1` at the end |
| Every player eliminated | Everyone `0` |

Only the totals of players who are still in the game are compared, so an eliminated player always gets `-1` (unless
every player is eliminated). If all remaining players tie after an elimination, they count as tied leaders and each
gets `+1`.

## Parameters

- `num_rounds` (default `5`): number of rounds.
- `communication_turns` (default `3`): simultaneous message turns before each decision; `0` skips communication.
- `endowment` (default `20`): tokens each player receives every round, which is also the maximum contribution.
- `multiplication_factor` (default `1.5`): factor applied to the pot before it is shared.
- `num_players` (default `4`): number of players used when `reset()` is called without `num_players`.

## Notes

- Every active player receives the same share of the pot, so the final ranking depends only on total contributions:
  among players who were never eliminated, the one who contributed the least overall wins. Contributing therefore
  never improves a player's reward, even though contributions raise the group's total payoff whenever
  `multiplication_factor` is above 1.
