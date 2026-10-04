# Negotiation

Players trade five resources that each of them values differently, using public messages, private messages, and
targeted trade offers; whoever holds the most valuable inventory when the turns run out wins. It tests negotiation,
persuasion, and trading under private valuations.

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `Negotiation-v0` | `turn_multiple=8` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Negotiation-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Negotiation-v0", turn_multiple=...)`.
<!-- END GENERATED: variants -->

## Rules

- Every player starts with a random 5–25 units of each resource: Wheat, Wood, Sheep, Brick, and Ore.
- Each player privately values every resource at a random amount within ±20% of its base value (Wheat 5, Wood 10,
  Sheep 15, Brick 25, Ore 40), limited to the range 5–40.
- Players take turns in order, starting with Player 0. In one turn a player may send any number of messages, make trade
  offers, and accept or deny offers addressed to them.
- An offer proposes giving some resources in exchange for others and stays pending until its recipient accepts or
  denies it. Accepting swaps the resources immediately. If the offering player no longer holds what they offered, the
  offer is cancelled instead.
- The game ends after `turn_multiple` turns per player (`num_players × turn_multiple` turns in total). Each inventory is
  then valued at its owner's private valuations, and the highest total wins.

## Actions

Put each command on its own line or separate commands with semicolons; commands are case-insensitive. A semicolon
only starts a new command when a command name follows it, so messages may contain semicolons:
`Broadcast: Wheat for sale; Ore wanted` is a single message.

- `Broadcast: <message>` sends a message to every player, e.g. `Broadcast: I have spare Wheat, who needs some?`
- `Whisper <player id>: <message>` sends a private message, e.g. `Whisper 2: I can beat any offer for your Ore.`
  (`Whisper to 2:` also works).
- `Offer to <player id>: <items> -> <items>` offers the items before the arrow in exchange for the items after it, e.g.
  `Offer to 3: 2 Wheat, 1 Ore -> 3 Wood`. Items are `<quantity> <resource>` separated by commas or `and`.
- `Accept #<offer id>` or `Deny #<offer id>` answers an offer addressed to you, e.g. `Accept #5`.

Example turn: `Whisper 1: Deal if you add a Brick.; Deny #4; Offer to 1: 3 Sheep -> 1 Brick, 1 Ore`

A reply is rejected as a whole if any part of it is not a complete command (including plain prose), if it messages or
makes an offer to yourself or a non-existent player, if an offer names an unknown resource or more than you hold, or if
it answers an offer that does not exist or is addressed to someone else, or that you cannot afford to accept.

## Observations

Each player first receives their inventory with their own valuation of every resource, the commands, and the turn
limit. Broadcasts reach everyone as `(Broadcast) Player X says: ...`, while whispers reach only their target as
`(Private) Player X says: ...`; raw replies are echoed only to their author. Everyone is told when an offer is created
and between whom, but only the recipient sees its contents, together with its id. Acceptances (including the traded
resources), denials, and cancellations are announced to everyone. Inventories are never re-sent, so players have to
track their own holdings, and other players' valuations and inventories are never shown.

## Rewards

| Outcome | Reward |
| --- | --- |
| Single highest inventory value at the turn limit | Winner `+1`, everyone else `-1` |
| Tie for the highest inventory value | Everyone `0` |
| Second consecutive invalid move | The turn is forfeited and counts toward the turn limit; no elimination or direct penalty |

## Parameters

- `turn_multiple` (default `3`): turns per player, so the game lasts `num_players × turn_multiple` turns.

## Notes

- The winner is the player with the highest absolute inventory value, not the largest gain, so the random starting
  inventories strongly influence the result.
- A line break always ends a command, so a message cannot span several lines. A semicolon followed by a command name
  also starts a new command even inside a message (`Broadcast: I need Ore; offer me anything` is rejected as a
  malformed `Offer`), which keeps a mistyped whisper or offer from being broadcast by accident.
- Text inside a message is never interpreted as commands; for example, `Broadcast: I would never Accept #1` does not
  accept offer #1.
