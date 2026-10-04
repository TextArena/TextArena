# Blackjack

Play a series of Blackjack hands against a dealer, hitting or standing to finish closer to 21 than the dealer without
going over ([rules](https://en.wikipedia.org/wiki/Blackjack)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Blackjack-v0` | `num_hands=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Blackjack-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Blackjack-v0", num_hands=...)`.
<!-- END GENERATED: variants -->

## Rules

- A game is `num_hands` hands. Each hand starts with two cards for you and two for the dealer; you see both of your
  cards and the dealer's first card.
- Cards come from an infinite deck: every card dealt is equally likely to be any of the 52 cards, regardless of the
  cards already seen.
- Number cards count their value, J, Q, and K count 10, and each ace counts 11 unless that would put the hand over 21,
  in which case it counts 1.
- `hit` draws a card. Going over 21 is a bust: you lose the hand at once and the dealer does not play.
- `stand` ends your turn. The dealer reveals the hidden card and draws until reaching 17 or more, standing on soft 17.
- If the dealer busts or your total is higher, you win the hand; equal totals push.
- A blackjack (an ace and a ten-value card as the first two cards) beats any other 21, and two blackjacks push. A
  blackjack is not settled automatically: you still reply `stand` (the dealer then does not draw), and hitting gives the
  blackjack up.
- There is no betting, doubling, splitting, insurance, or surrender. The next hand is dealt as soon as one ends.

## Actions

Reply `hit` or `stand`. Case does not matter.

## Observations

The prompt explains the rules and the scoring. Before every decision you see the hand number, your cards and total,
and the dealer's face-up card:

```
Hand 1/5
Your hand: 4♠, 6♠ (Score: 10)
Dealer shows: 9♣
```

When a hand ends you see its result and the dealer's full hand; after the last hand, the numbers of wins, losses, and
pushes.

## Rewards

| Outcome | Reward |
| --- | --- |
| All hands played | `(wins + 0.5 × pushes) / num_hands`, from `0` to `1` |
| Second consecutive invalid move | The same formula over the hands finished so far; unplayed hands count as losses |

## Parameters

- `num_hands` (required): the number of hands in a game, a positive integer.
