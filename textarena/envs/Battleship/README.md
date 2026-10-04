# Battleship

Two players each hide five ships on a grid and take turns firing at the opponent's grid; whoever sinks the entire
enemy fleet first wins ([rules](https://en.wikipedia.org/wiki/Battleship_%28game%29)). It tests searching efficiently
and following up on hits under hidden information.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Battleship-v0` | `grid_size=5` |
| `Battleship-v0-extreme` | `grid_size=20` |
| `Battleship-v0-large` | `grid_size=14` |
| `Battleship-v0-standard` | `grid_size=10` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Battleship-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Each player has a `grid_size`×`grid_size` grid with rows lettered from `A` and columns numbered from `0`. At reset,
  five ships are placed at random on each grid, horizontally or vertically, without overlapping (ships may touch):

  | Ship | Initial | Length |
  | --- | :---: | :---: |
  | Aircraft Carrier | `A` | 5 |
  | Battleship | `B` | 4 |
  | Submarine | `S` | 3 |
  | Destroyer | `D` | 3 |
  | Patrol Boat | `P` | 2 |

- Player 0 fires first, and the players alternate one shot per turn.
- Each shot is a hit or a miss, and both players are told which. When a shot hits the last remaining cell of a ship,
  both players are also told which ship sank.
- Firing outside the grid or at a coordinate you have already fired at is an invalid move.
- The first player to sink all five enemy ships wins immediately. There are no draws and no turn limit: every valid
  shot uses a new coordinate, so the game always ends.

## Actions

Reply with a row letter followed by a column number, e.g. `C4` (row C, column 4). The letter is case-insensitive, and
a space between the letter and the number is allowed (`c 4`).

## Observations

Each player first receives the rules, including the grid size, the coordinate ranges, and the fleet. Before every
move, the acting player sees two grids side by side:

- **Your Ships**: their own fleet by initial (`A`, `B`, `S`, `D`, `P`), `~` for water, and `X` / `O` where the
  opponent has hit / missed.
- **Your Hits on Opponent**: `X` for their hits, `O` for their misses, and `~` for coordinates not yet fired at.

After every shot, the shooter is told whether it hit, missed, or sank a ship (and which one), and the opponent is told
the same about the shot against them. The coordinate of every shot is visible to both players. The opponent's ship
positions are never shown.

## Rewards

| Outcome | Reward |
| --- | --- |
| Sinking the last enemy ship | Winner `+1`, loser `-1` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

- `grid_size` (default `10`): the side length of both grids, from 5 to 26 (rows use the letters `A` to `Z`). The fleet
  is the same on every grid size, so on the 5×5 grid it fills 17 of the 25 cells.
