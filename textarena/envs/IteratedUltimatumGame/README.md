# Iterated Ultimatum Game

Each round, a proposer offers the responder a share of a fixed pool, which the responder accepts (both get their shares)
or rejects (both get nothing); whoever has collected more money after the last round wins
([background](https://en.wikipedia.org/wiki/Ultimatum_game)). It tests fairness, bargaining power, and punishment over
repeated play.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `IteratedUltimatumGame-v0` | `pool=50`, `max_turns=10`, `alternate_roles=False` |
| `IteratedUltimatumGame-v0-alternate` | `pool=50`, `max_turns=12`, `alternate_roles=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedUltimatumGame-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The game lasts `max_turns / 2` rounds; every round is one offer followed by one response.
- Player 0 proposes in round 1. With `alternate_roles=False` Player 0 proposes every round; with `alternate_roles=True`
  the proposer and responder swap after each round.
- The proposer offers a whole number `X` from 0 to `pool`. If the responder accepts, the proposer gets `pool − X` and
  the responder gets `X`; if the responder rejects, both get nothing that round.
- Money adds up over the rounds. After the last round, the player with more money wins; equal totals are a draw.

## Actions

As the proposer, reply with `Offer: X` or `Offer: $X` (case-insensitive, the colon is required), e.g. `Offer: $20`.
Offers above `pool`, fractions, or any other text are invalid.

As the responder, reply with `accept` or `reject` (case-insensitive). Anything else is invalid.

## Observations

Each player first receives the number of rounds, their starting role, whether roles alternate, the pool, how the match
is won, and the reply formats. The start of every round announces who proposes and who responds. Offers and responses
are public: both players see every offer (with what the proposer would keep), every accept or reject, each player's
gain for the round, and the running totals.

## Rewards

| Outcome | Reward |
| --- | --- |
| More money after the last round | Winner `+1`, loser `-1` |
| Equal totals (for example, every offer rejected) | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `pool` (default `10`): money split each round; a non-negative integer.
- `max_turns` (default `4`): total number of turns, which must be a positive even number; the game has `max_turns / 2`
  rounds.
- `alternate_roles` (default `False`): swap the proposer and responder after every round.

## Notes

- With fixed roles the game is lopsided: the responder can only win if the proposer offers more than half of the pool,
  while rejecting every smaller offer guarantees the responder at least a draw. Alternating roles with an even number of
  rounds gives both players the same number of proposals.
