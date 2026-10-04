# Chopsticks

Each player has two hands of raised fingers and takes turns adding fingers to an opponent's hand or redistributing
their own; the first to knock out both of the opponent's hands wins
([rules](https://en.wikipedia.org/wiki/Chopsticks_%28hand_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Chopsticks-v0` | `max_turns=40` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Chopsticks-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Chopsticks-v0", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- Both players start with one finger on each hand (`[1, 1]`). Player 0 moves first.
- **Attack:** add the fingers of one of your live hands to one of the opponent's live hands. If the result is 5 or
  more, that hand dies (drops to 0). There is no wrap-around, so 3 + 4 also kills the hand.
- **Split:** redistribute your total fingers between your two hands, with 0–4 fingers per hand. The split must change
  your distribution; only swapping the two hands (for example `[1, 2]` to `[2, 1]`) is not allowed. A split may revive
  a dead hand (`[0, 2]` to `[1, 1]`) or empty one (`[1, 1]` to `[2, 0]`).
- You cannot attack with a dead hand, and you cannot attack a hand that is already dead.
- A player whose hands are both dead loses immediately.
- The game ends in a draw after `max_turns` valid moves, counting both players' moves.

## Actions

Reply with exactly one command and nothing else (case-insensitive). Hands are indexed `0` and `1`, matching their
positions in the board's `[a, b]` lists.

- `attack M O` attacks the opponent's hand `O` with your hand `M`.
- `split L R` sets your hands to `L` and `R` fingers, where `L + R` equals your current total.

Examples: `attack 0 1` adds your hand 0 to the opponent's hand 1; `split 2 0` turns `[1, 1]` into `[2, 0]`.

## Observations

Each player first receives the rules: both commands, the 0–4 finger limit and no-swap rule for splits, the dead-hand
rule, the winning condition, and the turn limit. Before every move, the acting player sees the current board
(`Player 0: [a, b]` and `Player 1: [c, d]`). Both players see every action together with a description of its
effect, such as `P0 attacks P1’s hand 0: it goes from 1 to 2.` There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Both opponent hands dead | Winner `+1`, loser `-1` |
| `max_turns` reached | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `max_turns` (default `40`): the number of valid moves, counting both players, before the game is declared a draw.
  It must be a positive integer.
