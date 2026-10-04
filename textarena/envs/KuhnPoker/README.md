# Kuhn Poker

Two players play repeated hands of the simplest poker game, with a three-card deck, one card each and a single
betting round ([rules](https://en.wikipedia.org/wiki/Kuhn_poker)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `KuhnPoker-v0` | `max_rounds=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `KuhnPoker-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("KuhnPoker-v0", max_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The deck has three cards: Jack, Queen and King (J < Q < K).
- Each round, both players ante 1 chip and receive one card each (never the same card).
- **Betting:** the first player checks or bets 1 chip. After a check, the second player checks (showdown) or bets.
  Facing a bet, a player calls with 1 chip (showdown) or folds. There are no raises.
- At a showdown the higher card wins the pot; after a fold the other player wins it.
- Player 1 acts first in the first round and the first player alternates every round.
- Chips are counted from zero and may go negative; there are no stacks to run out of. After `max_rounds` rounds the
  player with more chips wins.

## Actions

Reply with exactly one word (case-insensitive): `check`, `bet`, `call` or `fold`. Your available actions are listed
on every turn: `check`/`bet` when no bet has been made, `call`/`fold` when facing a bet.

## Observations

Each player first receives the rules and the number of rounds, and privately learns their card at the start of every
round. Before every action the acting player sees a board with the round, the pot, both players' chip totals and
their own card (the opponent's stays hidden), followed by their available actions. Both players see every action; a
showdown reveals both cards, while a folded hand stays hidden.

## Rewards

| Outcome | Reward |
| --- | --- |
| More chips after `max_rounds` rounds | Winner `+1`, loser `-1` |
| Equal chips after `max_rounds` rounds | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_rounds` (default `1`): number of rounds in the match.

## Notes

- Kuhn poker was introduced by Harold W. Kuhn, "A Simplified Two-Person Poker" (1950), as a game small enough to
  solve by hand; its equilibrium strategies are mixed.
