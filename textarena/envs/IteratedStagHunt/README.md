# Iterated Stag Hunt

Two players chat and then simultaneously choose to hunt a stag or a hare for a fixed number of rounds; a stag pays the
most but only if both hunt it, a hare pays less but safely, and the higher total wins
([background](https://en.wikipedia.org/wiki/Stag_hunt)). It balances trust against risk over repeated play.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `IteratedStagHunt-v1` | `num_rounds=5`, `conversation_rounds=3`, `mutual_stag_reward=10`, `single_hare_reward=8`, `single_stag_reward=1`, `mutual_hare_reward=5`, `randomize_payoff=False` |
| `IteratedStagHunt-v1-randomized` | `num_rounds=5`, `conversation_rounds=3`, `mutual_stag_reward=10`, `single_hare_reward=8`, `single_stag_reward=1`, `mutual_hare_reward=5`, `randomize_payoff=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedStagHunt-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("IteratedStagHunt-v1", num_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The game lasts `num_rounds` rounds. Each round has `conversation_rounds` conversation turns followed by one decision.
  In each conversation turn Player 0 speaks first and Player 1 replies; with `conversation_rounds=0` every round starts
  with the decision.
- Decisions are simultaneous: Player 0 decides first, but neither sees the other's choice until the round is resolved.
- Each round pays out according to that round's payoff matrix (default values shown, as Player 0 / Player 1):

  | | Player 1 hunts stag | Player 1 hunts hare |
  | --- | --- | --- |
  | **Player 0 hunts stag** | `10` / `10` (`mutual_stag_reward`) | `1` / `8` (`single_stag_reward` / `single_hare_reward`) |
  | **Player 0 hunts hare** | `8` / `1` (`single_hare_reward` / `single_stag_reward`) | `5` / `5` (`mutual_hare_reward`) |

- With `randomize_payoff=True`, a new matrix is drawn at the start of every round: the lone stag hunter always gets
  `single_stag_reward`; mutual hare is drawn from `single_stag_reward + 1` to `mutual_hare_reward`; the lone hare hunter
  gets a value from that mutual-hare payoff to `single_hare_reward`; and mutual stag is drawn from one above that to
  `mutual_stag_reward`. This keeps the stag hunt ordering mutual stag > lone hare ≥ mutual hare > lone stag every round.
- Payoffs add up over the rounds. After the last round, the higher total wins; equal totals are a draw.

## Actions

During conversation, reply with any text; it is shown to your opponent (sender labels such as `[GAME]` are removed).
Every message is valid, and words like "stag" in a message are never taken as a decision.

During the decision turn, reply with exactly `stag` or `hare` (case-insensitive). Anything else is invalid.

## Observations

Each player first receives the round structure, whether the payoffs change between rounds, and how the match is won.
Every round starts with an announcement of that round's payoff matrix and the number of conversation turns. Each
conversation message is shown to the opponent, and the start of the decision phase is announced. Your decision is
echoed only to you. Once both players have decided, both see each player's choice, payoff, and running total.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher total payoff after the last round | Winner `+1`, loser `-1` |
| Equal totals | Both `0` |
| Second consecutive invalid decision | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_rounds` (default `5`): The number of rounds. Accepts a positive integer.
- `conversation_rounds` (default `3`): The conversation turns before each decision, each one message per player; 0 skips conversation. Accepts a non-negative integer.
- `mutual_stag_reward` (default `10`): The payoff to each player when both hunt the stag (the upper bound when randomized). Accepts an integer.
- `single_hare_reward` (default `8`): The payoff to a lone hare hunter (the upper bound when randomized). Accepts an integer.
- `single_stag_reward` (default `1`): The payoff to a lone stag hunter (fixed even when randomized). Accepts an integer.
- `mutual_hare_reward` (default `5`): The payoff to each player when both hunt hares (the upper bound when randomized). Accepts an integer.
- `randomize_payoff` (default `False`): Draw a new payoff matrix every round, as described above. It requires single_stag_reward < mutual_hare_reward <= single_hare_reward < mutual_stag_reward.
<!-- END GENERATED: parameters -->

## Notes

- Without randomization the ordering of the payoffs is not checked.
- Only the comparison of totals decides the reward, so a round only changes the standings when one player hunts a hare
  while the other hunts a stag; mutual stag hunts keep the score level.
- The stag hunt goes back to Jean-Jacques Rousseau, *Discourse on the Origin of Inequality*, translated by Donald A.
  Cress, introduced by James Miller (Hackett, 1992), ISBN 978-0-87220-150-7.
