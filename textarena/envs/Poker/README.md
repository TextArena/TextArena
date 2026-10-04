# Texas Hold'em Poker

Two to fifteen players play a fixed number of no-limit Texas Hold'em hands and are ranked by their final chip counts
([rules](https://en.wikipedia.org/wiki/Texas_hold_%27em)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–15

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Poker-v0` | `num_rounds=10`, `starting_chips=1000`, `small_blind=10`, `big_blind=20` |
| `Poker-v0-extreme` | `num_rounds=50`, `starting_chips=1000`, `small_blind=10`, `big_blind=20` |
| `Poker-v0-long` | `num_rounds=15`, `starting_chips=1000`, `small_blind=10`, `big_blind=20` |
| `Poker-v0-small` | `num_rounds=5`, `starting_chips=1000`, `small_blind=10`, `big_blind=20` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Poker-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Everyone starts with `starting_chips` chips and the game lasts `num_rounds` hands.
- **Positions and blinds:** the button (Dealer) starts at Player 0 and moves to the next player still in the game
  after every hand. The two players after the button post the small and big blinds; heads-up, the button posts the
  small blind. A player who cannot cover a blind posts what they have and is all-in, but the amount to call pre-flop
  is still the full big blind.
- Each player gets two private hole cards. There are four betting rounds: pre-flop, flop (three community cards),
  turn (a fourth) and river (a fifth). Pre-flop, the player after the big blind acts first (heads-up, the button);
  after the flop, the first player still in the hand after the button acts first.
- On your turn you may fold, check (when there is nothing to call), call, bet (when nobody has bet this round; at
  least the big blind) or raise (by at least the previous full bet or raise). A smaller bet or raise is only allowed
  as an all-in, and a short all-in raise does not let players who have already acted raise again. Asking for more
  than your stack puts you all-in.
- A betting round ends once every player who can still act has acted and matched the current bet. If everyone else
  folds, the last player wins the pot without a showdown and unseen community cards stay hidden. If at most one player
  can still bet, the remaining community cards are dealt out.
- **Showdown:** each player's best five-card hand out of their two hole cards and the five community cards, with
  standard rankings (an ace can also play low in A-2-3-4-5). Side pots are formed from each player's total
  contribution; tied hands split a pot, and odd chips go to the tied winners closest to the button's left.
- Players with no chips left are eliminated. The game ends after `num_rounds` hands, or earlier when one player holds
  all the chips.

## Actions

Reply with exactly one command (case-insensitive): `check`, `call`, `fold`, `bet N` or `raise N`, where `N` is the
number of chips added on top of the current bet. Your board lists the amount to call and the exact range of `N` you
may use.

Examples: `call`, `bet 40`, `raise 60`, `raise 100000` (all-in).

## Observations

Each player first receives the number of hands, the starting stack and the blinds. Before every action the acting
player sees the hand number and betting round, the pot and the current bet, the visible community cards, every
player's chips, current bet and status (active, folded, all-in, eliminated or sitting out) with the Dealer and blind
positions, their own hole cards, the amount they must call, and their legal options with the allowed amounts. Everyone
sees every action; at a showdown all remaining players' hole cards are revealed along with each pot's winner.

## Rewards

Players are ranked by their chips at the end. Rewards go linearly from `+1` for the most chips to `-1` for the fewest;
players with equal chips share the average of their places, so rewards always sum to zero.

| Outcome | Reward |
| --- | --- |
| Two players, different chip counts | More chips `+1`, fewer `-1` |
| All players have equal chips | Everyone `0` |
| Second consecutive invalid move | Offender eliminated: their hand is folded and all their chips go into the pot, so they finish with 0 chips (last place); the others play on |

With two players, an elimination for invalid moves ends the game: the opponent wins `+1` and the offender gets `-1`.

## Parameters

- `num_rounds` (default `10`): number of hands.
- `starting_chips` (default `1000`): chips per player at the start.
- `small_blind` (default `10`) and `big_blind` (default `20`): the blinds; the small blind may not exceed the big
  blind.

## Notes

- Simplifications: the button simply moves to the next player still in the game (no dead-button rule), and there are
  no antes or rake.
