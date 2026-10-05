# Indian Poker

Two players each hold one card on their forehead, seeing only the opponent's card, and bet in a single no-limit round
on whose card is higher ([rules](https://en.wikipedia.org/wiki/Blind_man%27s_bluff_%28poker%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `IndianPoker-v1` | `max_rounds=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IndianPoker-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("IndianPoker-v1", max_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- Both players start with `starting_chips` chips. Each round uses a freshly shuffled 52-card deck.
- Each round both players ante 1 chip and receive one card that only the opponent can see.
- **Betting:** the first player checks or bets any amount. After a check, the second player checks (showdown) or bets.
  Facing a bet, a player calls (showdown), folds, or raises by any amount on top of the bet. There is no limit on the
  number of raises, but a bet or raise can never exceed the chips the opponent has left to call it (or the chips you
  have to pay for it).
- **Showdown:** the higher rank wins the pot, from 2 (low) to Ace (high); suits do not matter and equal ranks split
  the pot. After a fold the other player wins the pot.
- Player 1 acts first in the first round and the first player alternates every round.
- The match lasts `max_rounds` rounds, or ends earlier when a player cannot pay the ante. The player with more chips
  wins.

## Actions

Reply with exactly one command (case-insensitive): `check`, `bet X`, `call`, `raise X` or `fold`, where `X` is a
positive whole number of chips. You can only check or bet when no bet is pending, and only call, raise or fold when
facing one.

Examples: `bet 5`, `raise 10`, `call`.

## Observations

Each player first receives the rules, the starting chips and the number of rounds. At the start of every round each
player is privately shown the opponent's card. Before every action the acting player sees the round, the opponent's
card, the pot, both players' chips, the chips each has bet this round, and their possible actions with the allowed
amounts. Both players see every action and the ranks shown at each showdown; their own card is never shown to a
player before the showdown.

## Rewards

| Outcome | Reward |
| --- | --- |
| More chips after the last round, or when a player cannot ante | Winner `+1`, loser `-1` |
| Equal chips at the end | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_rounds` (default `1`): The number of rounds in the match. Accepts an integer of at least 1.
- `starting_chips` (default `100`): The number of chips each player starts with. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->
