# Iterated Matching Pennies

Two players simultaneously pick heads or tails for a fixed number of rounds; the Matcher (Player 0) wins a round when the
picks match, the Mismatcher (Player 1) wins when they differ, and whoever wins more rounds wins
([background](https://en.wikipedia.org/wiki/Matching_pennies)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `IteratedMatchingPennies-v0` | `num_rounds=10` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedMatchingPennies-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 is the Matcher and Player 1 the Mismatcher for the whole game.
- Each round, both players pick heads or tails. Picks are sealed: Player 0 picks first, but neither sees the other's
  pick until both are in.
- Matching picks win the round for Player 0, different picks win it for Player 1, so every round has a winner.
- After `num_rounds` rounds, the player who won more rounds wins. Equal round wins, which is only possible with an even
  number of rounds, is a draw.

## Actions

Reply with `heads` or `tails`, or the shorthand `h` or `t` (case-insensitive), e.g. `heads`. Anything else is invalid.

## Observations

Each player first receives their role, the number of rounds, and the rules. Picks are never echoed, not even to the
player who made them. Once both picks are in, both players see both picks, the round winner, and the score after that
round (for example `Score after round 2/10: Player 0 1, Player 1 1.`).

## Rewards

| Outcome | Reward |
| --- | --- |
| More round wins after `num_rounds` rounds | Winner `+1`, loser `-1` |
| Equal round wins | Both `0` |
| Second consecutive invalid pick | Offender `-1`, opponent `+1` |

## Parameters

- `num_rounds` (default `5`): number of rounds.

## Notes

- Matching pennies has no pure-strategy equilibrium: the equilibrium is to pick uniformly at random, so neither role is
  favored and any predictable pattern can be exploited.
