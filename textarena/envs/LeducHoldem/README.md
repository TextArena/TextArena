# Leduc Hold'em

Two players play a match of a six-card, two-round fixed-limit poker game that is a standard benchmark for
imperfect-information games ([rules](https://openspiel.readthedocs.io/en/latest/games.html)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LeducHoldem-v1` | `max_rounds=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `LeducHoldem-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("LeducHoldem-v1", max_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The deck has six cards: two Jacks, two Queens and two Kings (J < Q < K).
- Each hand, both players ante 1 chip and receive one private card; one public card is dealt face down.
- **Betting rounds:** a pre-flop round, then the public card is revealed, then a post-flop round. Bets are fixed: 2
  chips pre-flop and 4 chips post-flop. With no bet in the round you may check or bet; facing a bet you may call,
  raise (add one more bet on top) or fold. A round allows at most two bets: the opening bet and one raise. Two checks
  or a call end the round.
- The same player acts first in both rounds of a hand. Player 1 starts the first hand and the starting player
  alternates every hand.
- A bet or raise is only allowed if both players can still cover it, so nobody is ever all-in.
- **Showdown:** a private card that pairs the public card wins; otherwise the higher private card wins; equal private
  cards split the pot. A fold gives the pot to the other player.
- **Match:** players start with `starting_bank` chips and play `max_rounds` hands. The match ends early if a player
  cannot pay the ante. Whoever has more chips at the end wins.

## Actions

Reply with exactly one word (case-insensitive): `check`, `bet`, `call`, `raise` or `fold`. Bet sizes are fixed, so
no amounts are given.

## Observations

Each player first receives the rules, the match length and the starting chips, and privately learns their card at the
start of every hand. Before every action the acting player sees the hand number and betting round, their card, the
public card once it is revealed, the pot, both players' chips, the current bet and the amount they must call, how
many bets have been made this round, and their valid actions. Both players see every action and the public card; at a
showdown both private cards are revealed, while a folded hand stays hidden.

## Rewards

| Outcome | Reward |
| --- | --- |
| More chips after the last hand, or when a player cannot ante | Winner `+1`, loser `-1` |
| Equal chips at the end | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `starting_bank` (default `100`): The number of chips each player starts the match with. Accepts an integer of at least 1.
- `max_rounds` (default `5`): The number of hands in the match. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- Leduc Hold'em was introduced by Southey et al., "Bayes' Bluff: Opponent Modelling in Poker" (UAI 2005). The
  betting follows the standard definition used by OpenSpiel and RLCard (antes of 1, bets of 2 and 4, two bets per
  round); the multi-hand match with chip stacks is this environment's addition.
