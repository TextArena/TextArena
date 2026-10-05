# Public Goods Game

Each round, players exchange public messages and then simultaneously decide how many tokens to put into a shared pot
that is multiplied and split equally; each player is scored on their own total payoff
([background](https://en.wikipedia.org/wiki/Public_goods_game)). It tests cooperation, free-riding, and persuasion over
repeated rounds.

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt and every game message (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `PublicGoodsGame-v1` | `num_rounds=3`, `communication_turns=3`, `endowment=20`, `multiplication_factor=1.5`, `default_num_players=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `PublicGoodsGame-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("PublicGoodsGame-v1", num_rounds=...)`.
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
- Round payoffs add up to a running total, which each player tries to maximize. There is no winner: every player is
  scored on their own total (see Rewards).

## Actions

During a communication turn, reply with any text; only the parts inside curly braces are shown to the other players,
e.g. `Cooperation pays if everyone joins in. {Let's all contribute 15 tokens this round.}` A reply without braces counts
as remaining silent. Every reply is valid during communication.

During the decision turn, reply with just the number of tokens you contribute, e.g. `15`. Anything else, including
numbers above `endowment`, is invalid. The first invalid contribution gets a warning; a second one in a row eliminates
the player.

## Observations

Each player first receives the rules, the payoff formula, a worked example for the actual number of players, and the
maximum total payoff used to compute rewards.
After each communication turn, every player sees what each player said publicly, or that they remained silent. Raw
replies are never shown to other players. The start of every decision phase and of every new round is announced. After
each decision turn, everyone sees every contribution, the size of the pot and of each share, and each player's payoff
and running total. The final scores are announced at the end.

## Rewards

This is a mixed-motive game: each player gets their own score from `0` to `1`.

| Outcome | Reward |
| --- | --- |
| Game completed | Each remaining player gets their total payoff divided by the maximum total payoff (below) |
| Second consecutive invalid contribution | Offender is eliminated, takes no further part, and receives `0` at the end |
| Every player eliminated | Everyone `0` |

The maximum total payoff is the most any one player could earn: `num_rounds × endowment × (1 + (n − 1) ×
multiplication_factor / n)` for `n` players, which is what a player earns by contributing nothing every round while
everyone else contributes their whole endowment. When `multiplication_factor` is larger than `n`, contributing pays
even for oneself, so the maximum is instead `num_rounds × endowment × multiplication_factor` (everyone contributing
everything). With an `endowment` of 0 nobody can earn anything and every reward is `0`.

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_rounds` (default `5`): The number of rounds. Accepts a positive integer.
- `communication_turns` (default `3`): The simultaneous message turns before each decision. With 0, communication is skipped. Accepts a non-negative integer.
- `endowment` (default `20`): The tokens each player receives every round, which is also the maximum contribution. Accepts a non-negative integer.
- `multiplication_factor` (default `1.5`): The factor applied to the pot before it is shared. Accepts a finite non-negative number.
- `default_num_players` (default `4`): The number of players used when `reset()` is called without `num_players`. Accepts an integer from 2 to 15.
<!-- END GENERATED: parameters -->

## Notes

- Rewards are absolute rather than rank-based, which keeps the social dilemma: free-riding on others raises a player's
  own score, but whenever `multiplication_factor` is above 1 everyone scores more when all contribute than when nobody
  does.
- A player's share of the pot only counts the players still in the game, so eliminations change the shares of later
  rounds.
