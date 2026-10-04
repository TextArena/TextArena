# Ultimate Texas Hold'em

A single player plays the casino game against the dealer, choosing when to make one Play bet per round, and must
survive a fixed number of rounds without going broke ([rules](https://wizardofodds.com/games/ultimate-texas-hold-em/)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `UltimateTexasHoldem-v0` | `max_turns=1000`, `start_chips=1000`, `ante_amount=25` |

Append `-mdp` to any ID for the state-complete variant (e.g. `UltimateTexasHoldem-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- You start with `start_chips` chips. Each round uses a freshly shuffled 52-card deck.
- **Round structure:** you post an Ante and a Blind of `ante_amount` each. You and the dealer get two cards each (the
  dealer's stay hidden) and five community cards are dealt face down.
  - **Pre-flop:** check, or make a Play bet of 3× or 4× the ante. Then the first three community cards are revealed.
  - **Flop:** if you have not bet yet, check or bet 2× the ante; if you have, skip. Then the last two community cards
    are revealed.
  - **River:** if you have not bet yet, bet 1× the ante or fold; if you have, skip to the showdown.
  - Only one Play bet can be made per round, and a Play bet you cannot afford is invalid.
- **Showdown:** you and the dealer each use the best five of your seven cards. The dealer qualifies with a pair or
  better.
  - **Ante:** pushes (is returned) if the dealer does not qualify; otherwise pays 1:1 if you win, is lost if you lose,
    and pushes on a tie.
  - **Play:** pays 1:1 if you win, is lost if you lose, and pushes on a tie.
  - **Blind:** if you win it pays by the table below (it pushes when your hand is less than a straight), it is lost if
    you lose, and it pushes on a tie.
  - Folding loses the Ante and the Blind.
- **Blind pay table:** royal flush 500:1, straight flush 50:1, four of a kind 10:1, full house 3:1, flush 3:2,
  straight 1:1. Flush payouts can leave you with half chips.
- **End of the game:** you win by completing `max_turns` rounds; you lose as soon as a round leaves you with less than
  twice the ante, the cost of the next Ante and Blind.

## Actions

Reply with exactly one command (case-insensitive):

- Pre-flop: `4x`, `3x` or `check`.
- Flop: `2x` or `check`, or `skip` after a pre-flop bet.
- River: `1x` or `fold`, or `skip` after an earlier bet.

Aliases are accepted: `play bet 4x` (and so on), `c` for `check`, `f` for `fold`, `s` for `skip`.

## Observations

The first observation explains the rules, bet sizes and pay table. Before every decision you see the round number and
phase, your chips, your bets on the table, your two cards, the community cards revealed so far and your available
actions. At each showdown the dealer's cards, both best hands and the result of every bet are announced.

## Rewards

| Outcome | Reward |
| --- | --- |
| Complete `max_turns` rounds | `+1` |
| A round leaves you unable to post the next Ante and Blind | `-1` |
| Second consecutive invalid move | `-1` |

## Parameters

- `max_turns` (default `1000`): the number of rounds to survive. It counts rounds, not individual actions.
- `start_chips` (default `1000`): starting chips; it must cover at least one Ante and Blind.
- `ante_amount` (default `25`): the Ante and the Blind; Play bets are multiples of it.

## Notes

- The optional Trips side bet is not offered.
- The reward depends only on whether you survive every round, not on how many chips you end with; the house edge
  makes long games hard to survive.
