# Briscola

Two to four players play the Italian trick-taking card game Briscola with a 40-card deck, each trying to capture the
most of its 120 card points ([rules](https://en.wikipedia.org/wiki/Briscola)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–4

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Briscola-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Briscola-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The deck is the 40-card Italian deck in four suits (♠ ♥ ♦ ♣) with the ranks A, 2–7, J (Fante), Q (Cavallo), and
  K (Re). With three players, the 2♣ is removed so that the 39 cards divide evenly.
- Card points: A 11, 3 10, K 4, Q 3, J 2, all other cards 0, for 120 in total. Trick strength, from highest to lowest:
  A, 3, K, Q, J, 7, 6, 5, 4, 2.
- Each player is dealt three cards. The next card is turned face up as the trump card: its suit is the trump suit
  (briscola), and it goes to the bottom of the stock, so it is the last card drawn.
- Player 0 leads the first trick, and the others play one card each in turn order. Nobody has to follow suit.
- The highest trump wins the trick. If no trump was played, the highest card of the suit that was led wins; cards of
  other suits cannot win.
- The trick winner scores the points of its cards, draws first from the stock (the others follow in turn order), and
  leads the next trick. Once the stock is empty, play continues until every hand is empty.
- When all cards have been played, the player with the most points wins. Equal top scores share the win, and the game
  is a draw only if every player has the same score (60–60 with two players).
- With four players, everyone plays alone; the traditional two-against-two partnerships are not implemented.
- A player who makes two invalid moves in a row is eliminated. With two players, the opponent wins at once. With three
  or four, the eliminated player's hand leaves play (along with any stock cards needed to keep the remaining tricks
  complete) and the others play on.

## Actions

Reply `play X`, where `X` is the position of a card in your hand, counting from 1. Example: `play 2`. The command is
case-insensitive.

## Observations

Every player first receives the rules, and then the trump suit and trump card are announced to all. Before each move,
the acting player sees their own hand (with card points and trump markers), the cards already played to the current
trick, every player's points, the trump suit, and the number of cards left in the stock with the face-up trump card at
its bottom. Every card played and every trick result is announced to all players. Other players' hands and the order of
the stock stay hidden.

## Rewards

| Outcome | Reward |
| --- | --- |
| Most points when all cards are played | Winner(s) `+1`, everyone else `-1` |
| Every player tied | All `0` |
| Second consecutive invalid move, two players | Offender `-1`, opponent `+1` |
| Second consecutive invalid move, three or four players | Offender is eliminated and gets `-1`; the others play on, and a last remaining player wins at once |
| Every remaining player tied after an elimination | Remaining players `0`, eliminated players `-1` |
