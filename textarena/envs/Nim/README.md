# Nim

Players take turns removing one or more objects from a single pile, and whoever takes the last object wins
([rules](https://en.wikipedia.org/wiki/Nim)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Nim-v0` | `piles=[3, 4, 5]` |
| `Nim-v0-large` | `piles=[5, 7, 9, 11, 2]` |
| `Nim-v0-medium` | `piles=[4, 2, 3, 7]` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Nim-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The game starts with the piles given by `piles`. Player 0 moves first.
- On your turn, remove at least one object from exactly one pile; you may take the whole pile.
- Whoever takes the last object wins (normal play). There are no draws.

## Actions

Reply with the pile number and how many objects to remove, separated by a space. Piles are numbered from `0`.

Example: `2 3` removes three objects from pile 2.

## Observations

Each player first receives the rules. Before every move, the acting player sees the size of every pile. Both players
see every removal.

## Rewards

| Outcome | Reward |
| --- | --- |
| Took the last object | Winner `+1`, loser `-1` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `piles` (default `[3, 4, 5]`): starting pile sizes. A non-empty list of at most 100 non-negative integers, each at
  most 1,000,000, holding at least one object in total.

## Notes

- Nim is solved: the player to move wins with perfect play exactly when the XOR of the pile sizes (the nim-sum) is not
  zero. Every registered starting position has a non-zero nim-sum, so Player 0 can always force a win.
