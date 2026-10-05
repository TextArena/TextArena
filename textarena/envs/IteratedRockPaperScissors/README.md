# Iterated Rock-Paper-Scissors

Two players simultaneously throw rock, paper, or scissors for a fixed number of rounds, and whoever wins more rounds
wins ([rules](https://en.wikipedia.org/wiki/Rock_paper_scissors)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt and every game message (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `IteratedRockPaperScissors-v1` | `num_rounds=9` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedRockPaperScissors-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("IteratedRockPaperScissors-v1", num_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- Each round, both players choose rock, paper, or scissors. Moves are sealed: Player 0 moves first, but neither sees
  the other's move until both are in.
- Rock beats scissors, scissors beats paper, and paper beats rock. Identical moves tie the round.
- After `num_rounds` rounds, the player who won more rounds wins; equal round wins is a draw.

## Actions

Reply with `rock`, `paper`, or `scissors`, or the shorthand `r`, `p`, or `s` (case-insensitive), e.g. `paper`. Anything
else is invalid.

## Observations

Each player first receives the number of rounds and the rules. Your move is echoed only to you, with a confirmation of
the move it was read as. Once both moves are in, both players see both moves, the round result, and the score after
that round.

## Rewards

| Outcome | Reward |
| --- | --- |
| More round wins after `num_rounds` rounds | Winner `+1`, loser `-1` |
| Equal round wins | Both `0` |
| Second consecutive invalid move | Offender `-1`, opponent `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_rounds` (default `5`): The number of rounds. Accepts a positive integer.
<!-- END GENERATED: parameters -->
