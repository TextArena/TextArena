# Set

Find as many Sets as you can in 20 turns, where a Set is three cards whose four attributes are each all the same or all
different ([rules](https://en.wikipedia.org/wiki/Set_%28card_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Set-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Set-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The deck has 81 cards, one for every combination of four attributes: number (one, two, three), color (red, green,
  purple), fill (open, striped, solid), and shape (oval, diamond, squiggle).
- Twelve cards are dealt face up. Whenever the board holds no Set, three more cards are dealt until it does or the deck
  runs out.
- Three cards form a Set if, for each attribute separately, they are all the same or all different. For example,
  `one red open squiggle`, `two green open squiggle`, and `three purple open squiggle` form a Set.
- Each turn you pick three cards. A Set scores a point, and its cards leave the board, which is refilled up to 12 cards
  from the deck. A pick that is not a Set wastes the turn.
- The game ends after 20 turns, or earlier if no Set remains on the board and the deck is empty.
- A malformed pick (wrong format, a number that is not on the board, or the same card twice) is rejected without using
  a turn. Two rejected picks in a row end the game.

## Actions

Reply with the board numbers of three different cards, separated by commas or spaces, for example `1, 4, 11` or
`1 4 11`.

## Observations

The prompt explains the cards and the scoring. The board is a numbered list such as `3: two green striped diamond`,
shown at the start and again after every Set you find (it does not change otherwise). You are told whether each pick
was a Set and when extra cards were dealt.

## Rewards

| Outcome | Reward |
| --- | --- |
| 20 turns used | Number of Sets found (`0` to `20`) |
| No Set left and the deck is empty | Number of Sets found |
| Second consecutive rejected pick | Number of Sets found so far |
