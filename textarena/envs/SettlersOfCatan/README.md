# Settlers of Catan

Three or four players gather resources from dice rolls, trade with each other in private one-on-one negotiations, and
build roads, settlements, and cities on the beginner Catan board until someone reaches the target number of victory
points ([rules](https://www.catan.com/understand-catan/game-rules)).

<!-- BEGIN GENERATED: variants -->
**Players:** 3–4

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `SettlersOfCatan-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `SettlersOfCatan-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- **Players and setup:** Player 0 is Red, 1 White, 2 Blue, 3 Orange (Orange sits out in a three-player game). The
  board is the fixed beginner layout, and every color starts with its beginner pieces: two settlements and two roads,
  plus one resource card for each producing hex next to its second settlement. Red moves first, then turns go up in
  player order.
- **Production:** at the start of every turn two dice are rolled automatically. Each settlement next to a hex showing
  the rolled number collects one card of that hex's resource, and each city two. The desert never produces, and a 7
  produces nothing (there is no robber).
- **Your turn:** you may take up to `player_move_allowance` actions, each chosen from a numbered list of the moves that
  are currently legal: build a road, build a settlement, upgrade a settlement to a city, start a negotiation, or
  `Nothing.` to end your turn. The turn also ends once the allowance is used up.
- **Building:**

  | Piece | Cost | Limit | Placement |
  | --- | --- | --- | --- |
  | Road | 1 Brick, 1 Wood | 15 | Touches your road or building; it cannot extend through a corner occupied by an opponent |
  | Settlement | 1 Brick, 1 Wood, 1 Wheat, 1 Sheep | 5 | Touches your road; no building on any adjacent corner |
  | City | 3 Ore, 2 Wheat | 4 | Replaces one of your settlements, which returns to your supply |

- **Victory points:** settlement 1, city 2. A player who reaches `winning_score` wins at once.
- **Negotiation:** starting one costs an action. You pick one other player, and the two of you then alternate private
  messages, starting with you. A message may carry one command: an offer, a reply to the open offer addressed to you,
  or `Done`. Only one offer can be open at a time and it stays open until its recipient accepts or denies it; accepting
  swaps the resources immediately (both sides must still hold them). `Done` from either player ends the negotiation,
  and the turn returns to you with your remaining actions, if any.
- **Game end:** the game ends when a player reaches `winning_score`, when only one player is left, or after `max_turns`
  moves in total. Every valid reply counts as a move, including partner choices and negotiation messages.

## Actions

| When | Reply | Example |
| --- | --- | --- |
| Your action phase | The index of a move in the "Viable moves" list (the last two are always `Negotiate.` and `Nothing.`) | `3` |
| After choosing `Negotiate.` | The partner's id or color | `2` or `Blue` |
| Negotiating | Free text, plus at most one command on a line of its own | see below |

Negotiation commands (case-insensitive):

- `Offer: <items> -> <items>` gives the items before the arrow for the items after it, e.g.
  `Offer: 2 Wood, 1 Brick -> 1 Wheat`. Items are `<quantity> <resource>` separated by commas, using Brick, Wood, Wheat,
  Ore, and Sheep (plurals such as `Bricks` or `sheeps` are also accepted).
- `Accept` or `Deny` answers the open offer addressed to you.
- `Done` ends the negotiation.

Example negotiation message:

```
I'm short on Wheat for a city. Fair price?
Offer: 2 Wood -> 1 Wheat
```

`Accept`, `Deny`, and `Done` may end with `.` or `!`. Any line that starts with `Offer` must be a complete offer. A
reply is invalid if it names a move that is not in the list, contains more than one command, offers resources you do
not hold, makes an offer while one is open, answers an offer that is not addressed to you, or accepts without holding
the requested resources.

## Observations

Each player first receives the rules, build costs, and a legend for the text board. Before every action-phase move,
the acting player sees every color's victory points and piece counts, the full board (settlements `V` and cities `C`
marked with the owner's initial, roads drawn in the owner's initial), their own hand, the numbered list of legal
moves, and how many actions they have left. Moves name each corner by the tiles around it, e.g.
`{10 ore, 6 brick, 2 sheep}`; a coastal corner that touches a single tile also names its position on that tile as
drawn, e.g. `{10 ore (upper-left corner)}`, so no two moves read the same. During a negotiation, each negotiator
instead sees their own hand, the open offer, and how to respond.

Dice rolls and everyone's resulting income, every build, a player ending their turn with `Nothing.`, the end of each
negotiation, and eliminations are announced to all players. Negotiation messages, offers, denials, and completed trades are shown only to the two negotiators, and each
player's reply is echoed only to themselves. Other players' hands are never shown.

## Rewards

At the end, players still in the game are ranked by victory points into groups of equal points, and the groups are
spread evenly from `-1` (fewest points) to `+1` (most). For example, four players with 9, 5, 5, and 3 points get
`+1`, `0`, `0`, and `-1`.

| Outcome | Reward |
| --- | --- |
| A player reaches `winning_score`, or the turn limit is reached | Ranked by victory points as above; eliminated players `-1` |
| All remaining players tied on points | Everyone `0` if nobody was eliminated; otherwise remaining players `+1`, eliminated `-1` |
| Only one player left | That player `+1`, everyone else `-1` |
| Second consecutive invalid move | Offender is eliminated (final reward `-1`). If they were the negotiation partner, the negotiation ends and the turn goes back to its owner; otherwise the next player's turn starts |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `player_move_allowance` (default `10`): The number of actions per turn. Accepts an integer of at least 1.
- `max_turns` (default `500`): The number of moves in the whole game, counting every valid reply from any player. Accepts an integer of at least 1.
- `winning_score` (default `10`): The victory points needed to win; everyone starts with 2. Accepts an integer of at least 3.
<!-- END GENERATED: parameters -->

## Notes

- Not implemented: the robber and the 7 rule, development cards, Longest Road and Largest Army, trading with the bank
  or harbors, the initial placement phase (the beginner setup is always used), and the limited resource supply (the
  bank never runs out).
- Eliminated players' pieces stay on the board and still block placement.
- With the default limits, many games end at the turn limit and are decided by the victory-point ranking.
