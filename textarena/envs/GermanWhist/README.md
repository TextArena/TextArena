# German Whist

Two players use 13 tricks to win cards from the stock, then play 13 more tricks with their improved hands, and the
majority of those last tricks wins ([rules](https://www.pagat.com/whist/german_whist.html)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `GermanWhist-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `GermanWhist-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- A standard 52-card deck ranked A (high) K Q J 10 9 8 7 6 5 4 3 2 (low). Each player is dealt 13 cards. The next
  card is turned face up on top of the stock; its suit is trump for the whole game.
- Player 0 leads the first trick. The other player must follow the suit led if they can; otherwise they may play any
  card. The highest trump wins the trick; if no trump was played, the higher card of the suit led wins. The trick
  winner leads the next trick.
- **Learning phase (tricks 1–13).** After each trick the winner takes the face-up card from the stock and the loser
  takes the next card face down, so both hands are back to 13 cards; then the next stock card is turned face up. The
  card turned up at the start is the prize for the first trick. Tricks won in this phase do not count.
- **Playing phase (tricks 14–26).** Once the stock is empty, the last 13 tricks are played without drawing. Whoever
  wins 7 or more of them wins the game, so there are no ties. The game always ends after 26 tricks; there is no turn
  limit.

## Actions

Reply with `play X`, where `X` is the position of a card in your hand as numbered on your board (case-insensitive).

Example: `play 3`.

Positions start at 1 and follow the order in which cards entered your hand (played cards are removed and drawn cards
are added at the end), so they change during the game; the board groups your cards by suit but shows each card's
current position. Any other text, a position you do not have, or a card that does not follow suit when you could is
an invalid move.

## Observations

Each player first receives the rules and the trump suit, with the card that was turned up. Before every move the
acting player sees their hand grouped by suit (trumps first) with each card's position, the card already played to the
current trick, the face-up card the next trick winner will take and the number of cards left in the stock (learning
phase), and the trick count of the current phase. Both players see every card played, the winner of each trick, which
face-up card the winner took, and each newly turned card. The face-down card is shown only to the player who draws it.

## Rewards

| Outcome | Reward |
| --- | --- |
| 7 or more of the 13 playing-phase tricks | Winner `+1`, loser `-1` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Notes

- Following suit is enforced in both phases, as in Pagat's main rules; a common variation drops it during the
  learning phase.
- The final summary also reports the tricks each player won in the learning phase, but only playing-phase tricks
  decide the game (some groups count all 26 tricks instead).
