# Market Entry Game

Each round, players exchange public messages and then simultaneously decide whether to enter a market that only pays
off if few enough of them enter; the highest total score after all rounds wins. It tests coordination, signalling, and
trust in a repeated congestion game.

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `MarketEntryGame-v0` | `num_rounds=5`, `communication_turns=3`, `market_capacity=2`, `entry_profit=15`, `overcrowding_penalty=-5`, `safe_payoff=5`, `default_num_players=4` |

Append `-mdp` to any ID for the state-complete variant (e.g. `MarketEntryGame-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The game lasts `num_rounds` rounds. Each round has `communication_turns` communication turns followed by one decision
  turn, and in every turn each active player acts once, in player order.
- **Communication is simultaneous:** the public messages of a turn are revealed together once every player has
  submitted.
- **Decisions are simultaneous:** every player chooses to enter the market or stay out, and the choices are revealed
  together once everyone has decided.
- Staying out always pays `safe_payoff`. If at most `market_capacity` players enter, each entrant earns
  `entry_profit`; if more enter, each entrant gets `overcrowding_penalty` instead.
- Round payoffs add up to a running total. After the last round, the highest total wins.

## Actions

During a communication turn, reply with any text; only the parts inside curly braces are shown to the other players,
e.g. `Entering looks risky with four players. {I think only two of us should enter this round.}` A reply without braces
counts as remaining silent. Every reply is valid during communication.

During the decision turn, reply with exactly `E` to enter or `S` to stay out (case-insensitive). Anything else is
invalid.

## Observations

Each player first receives the rules, the market capacity, all payoffs, and worked example scenarios for the actual
number of players. The start of every round and of every decision phase is announced. After each communication turn,
every player sees what each player said publicly, or that they remained silent. Raw replies are never shown to other
players. After each decision turn, everyone sees who entered, whether the market was overcrowded, and each player's
payoff and running total. The final scores are announced at the end.

## Rewards

| Outcome | Reward |
| --- | --- |
| Single highest total score | Winner `+1`, everyone else `-1` |
| Several, but not all, players tie for the highest total | Each tied leader `+1`, everyone else `-1` |
| All players tie (nobody eliminated) | Everyone `0` |
| Third consecutive invalid decision | Offender is eliminated, earns nothing in later rounds, and receives `-1` at the end |
| Every player eliminated | Everyone `0` |

Only the totals of players who are still in the game are compared, so an eliminated player always gets `-1` (unless
every player is eliminated). If all remaining players tie after an elimination, they count as tied leaders and each
gets `+1`.

## Parameters

- `num_rounds` (default `5`): number of rounds.
- `communication_turns` (default `3`): simultaneous message turns before each decision; `0` skips communication.
- `market_capacity` (default `2`): the largest number of entrants for which entering is profitable.
- `entry_profit` (default `15`): payoff for entering a market that is not overcrowded.
- `overcrowding_penalty` (default `-5`): payoff for entering an overcrowded market.
- `safe_payoff` (default `5`): payoff for staying out.
- `default_num_players` (default `4`): number of players used when `reset()` is called without `num_players`.
