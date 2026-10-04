# Retro Space Duel

A turn-based two-player space shooter: steer your ship through an asteroid field, grab power-ups, and shoot the
enemy ship down without ever firing into a wall.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `RetroSpaceDuel-v1` | `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `RetroSpaceDuel-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("RetroSpaceDuel-v1", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- The arena (15×15 by default) is ringed by a boundary (`#`). Player 0's ship (`0`) starts at `(1, 1)` and Player
  1's ship (`1`) in the opposite corner. Asteroids (`A`), debris (`D`), nebulas (`~`), mines (`M`) and power-ups
  (`+`) are scattered at random, never on or next to a spawn.
- Players alternate turns, Player 0 first. Each turn is either a move or a shot.
- **Moving:** one cell in any of the 8 directions, or up to two cells after a speed power-up (only one when the move
  starts inside a nebula). The boundary, asteroids, debris and the enemy ship block movement: a move stops in front
  of a blocked cell, and a move whose first cell is blocked is invalid. Entering a nebula, mine or power-up ends the
  move.
- **Shooting:** a shot flies in a straight line and resolves instantly. It hits the enemy ship for 10 damage (5
  while the enemy has a shield charge, which the hit uses up), destroys the first debris, mine or power-up in its
  path, and passes through nebulas (a ship inside a nebula can still be hit). A shot that reaches the boundary or an
  asteroid ricochets back and destroys the shooter.
- **Mines:** entering one costs 20 health (10 with a shield charge, which it uses up).
- **Power-ups:** entering one grants a random upgrade: shield (recharged to 3 charges), speed (move up to two cells)
  or spread shot (every shot also fires two side projectiles 45° to either side; side projectiles that reach the
  boundary or an asteroid simply dissipate).
- Both ships start with 100 health. A ship at 0 health is destroyed and its player loses; if both ships are
  destroyed on the same turn, the duel is a draw. After `max_turns` turns in total, the ship with more health wins
  and equal health is a draw.

## Actions

Reply with exactly one bare action (case-insensitive):

- Move: `w` (up), `s` (down), `a` (left), `d` (right), `q` (up-left), `e` (up-right), `z` (down-left), `c`
  (down-right).
- Shoot: `f` followed by a direction key, e.g. `f a` shoots left.

Positions are `(x, y)`, where `x` is the column and `y` the row, so `w` decreases `y`.

## Observations

Each player first receives the rules and legend. Before every turn, the acting player sees the turn counter, the
arena with row and column numbers, and each ship's position, health, shields, speed and weapon. Both players see
every action and its effects (hits, ricochets, mines, power-ups).

## Rewards

| Outcome | Reward |
| --- | --- |
| A ship is destroyed (shot, mine or ricochet) | Survivor `+1`, destroyed ship `-1` |
| Both ships destroyed on the same turn | Both `0` |
| `max_turns` reached | More health `+1`, less health `-1`; equal health both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `grid_size` (default `(15, 15)`): The arena width and height, including the boundary ring. Accepts a (width, height) pair of integers of at least 5.
- `max_turns` (default `100`): The total number of turns, counting both players, before the duel is decided on health. Accepts a positive even integer, so both ships get the same number of turns.
- `num_asteroids` (default `5`): The number of asteroids to scatter. Accepts an integer of at least 0.
- `num_debris` (default `8`): The number of debris objects to scatter. Accepts an integer of at least 0.
- `num_nebulas` (default `3`): The number of nebulas to scatter. Accepts an integer of at least 0.
- `num_mines` (default `4`): The number of mines to scatter. Accepts an integer of at least 0.
- `num_powerups` (default `3`): The number of power-ups to scatter. Accepts an integer of at least 0.
<!-- END GENERATED: parameters -->
