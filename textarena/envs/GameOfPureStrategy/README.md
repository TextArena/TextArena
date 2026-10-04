# Game of Pure Strategy (GOPS)

Two players each hold the thirteen cards from ace to king and spend one per round on a sealed bid for a randomly revealed
prize card; the higher card wins the prize, and the higher prize total after thirteen rounds wins
([rules](https://en.wikipedia.org/wiki/Goofspiel)). Also known as Goofspiel; in this version tied prizes carry over to
the next round.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `GameOfPureStrategy-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `GameOfPureStrategy-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Card values: `A` = 1, `2`–`10` at face value, `J` = 11, `Q` = 12, `K` = 13.
- Both players start with one card of each value. The thirteen prize cards (values 1–13) are shuffled with the seed
  and revealed one per round.
- Each round, both players bid one card from their hand; a played card is gone for good. Bids are sealed: Player 1 bids
  first in round 1 and the first bidder alternates every round, but neither sees the other's card until both are in.
- The higher card wins the prize value plus the carry-over pot. On equal cards nobody scores: the prize goes into the
  pot and is added to the next round's prize. A tie in the last round leaves the pot unclaimed.
- After thirteen rounds (every card played), the higher total wins; equal totals are a draw.

## Actions

Reply with the face of a card you still hold: `A`, `2`–`10`, `J`, `Q`, or `K` (case-insensitive), e.g. `Q`. Numbers
for the face cards (`1`, `11`–`13`), a card you have already played, or more than one card are invalid.

## Observations

Each player first receives the rules. At the start of every round, each player is told the prize card, its worth
including the carry-over pot, and their own remaining hand. Before every move, the acting player also sees a status
line with the round, the prize, the pot, both scores, their hand, and whether they have already bid this round. Your bid
is echoed only to you. Once both bids are in, both players see both cards, who won how much (or the new pot after a
tie), and the updated scores.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher total after thirteen rounds | Winner `+1`, loser `-1` |
| Equal totals | Both `0` |
| Second consecutive invalid bid | Offender `-1`, opponent `+1` |
