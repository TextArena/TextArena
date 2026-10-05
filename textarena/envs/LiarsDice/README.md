# Liar's Dice

Players bid on how many dice of a face are showing across everyone's hidden dice or call the last bid a lie; every
lost challenge costs a die, and the last player with dice wins ([rules](https://en.wikipedia.org/wiki/Liar%27s_dice)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LiarsDice-v1` | `num_dice=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `LiarsDice-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("LiarsDice-v1", num_dice=...)`.
<!-- END GENERATED: variants -->

## Rules

- Every player starts with `num_dice` six-sided dice. At the start of each round all remaining dice are re-rolled, and
  each player sees only their own.
- Player 0 opens the first round. Turns go up in player order, skipping players who are out.
- On your turn you either raise the bid or call it:
  - A **bid** claims that at least `quantity` of all dice in play show `face`. Faces are 1–6 and nothing is wild. A new
    bid must raise the quantity (with any face) or keep the quantity and raise the face, and the quantity can never
    exceed the number of dice in play.
  - A **call** challenges the current bid. All dice are revealed: if fewer dice show that face than the bid claims,
    the bidder loses a die; otherwise the caller loses a die. You cannot call before anyone has bid.
- The loser of a challenge opens the next round (if they are out, the next player still in after them does).
- A player with no dice left is out. The last player with dice wins.

## Actions

Reply with exactly one command (case-insensitive; surrounding spaces are ignored):

- `Bid: <quantity>, <face>`, e.g. `Bid: 3, 4` claims at least three 4s. `Bid 3 4` and `Bid:3,4` also work.
- `Call` challenges the current bid.

Anything else, a bid that does not beat the current one, a bid above the number of dice in play, or a call with no bid
is invalid.

## Observations

Each player first receives the rules and the starting dice count. At the start of every round, each player privately
receives everyone's remaining dice counts and their own new roll. Before every move, the acting player sees a board
with their own dice, how many hidden dice every other player has, the total number of dice in play, and the current
bid (with more than five players the board is a compact list). Every bid is announced to all players; after a call,
everyone sees all the revealed dice, the actual count of the face, who lost a die, and whether that player is now out.
Other players' dice for the current round are never shown.

## Rewards

Players are ranked by when they ran out of dice, and rewards are spread evenly from `-1` (first out) to `+1` (winner).
With `N` players, the player who goes out `k`-th (`k = 1 … N−1`) gets `-1 + 2(k−1)/(N−1)`: for example `-1`, `0`, `+1`
with three players.

| Outcome | Reward |
| --- | --- |
| Last player with dice | `+1` |
| Running out of dice | By order of elimination, from `-1` (first out) upwards |
| Second consecutive invalid move | Offender is out immediately (their dice are removed and a new round starts) and is ranked as the next player out |

There are no draws and no turn limit: bids are capped by the dice in play, so every round ends with a call, and every
call removes a die.

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_dice` (default `5`): The number of dice each player starts with. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- Common variants such as wild 1s or a "spot on" call are not implemented.
