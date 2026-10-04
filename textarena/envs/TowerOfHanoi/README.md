# Tower of Hanoi

Move a stack of disks from tower A to tower C one disk at a time, never placing a larger disk on a smaller one
([rules](https://en.wikipedia.org/wiki/Tower_of_Hanoi)). The shortest solution doubles with every disk (`2ⁿ − 1` moves
for `n` disks), so it tests long, exact sequential planning.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `TowerOfHanoi-v0` | `num_disks=3`, `max_turns=14` |
| `TowerOfHanoi-v0-extreme` | `num_disks=7`, `max_turns=254` |
| `TowerOfHanoi-v0-hard` | `num_disks=5`, `max_turns=62` |
| `TowerOfHanoi-v0-hardcore` | `num_disks=6`, `max_turns=126` |
| `TowerOfHanoi-v0-medium` | `num_disks=4`, `max_turns=30` |

Append `-mdp` to any ID for the state-complete variant (e.g. `TowerOfHanoi-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The disks are numbered by size, from 1 (smallest) to `num_disks`, and start stacked on tower A with the largest at
  the bottom. Towers B and C start empty.
- Each move takes the top disk of one tower and puts it on another tower that is empty or whose top disk is larger.
- You win when every disk is on tower C.
- Moving from an empty tower, onto a smaller disk, or onto the same tower, or a malformed reply (including a tower
  other than A, B, or C) is an invalid move. It changes nothing and does not count as a move. Two invalid moves in a
  row end the game.
- The game ends after `max_turns` valid moves.

## Actions

Reply with the source tower and the target tower, separated by a space or a comma (case-insensitive).

Example: `A C` moves the top disk of tower A onto tower C.

## Observations

The player first receives the rules, the number of disks, and the move limit. Before every move, the player sees each
tower's disks listed from bottom to top; after each valid move, they are told which disk moved, for example
`You moved disk 1 from A to C.`

```
Current Board (disks listed bottom to top):
A: [3, 2]
B: []
C: [1]
```

## Rewards

| Outcome | Reward |
| --- | --- |
| Every disk on tower C | `1` |
| `max_turns` valid moves made | Fraction of disks correctly stacked from the base of tower C |
| Second consecutive invalid move | Fraction of disks correctly stacked from the base of tower C |

Disks count as correctly stacked from the bottom of tower C upward, starting with the largest disk and stopping at
the first disk that is out of place.

## Parameters

- `num_disks` (default `3`): the number of disks, from 1 to 20.
- `max_turns` (default `100`): the number of valid moves allowed. It must be at least `2^num_disks − 1`, the length of
  the shortest solution. The registered variants allow about twice that (`2^(num_disks + 1) − 2`).

## Notes

- `renderer.py` draws the towers as ASCII art for the visual renderer (`get_board_str`); players see the lists shown
  above.
