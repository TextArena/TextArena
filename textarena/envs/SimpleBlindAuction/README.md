# Simple Blind Auction

Two players chat openly and then submit one round of sealed bids on items that each of them values differently; the
higher final net worth wins. It is the two-player version of [Blind Auction](../BlindAuction/README.md), without
private messages, and tests negotiation and bidding under private valuations.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `SimpleBlindAuction-v0` | `starting_capital=1000`, `num_items=5`, `conversation_rounds=3` |
| `SimpleBlindAuction-v0-quick` | `starting_capital=750`, `num_items=3`, `conversation_rounds=1` |
| `SimpleBlindAuction-v0-rich` | `starting_capital=2000`, `num_items=5`, `conversation_rounds=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SimpleBlindAuction-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Both players start with `starting_capital` coins. Each item has a base value (random 50–500 unless configured), and
  each player privately values every item at a random amount within ±20% of its base value.
- **Conversation phase:** the players alternate public messages, starting with Player 0, until each has sent
  `conversation_rounds` messages.
- **Bidding phase:** Player 0 and then Player 1 each take exactly one turn to submit all of their sealed bids at once,
  or no bids. The total of a player's bids may not exceed their coins.
- For each item the higher bid wins and only the winner pays; if the bids are equal (or nobody bids), nobody gets the
  item.
- Net worth is remaining coins plus your own valuation of the items you won. The game ends after Player 1's bidding
  turn, and the higher net worth wins.

## Actions

During the conversation phase, reply with any text; the whole reply is your public message, e.g.
`I mostly care about the Gold Statue. Shall we avoid bidding against each other?`

During the bidding phase, submit all of your bids in one reply, each on its own line or separated by semicolons (as in
Blind Auction):

```
Bid on Item 0: 250
Bid on Item 3: 175
```

or `Bid on Item 0: 250; Bid on Item 3: 175`. `Bid Item 0: 250` and `Bid 0: 250` also work, and commands are
case-insensitive. Amounts are positive integers, and each item may be bid on at most once. A reply without any `Bid`
command, such as `pass`, submits no bids. Mixing bids with other text, malformed bids, bids on unknown items, and bids
totalling more than your coins are invalid.

## Observations

Each player first receives the rules, their coins, and the item list with their private value for every item.
Conversation messages are shown to both players. A game message announces the bidding phase and the bid format. During
bidding, a bidder receives a private confirmation of the items they bid on, and the opponent is only told that bids
were submitted (a player who bids nothing is not announced); bid amounts stay hidden until the end. Once both players have bid, the full results are broadcast: each
item's winner, winning bid, and the winner's valuation, plus both players' spending, remaining coins, profit, and net
worth. No board is shown to players during the game.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher net worth | Winner `+1`, loser `-1` |
| Equal net worth (e.g. nobody wins an item) | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `starting_capital` (default `1000`): coins per player, which also caps the total of a player's bids.
- `num_items` (default `5`): number of items up for auction.
- `conversation_rounds` (default `3`): messages each player sends before bidding; `0` starts directly with bidding.
- `base_item_values` (default `None`): optional fixed base values; missing entries are drawn at random and extra entries
  are ignored.
