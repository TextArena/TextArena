# High Society

Two players bid one sealed money card at a time for ten prestige cards, and the higher net worth (money left plus
prestige won) after ten auctions wins. It is a streamlined two-player take on Reiner Knizia's
[High Society](https://boardgamegeek.com/boardgame/220/high-society).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `HighSociety-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `HighSociety-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The prestige cards 1–10 are shuffled with the seed and auctioned one at a time. Each player starts with the money
  cards 1–11 (66 in total).
- In every auction, both players bid one money card they still hold. Bids are sealed: Player 0 opens the first auction
  and the player who bid second opens the next one, but neither sees the other's card until both are in.
- The higher bid wins the prestige card and discards the money card it bid; the other player keeps their card.
- Equal bids are returned and the same prestige card is auctioned again. After `max_ties` ties in a row on the same
  card (3 by default), it is discarded instead: nobody gets it and both players keep their money.
- After ten auctions, each player's net worth is their remaining money plus their prestige. The higher net worth wins;
  equal net worth is a draw.

## Actions

Reply with the value of a money card you still hold, `1` to `11`, e.g. `7`. Any other text, or a card you have already
spent, is invalid.

## Observations

Each player first receives the rules, including the tie limit. At the start of every auction, each player is told the
auction number, the prestige card, and their own remaining money cards. Your bid is echoed only to you. Once both bids
are in, both players see both bids and who won the card (with the winner's prestige total), or the tied value and how
many ties the card has had, or that the card was discarded.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher net worth after ten auctions | Winner `+1`, loser `-1` |
| Equal net worth | Both `0` |
| Second consecutive invalid bid | Offender `-1`, opponent `+1` |

## Parameters

- `max_ties` (default `3`): ties allowed in a row on one prestige card; the tie that reaches this number discards the
  card, so a game has at most `10 × max_ties` rounds of bidding. With `1`, every tie discards the card.

## Notes

- Winning a card raises your net worth by the card's value minus your bid, while losing an auction costs nothing, so
  overpaying for a cheap card lowers your net worth.
- Differences from Knizia's game: bids are a single sealed card instead of open, escalating bids; there are no
  disgrace or multiplier cards; and there is no rule eliminating the poorest player.
