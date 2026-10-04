# Three-Player Iterated Prisoner's Dilemma

Three players chat and then privately decide, for each opponent separately, whether to cooperate or defect; every pair
of players scores a prisoner's dilemma each round, and players are ranked by their totals after a fixed number of rounds
([background](https://en.wikipedia.org/wiki/Prisoner%27s_dilemma)). It tests coalition building and selective trust.

<!-- BEGIN GENERATED: variants -->
**Players:** 3

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `ThreePlayerIPD-v0` | `num_rounds=5`, `communication_turns=1`, `cooperate_reward=3`, `defect_reward=5`, `sucker_reward=0`, `mutual_defect_reward=1` |

Append `-mdp` to any ID for the state-complete variant (e.g. `ThreePlayerIPD-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("ThreePlayerIPD-v0", num_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The game lasts `num_rounds` rounds. Each round has `communication_turns` chat turns followed by one decision turn. In
  every turn the players act in the order Player 0, 1, 2; with `communication_turns=0` every round starts with the
  decision turn.
- In the decision turn, each player privately chooses to cooperate with or defect against each of the two opponents.
  Decisions are sealed until all three players have decided. An opponent you do not mention gets `cooperate`.
- Each of the three pairs then scores the payoff matrix with their choices towards each other (default values shown,
  as you / them):

  | | They cooperate with you | They defect against you |
  | --- | --- | --- |
  | **You cooperate with them** | `3` / `3` (`cooperate_reward`) | `0` / `5` (`sucker_reward` / `defect_reward`) |
  | **You defect against them** | `5` / `0` (`defect_reward` / `sucker_reward`) | `1` / `1` (`mutual_defect_reward`) |

- Each player's round score is the sum over their two pairs, and scores add up over the rounds. After the last round,
  rewards follow the ranking by total (see [Rewards](#rewards)).
- Two invalid moves in a row forfeit the whole game for the offender.

## Actions

During chat, reply with any text; it is shown to both opponents with whitespace collapsed and sender labels such as
`[GAME]` removed. Every message is valid, and phrases like "1 defect" in a chat message are never taken as a decision.

During the decision turn, reply with one `<player-id> cooperate` or `<player-id> defect` token per opponent, separated
by spaces, commas, or semicolons (case-insensitive). For Player 0, `1 defect 2 cooperate` defects against Player 1 and
cooperates with Player 2, `2 cooperate; 1 defect` means the same, and `1 defect` alone also cooperates with Player 2.
An empty reply cooperates with both opponents. Naming yourself or a player who does not exist, naming an opponent twice,
or adding any other text is invalid.

## Observations

Each player first receives the round structure, the payoff matrix, an example decision for their own opponents, and the
reward scheme. The start of every round and of every decision turn is announced, and each chat message is shown to both
opponents. Your decision is echoed only to you. Once all three players have decided, everyone sees the choices made
within each pair, what each player gained, and the running totals.

## Rewards

| Outcome | Reward |
| --- | --- |
| Three different totals | Highest `+1`, middle `0`, lowest `-1` |
| Two players tie for the highest total | Both `+1`, third `-1` |
| Two players tie for the lowest total | Highest `+1`, both tied `-1` |
| All three totals equal | Everyone `0` |
| Second consecutive invalid move | Offender `-1`, both opponents `+1` (the game ends) |

## Parameters

- `num_rounds` (default `5`): number of rounds.
- `communication_turns` (default `3`): chat turns before each decision, each one message per player; `0` skips chat.
- `cooperate_reward` (default `3`): payoff to each player of a pair when both cooperate.
- `defect_reward` (default `5`): payoff to a defector whose opponent cooperates.
- `sucker_reward` (default `0`): payoff to a cooperator whose opponent defects.
- `mutual_defect_reward` (default `1`): payoff to each player of a pair when both defect.

The payoffs may be any finite numbers; their ordering is not checked.

## Notes

- A forfeit ends the game instead of eliminating the player, because every remaining round would still need the
  forfeiting player's decisions towards the other two.
