# Santorini

Two or three players move builders around a 5×5 island and raise towers, winning by stepping a worker up onto the third
level ([rules](https://en.wikipedia.org/wiki/Santorini_%28game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–3

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `SantoriniBaseFixed-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `SantoriniBaseFixed-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

This is the base game without God Powers, with fixed starting positions instead of a placement phase.

- Each player has two workers. Turn order is Navy (Player 0), White (Player 1), then Grey (Player 2) in a three-player
  game. Workers start on fixed squares:
  - 2 players: Navy on C2 and B3, White on D3 and C4.
  - 3 players: Navy on C3 and B3, White on D3 and B4, Grey on D2 and D4.
- On your turn, **move** one of your workers to one of the eight adjacent squares that has no worker and no dome. It may
  climb at most one level, and may step down any number of levels.
- Then **build** with the worker you moved, on a square adjacent to its new position that has no worker and no dome
  (the square it just left counts). Building raises a square by one level, from 0 up to 3; building on level 3 adds a
  dome (shown as height 4).
- Moving a worker up from level 2 onto level 3 wins immediately; the turn ends without a build. Moving between two
  level-3 squares does not win.
- A player who cannot make a complete turn (a move followed by a build) loses. With three players, that player is
  eliminated, their workers are removed, and play continues; the last player remaining wins. A player who exceeds the
  invalid-move allowance is treated the same way.
- Every turn that does not win includes a build, and the board can take at most 100 builds (three levels and a dome on
  each of the 25 squares), so the game always ends.

## Actions

Reply with one token: worker id, starting square, destination square, and build square. Worker ids are the first letter
of the colour plus `1` or `2` (`N1`, `N2`, `W1`, `W2`, `G1`, `G2`). Squares are a row letter `A`–`E` (top to bottom)
followed by a column number `1`–`5` (left to right). Input is case-insensitive, and spaces between the parts are
accepted.

- `N1C2C3B2` moves Navy's worker 1 from C2 to C3 and builds on B2 (legal as Navy's first move in a two-player game).
- `N1C2C3` is enough for a winning move onto level 3, since no build follows; a build square, if given, is ignored.

## Observations

Each player first receives the rules and an example move that is legal for them at the start. Before every move, the
acting player sees the board and, when `show_valid` is on, the list of their own legal moves. Each cell shows its height
(0–3, or 4 for a dome) and any worker on it:

```
     1     2     3     4     5
  ┌─────┬─────┬─────┬─────┬─────┐
A │ 0   │ 0   │ 0   │ 0   │ 0   │ A
  ├─────┼─────┼─────┼─────┼─────┤
B │ 0   │ 0   │ 0 N2│ 0   │ 0   │ B
  ├─────┼─────┼─────┼─────┼─────┤
C │ 0   │ 0 N1│ 0   │ 0 W2│ 0   │ C
  ├─────┼─────┼─────┼─────┼─────┤
D │ 0   │ 0   │ 0 W1│ 0   │ 0   │ D
  ├─────┼─────┼─────┼─────┼─────┤
E │ 0   │ 0   │ 0   │ 0   │ 0   │ E
  └─────┴─────┴─────┴─────┴─────┘
```

Every player sees each move and build, and every elimination. When `is_open` is off, the board is not shown and
players have to track it from the announced moves.

## Rewards

| Outcome | Reward |
| --- | --- |
| A worker moves up onto level 3 | Mover `+1`, every other player `-1` |
| Every other player is blocked or eliminated | Last player `+1`, every other player `-1` |
| More than `error_allowance` consecutive invalid moves | With one opponent left: that opponent `+1`, every other player `-1`. With two opponents left: the offender is eliminated and play continues |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `is_open` (default `True`): Whether the acting player is shown the board.
- `show_valid` (default `True`): Whether the acting player is shown the list of their legal moves.
- `error_allowance` (default `10`): The number of consecutive invalid moves a player may make; the next one counts as the escalation above. Accepts an integer of at least 0.
<!-- END GENERATED: parameters -->

## Notes

- Santorini was designed by Gordon Hamilton and is published by Roxley Games. This version has no God Powers, no worker
  placement phase, and no four-player team mode.
