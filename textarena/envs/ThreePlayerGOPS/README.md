# Three-Player Game of Pure Strategy (GOPS)

Three players each hold the thirteen cards from ace to king and spend one per round on a sealed bid for a randomly
revealed prize card; the single highest card wins the prize, and players are ranked by their prize totals after thirteen
rounds ([rules](https://en.wikipedia.org/wiki/Goofspiel)). It is the three-player version of
[Game of Pure Strategy](../GameOfPureStrategy/README.md), with tied prizes carrying over to the next round.

<!-- BEGIN GENERATED: variants -->
**Players:** 3

**`-mdp` observation:** the prompt and every game message (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `ThreePlayerGOPS-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `ThreePlayerGOPS-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Card values: `A` = 1, `2`–`10` at face value, `J` = 11, `Q` = 12, `K` = 13.
- Every player starts with one card of each value. The thirteen prize cards (values 1–13) are shuffled with the seed
  and revealed one per round.
- Each round, every remaining player bids one card from their hand, in the order Player 0, 1, 2; a played card is gone
  for good. Bids are sealed until everyone has bid.
- The single highest card wins the prize value plus the carry-over pot. If two or three players tie for the highest
  card, nobody scores: the prize goes into the pot and is added to the next round's prize. A tie in the last round
  leaves the pot unclaimed.
- After thirteen rounds, rewards follow the ranking by total (see [Rewards](#rewards)).
- Two invalid moves in a row eliminate a player. The others keep playing (and are ranked among themselves at the end);
  if only one player remains, they win at once.

## Actions

Reply with the face of a card you still hold: `A`, `2`–`10`, `J`, `Q`, or `K` (case-insensitive), e.g. `Q`. Numbers
for the face cards (`1`, `11`–`13`), a card you have already played, or more than one card are invalid.

## Observations

Each player first receives the rules and the reward scheme. At the start of every round, each player is told the prize
card, its worth including the carry-over pot, and their own remaining hand. Your bid is echoed only to you. Once every
remaining player has bid, everyone sees all bids, who won how much (or the new pot after a tie), and the updated scores.

## Rewards

| Outcome | Reward |
| --- | --- |
| Three different totals | Highest `+1`, middle `0`, lowest `-1` |
| Two players tie for the highest total | Both `+1`, third `-1` |
| Two players tie for the lowest total | Highest `+1`, both tied `-1` |
| All three totals equal | Everyone `0` |
| One player eliminated, the survivors' totals differ | Higher survivor `+1`, lower survivor `-1`, eliminated `-1` |
| One player eliminated, the survivors' totals are equal | Survivors `0`, eliminated `-1` |
| Second player eliminated (second consecutive invalid move) | Last remaining player `+1`, both eliminated `-1` |
