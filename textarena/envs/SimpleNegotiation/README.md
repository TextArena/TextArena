# Simple Negotiation

Two players barter five resources that each of them values privately, and whoever increases the value of their own
inventory more by the turn limit wins.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `SimpleNegotiation-v0` | `max_turns=10` |
| `SimpleNegotiation-v0-long` | `max_turns=30` |
| `SimpleNegotiation-v0-short` | `max_turns=6` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SimpleNegotiation-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Each player starts with a random 5–25 units of each resource: Wheat, Wood, Sheep, Brick, and Ore.
- Each player privately values every resource at a random whole amount within ±20% of its base value, limited to
  5–40: Wheat 5–6, Wood 8–12, Sheep 12–18, Brick 20–30, Ore 32–40.
- Players alternate turns, starting with Player 0, for `max_turns` turns in total.
- On each turn a player writes a message to the opponent and may include one trade command:
  - An **offer** proposes giving some of your resources in exchange for some of the opponent's. You must hold what you
    offer. There is at most one pending offer, always addressed to the player whose turn is next.
  - The recipient resolves it on their next turn: **accepting** swaps the resources immediately (both players must
    still hold them); denying it, replying without a command, or making a counteroffer rejects it.
- When the turn limit is reached, each inventory is valued at its owner's prices. The player whose value rose more
  since the start wins; equal gains are a draw.

## Actions

Your whole message is shown to your opponent. Put at most one command on a line of its own (case-insensitive):

- `Offer: <items> -> <items>` gives the items before the arrow for the items after it, e.g.
  `Offer: 3 Sheep, 2 Ore -> 5 Brick`. Items are `<quantity> <resource>` separated by commas or `and`; plurals such as
  `Ores` and a leading `I give` or `I offer` are accepted.
- `Accept` accepts the offer you received.
- `Deny` rejects the offer you received.

Example:

```
I really need Brick and can spare plenty of Sheep.
Offer: 3 Sheep -> 1 Brick
```

Any line that begins with `Offer`, `Accept`, or `Deny` is read as a command and must match one of these formats
exactly, so `Accept.` or `Offer 3 Sheep -> 1 Brick` (no colon) is invalid. Lines that merely contain those words, such
as `I accept your point`, are chat. A message is also invalid if it has more than one command, offers resources you
do not hold, names an unknown resource or a zero quantity, accepts or denies when no offer is pending, or accepts
without holding the requested resources.

## Observations

Each player first receives their starting quantities and values, the rules, and the turn limit. Before every move,
the acting player sees the turn counter (`Turn 3 of 10`), their own current inventory with values, total value and
change, and the pending offer; the opponent's inventory and values are never shown. Both players see each other's
full messages and the game's announcements of every offer, acceptance, and rejection.

## Rewards

| Outcome | Reward |
| --- | --- |
| Larger gain in inventory value at the turn limit | Winner `+1`, loser `-1` |
| Equal gains | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_turns` (default `10`): turns in the whole game, counting both players.

## Notes

- Gains are measured with each player's own prices, so one trade can raise both values; only the comparison decides
  the winner.
- An offer made on the final turn can never be answered.
- The `-mdp` variant shows game messages and the board but not raw player messages, so chat is not part of that
  transcript; offers and responses still are.
