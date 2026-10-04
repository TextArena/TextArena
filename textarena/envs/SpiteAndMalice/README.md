# Spite and Malice

Two players race to empty their payoff piles by building shared center piles from Ace up to Queen, with Kings wild
([rules](https://www.pagat.com/patience/spitemal.html)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `SpiteAndMalice-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `SpiteAndMalice-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Two 52-card decks without the 10s are shuffled together (96 cards). Ranks run A = 1, 2–9, J = 10, Q = 11; Kings
  are wild.
- Each player has a 20-card payoff pile with only its top card face up, a hand of 5 cards, and four personal discard
  piles that start empty. There are four shared center piles. The remaining cards form the draw pile.
- The player whose payoff pile shows the higher card goes first (Aces low, Kings high); on equal cards Player 0 goes
  first. Every turn starts with a draw, which refills your hand to 5 cards.
- You may then play any number of cards onto the center piles, taken from your hand, the top of your payoff pile, or
  the top of any of your discard piles. An empty center pile must be started with an Ace; after that each card must
  be exactly one rank higher than the pile's top card, regardless of suit. A King can be played anywhere and counts as
  the rank it replaces. A pile that reaches the Queen (11 cards) is cleared and its cards are set aside.
- Whenever a draw needs a card and the draw pile is empty, the cleared cards set aside so far are shuffled to form a
  new draw pile, and the draw continues.
- If you play every card in your hand, you immediately draw 5 more and keep playing.
- You end your turn by moving one card from your hand onto one of your discard piles. If your hand is empty and you
  have no legal play, your turn ends automatically.
- The first player to empty their payoff pile wins.
- **Deadlock:** when no card is left to draw (the draw pile is empty and no cleared cards are waiting), both hands are
  empty and neither player can play from their payoff or discard piles, nobody can ever move again. The player with
  fewer payoff cards left then wins; equal counts are a draw. There is no turn limit.

## Actions

A reply contains one or more commands separated by spaces, executed in order:

- `draw` must be the first command of each turn.
- `play <card> <pile>` plays a card onto center pile 0–3.
- `discard <card> <pile>` moves a card from your hand onto your discard pile 0–3 and ends your turn, so it must be the
  last command.

Cards are written as rank then suit: `A♠`, `7♥`, `J♦`, `K♣` (there are no 10s). Ranks are case-insensitive and
emoji-style suits such as `♥️` are accepted. If the same card is available from several places, it is taken from your
payoff pile first, then your hand, then your discard piles.

Examples: `draw`, `play A♠ 0`, `draw play A♠ 0 play 2♥ 0 discard 7♣ 3`.

A reply is applied completely or not at all: if any command is illegal, or there is extra text, nothing changes and
the reply counts as one invalid move. A turn may also be spread over several replies until you discard.

## Observations

Each player first receives the rules and who goes first. Before every reply the acting player sees the size of the
draw pile, the number of cleared cards waiting to be shuffled into it, the center piles, both players' payoff tops, payoff sizes and discard piles, their own hand (only the size of the opponent's),
and a list of their available moves. Both players are told about every play, discard, refill and reshuffle; the
opponent's draws are announced without revealing the cards.

## Rewards

| Outcome | Reward |
| --- | --- |
| Empty your payoff pile | Winner `+1`, loser `-1` |
| Deadlock with fewer payoff cards left | That player `+1`, opponent `-1` |
| Deadlock with equal payoff cards left | Both `0` |
| Second consecutive invalid reply | Offender `-1`, opponent `+1` |

## Notes

- Differences from the standard game: there are four center piles (Pagat allows three); no card ever has to be
  played (some groups force Aces to be played at once); cleared piles wait until the draw pile runs out before they
  are shuffled into it (Pagat shuffles each one in as soon as it is completed); on equal payoff top cards Player 0
  starts (Pagat reshuffles the payoff piles); and a game in which nobody can move is decided by the payoff cards
  left, as in Pagat's "Resolving Stalemates" variant (the standard game is a draw once the stock runs out).
