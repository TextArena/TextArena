# Blind Auction

Players talk in public and in private, then submit sealed bids on items that each of them values differently; the
player with the highest final net worth wins. It tests negotiation, bluffing, and bidding under private valuations.

<!-- BEGIN GENERATED: variants -->
**Players:** 3–15

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `BlindAuction-v1` | `starting_capital=1000`, `num_items=5`, `conversation_rounds=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `BlindAuction-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("BlindAuction-v1", starting_capital=...)`.
<!-- END GENERATED: variants -->

## Rules

- Every player starts with `starting_capital` coins. Each item has a base value (random 50–500 unless configured), and
  each player privately values every item at a random amount within ±20% of its base value.
- **Conversation phase:** `conversation_rounds` rounds in which every player, starting with Player 0, takes one turn to
  send public and/or private messages.
- **Bidding phase:** every player takes exactly one turn and submits all of their sealed bids at once, or no bids. The
  total of a player's bids may not exceed their coins.
- For each item the highest bid wins and only the winner pays; if the highest bid is tied, nobody gets the item.
- Net worth is remaining coins plus your own valuation of the items you won. The game ends after the last player's
  bidding turn, and the highest net worth wins.

## Actions

During the conversation phase, send one or more messages per turn, one command per line or separated by semicolons:

- `Broadcast: <message>` sends a message to every player, e.g. `Broadcast: Anyone else after the Gold Statue?`
- `Whisper <player id>: <message>` sends a private message, e.g. `Whisper 2: I'll stay off Item 1 if you skip Item 3.`
  (`Whisper to 2:` and `Whisper to Player 2:` also work).

A semicolon only starts a new command when a command name follows it, so messages may contain semicolons:
`Broadcast: I want the vase; who else does?` is a single message.

During the bidding phase, submit every bid in a single reply, one per line or separated by semicolons:

- `Bid Item <item id>: <amount>`, e.g. `Bid Item 0: 250; Bid Item 3: 175` (`Bid on Item 0: 250` and `Bid 0: 250` also
  work). Amounts are positive integers, and each item may be bid on at most once.
- A reply without any `Bid` command, such as `pass`, submits no bids.

Commands are case-insensitive. Apart from a bid-free pass, every line of a reply must be a complete command, so plain
prose during the conversation, prose mixed with commands, bids during the conversation, messages during bidding,
whispers to yourself or to a non-existent player, bids on unknown items, and bids totalling more than your coins are all
rejected as a whole.

## Observations

Each player first receives the rules, their coins, and the item list with their private value for every item. During the
conversation, broadcasts reach everyone as `(Broadcast) Player X says: ...`, while a whisper reaches only its target as
`(Private) Player X says: ...`; raw replies are echoed only to their author. A game message announces the start of the
bidding phase. A bidder receives a private confirmation of the items they bid on, but no bid amounts are shown to anyone
else; a player who submits no bids is announced publicly. Once everyone has bid, the full results are broadcast: each
item's winner, winning bid, and the winner's valuation, plus every player's spending, remaining coins, profit, and net
worth. No board is shown to players during the game.

## Rewards

| Outcome | Reward |
| --- | --- |
| Single highest net worth | Winner `+1`, everyone else `-1` |
| Several (but not all) players tie for the highest net worth | Each tied leader `+1`, everyone else `-1` |
| All players tie (e.g. nobody wins an item) | Everyone `0` |
| Second consecutive invalid move | The turn is forfeited (in the bidding phase, the player bids nothing); no elimination or direct penalty |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `starting_capital` (default `1000`): The coins per player, which also cap the total of a player's bids. Accepts an integer of at least 1.
- `num_items` (default `5`): The number of items up for auction. Accepts an integer of at least 1.
- `conversation_rounds` (default `3`): The rounds of conversation before bidding. With 0, the game starts directly with bidding. Accepts an integer of at least 0.
- `base_item_values` (default `None`): Fixed base values for the items. Missing entries are drawn at random and extra entries are ignored. Accepts a list of positive integers or None.
<!-- END GENERATED: parameters -->

## Notes

- A line break always ends a command, so a message cannot span several lines. A semicolon followed by a command name
  also starts a new command even inside a message (`Broadcast: I like the vase; bid wisely` is rejected as a malformed
  `Bid`), which keeps a mistyped whisper from being broadcast by accident.
- Text inside a message is never interpreted as commands; for example, a broadcast quoting `Whisper 2: hi` does not
  also send a whisper.
