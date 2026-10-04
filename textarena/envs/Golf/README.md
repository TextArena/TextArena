# Golf

Two to four players draw and swap cards to build the lowest-scoring grid, where a column of equal ranks scores zero
([rules](https://www.pagat.com/draw/golf.html)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–4

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Golf-v0` | `num_cards=6`, `num_columns=3` |
| `Golf-v0-medium` | `num_cards=9`, `num_columns=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Golf-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Each player is dealt `num_cards` cards face down in a grid of `num_columns` columns (2 rows of 3 by default). A
  third of them (`num_cards // 3`, at random positions) start face up. One card starts the discard pile and the rest
  form the draw pile. One 52-card deck is used for up to 6 cards per player, two decks for 7–9, three for 10–12.
- Player 0 starts and turns pass in seat order. On your turn you do one of:
  - **Draw** the top card of the draw pile, then either swap it into your grid or discard it.
  - **Take** the top card of the discard pile, then swap it into your grid (you may not discard it again).
  - **Knock** instead of drawing (only before the final round has started).
- Swapping places the new card face up and puts the card it replaces face up on the discard pile. You do not get to
  look at a face-down card before replacing it.
- The **final round** starts when a player's cards are all face up or a player knocks: every other player then gets
  exactly one more turn. During the final round you may spend your turn peeking privately at one of your own
  face-down cards instead of drawing.
- The game also ends as soon as the turn that draws the last card of the draw pile is over; the discard pile is not
  reshuffled.
- **Scoring:** all cards are turned face up. Ace = 1, 2–10 = face value, Jack and Queen = 10, King = 0. A column whose
  cards all have the same rank scores 0 (a 10 and a Jack are both worth 10 but do not cancel). The lowest total wins,
  and players tied for the lowest total share the win.
- **Turn limit:** the game ends after `max_turns` accepted actions in total across all players; each `draw`, `take`,
  `swap`, `discard`, `knock` and `peek` counts as one and invalid moves do not count. At the limit, a card still in
  hand goes to the discard pile and the grids are scored as above.

## Actions

Reply with exactly one command (case-insensitive). Rows and columns are numbered from 1.

- At the start of your turn: `draw`, `take`, `knock` (before the final round), or `peek R C` (final round only, on one
  of your face-down cards).
- Holding a card: `swap R C` to put it at row `R`, column `C`, or `discard` (only for a card drawn from the draw pile).

Examples: `draw`, `swap 2 1`, `discard`, `take`, `knock`, `peek 1 3`.

## Observations

Each player first receives the rules, including the turn limit. Before every action the acting player sees their own
grid (face-up cards and cards they have peeked at; the rest as `?`), every opponent's face-up cards, the top of the
discard pile, the number of cards left in the draw pile, the card they are holding, the actions used so far, and
their options. A card drawn from the draw pile is shown only to its drawer until it is swapped in or discarded;
everyone sees every swap (both cards) and every discard. Peeks are private.

## Rewards

| Outcome | Reward |
| --- | --- |
| Lowest total, at the normal end or the turn limit | Lowest player(s) `+1`, everyone else `-1` |
| All remaining players tie for the lowest total | Remaining players `0`, eliminated players `-1` |
| Second consecutive invalid move, two players | Offender `-1`, opponent `+1` |
| Second consecutive invalid move, three or four players | Offender eliminated and scored `-1` at the end; play continues |

An eliminated player's card in hand goes to the discard pile, and if the final round has started, the turn they still
had is forfeited. When only one player is left, that player wins.

## Parameters

- `num_cards` (default `6`): cards per player, from 2 to 12; it also sets the number of decks.
- `num_columns` (default `3`): columns in each grid; it must divide `num_cards`.
- `max_turns` (default `None`): the action limit. `None` uses `2 × num_players × 4 × num_cards`, about four full rounds
  per grid card (96 actions for two players on the default grid), which normal games finish well within.

## Notes

- Differences from Pagat's six-card Golf: a 2 scores 2 points (Pagat scores it −2), the starting face-up cards are
  chosen at random rather than by the player, knocking is borrowed from four-card Golf, and the game ends when the
  draw pile runs out instead of reshuffling.
- A peek happens on a player's last turn, so it does not change what they can do; it is effectively a pass.
