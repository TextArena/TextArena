# Briscola

Two to four players play the Italian trick-taking card game Briscola with a 40-card deck, trying to capture the most
of its 120 card points, alone or, with four players, in two partnerships ([rules](https://en.wikipedia.org/wiki/Briscola)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–4

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Briscola-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Briscola-v1-mdp`).
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
- With two or three players, everyone plays alone. When all cards have been played, the player with the most points
  wins. Equal top scores share the win, and the game is a draw only if every player has the same score (60–60 with two
  players).
- With four players, the game is played in two fixed partnerships, as standard Briscola is: Players 0 and 2 against
  Players 1 and 3. Partners sit opposite each other, so the turn order alternates between the teams. Each player is
  told who their partner is. Partners' card points are combined, and when all cards have been played the team with
  more points wins; 60–60 is a draw.
- A player who makes two invalid moves in a row is eliminated. With two players, the opponent wins at once. With
  three, the eliminated player's hand leaves play (along with any stock cards needed to keep the remaining tricks
  complete) and the others play on. With four, the offender's team forfeits and the other team wins at once.

## Actions

Reply `play X`, where `X` is the position of a card in your hand, counting from 1. Example: `play 2`. The command is
case-insensitive.

## Observations

Every player first receives the rules (with four players, including who their partner is), and then the trump suit and
trump card are announced to all. Before each move, the acting player sees their own hand (with card points and trump
markers), the cards already played to the current trick (with four players, the partner's card is marked), every
player's points (with four players, also both teams' combined points), the trump suit, and the number of cards left in
the stock with the face-up trump card at its bottom. Every card played and every trick result is announced to all
players. Other players' hands, including the partner's, and the order of the stock stay hidden.

## Rewards

| Outcome | Reward |
| --- | --- |
| Most points when all cards are played, two or three players | Winner(s) `+1`, everyone else `-1` |
| Every player tied, two or three players | All `0` |
| More combined points when all cards are played, four players | Both winning partners `+1`, both losing partners `-1` |
| Teams tied at 60–60, four players | All `0` |
| Second consecutive invalid move, two players | Offender `-1`, opponent `+1` |
| Second consecutive invalid move, three players | Offender is eliminated and gets `-1`; the others play on, and a last remaining player wins at once |
| Every remaining player tied after an elimination, three players | Remaining players `0`, eliminated player `-1` |
| Second consecutive invalid move, four players | Offender and partner `-1`, the other team `+1` |
