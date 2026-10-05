# Pig Dice

Two players race to a target score by rolling a die to build up a turn total and deciding when to bank it, since
rolling a 1 wipes out the points from that turn ([rules](https://en.wikipedia.org/wiki/Pig_%28dice_game%29)). It tests
risk management under chance and adapting to the opponent's score.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `PigDice-v1` | `winning_score=100`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `PigDice-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("PigDice-v1", winning_score=...)`.
<!-- END GENERATED: variants -->

## Rules

- Both players start with a banked score of 0. Player 0 goes first.
- On your turn, you either roll a six-sided die or hold, and you may roll as many times as you like:
  - Rolling 2–6 adds the number to your turn total, and you act again.
  - Rolling a 1 is a bust: you lose your turn total and the turn passes to your opponent.
  - Holding adds your turn total to your banked score and passes the turn. Holding with a turn total of 0 is allowed.
- The first player whose banked score reaches `winning_score` wins immediately.
- Every action (each roll and each hold, by either player) counts toward `max_turns`. When the limit is reached, the
  player with the higher banked score wins; unbanked turn totals do not count, and equal scores are a draw.

## Actions

Reply with exactly one word and nothing else (case-insensitive):

- `roll` rolls the die.
- `hold` banks your turn total and ends your turn.

## Observations

Each player first receives the rules, including the target score and the turn limit. Before every action, the acting
player sees both banked scores, their current turn total, and the rolls made so far this turn. Both players see every
roll, bust, and hold, followed by the updated scores whenever a turn ends. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Banked score reaches `winning_score` | Winner `+1`, loser `-1` |
| `max_turns` reached with different banked scores | Higher score `+1`, lower score `-1` |
| `max_turns` reached with equal banked scores | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `winning_score` (default `100`): The banked score needed to win. Accepts an integer from 1 to 1000000.
- `max_turns` (default `500`): The total number of actions, counting every roll and hold by both players, before the game is decided by banked score. Since rolls count as well, a configuration whose `max_turns` is small relative to `winning_score` is usually decided at the limit rather than by reaching the target. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->
