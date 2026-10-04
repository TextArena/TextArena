# Iterated Prisoner's Dilemma

Two players chat and then simultaneously choose to cooperate or defect for a fixed number of rounds, scoring points from
a prisoner's dilemma payoff matrix, and the higher total wins
([background](https://en.wikipedia.org/wiki/Prisoner%27s_dilemma)). It tests trust, persuasion, and retaliation over
repeated play.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `IteratedPrisonersDilemma-v0` | `num_rounds=10`, `communication_turns=1`, `cooperate_reward=3`, `defect_reward=5`, `sucker_reward=0`, `mutual_defect_reward=1` |
| `IteratedPrisonersDilemma-v0-short` | `num_rounds=5`, `communication_turns=1`, `cooperate_reward=3`, `defect_reward=5`, `sucker_reward=0`, `mutual_defect_reward=1` |

Append `-mdp` to any ID for the state-complete variant (e.g. `IteratedPrisonersDilemma-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The game lasts `num_rounds` rounds. Each round has `communication_turns` conversation turns followed by one decision.
  In each conversation turn Player 0 speaks first and Player 1 replies; with `communication_turns=0` every round starts
  with the decision.
- Decisions are simultaneous: Player 0 decides first, but neither sees the other's choice until the round is resolved.
- Each round pays out according to the payoff matrix, which is the same every round (default values shown, as
  Player 0 / Player 1):

  | | Player 1 cooperates | Player 1 defects |
  | --- | --- | --- |
  | **Player 0 cooperates** | `3` / `3` (`cooperate_reward`) | `0` / `5` (`sucker_reward` / `defect_reward`) |
  | **Player 0 defects** | `5` / `0` (`defect_reward` / `sucker_reward`) | `1` / `1` (`mutual_defect_reward`) |

- Payoffs add up over the rounds. After the last round, the higher total wins; equal totals are a draw.

## Actions

During conversation, reply with any text; it is shown to your opponent (sender labels such as `[GAME]` are removed).
Every message is valid, and words like "defect" in a message are never taken as a decision.

During the decision turn, reply with exactly `cooperate` or `defect` (case-insensitive). Anything else is invalid.

## Observations

Each player first receives the round structure, the payoff matrix, and how the match is won. The start of every round
and of every decision phase is announced, and each conversation message is shown to the opponent. Your decision is
echoed only to you. Once both players have decided, both see both decisions, what each player earned, and the running
totals.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher total payoff after the last round | Winner `+1`, loser `-1` |
| Equal totals | Both `0` |
| Second consecutive invalid decision | Offender `-1`, opponent `+1` |

## Parameters

- `num_rounds` (default `5`): number of rounds.
- `communication_turns` (default `3`): conversation turns before each decision, each one message per player; `0`
  skips conversation.
- `cooperate_reward` (default `3`): payoff to each player when both cooperate.
- `defect_reward` (default `5`): payoff to a defector whose opponent cooperates.
- `sucker_reward` (default `0`): payoff to a cooperator whose opponent defects.
- `mutual_defect_reward` (default `1`): payoff to each player when both defect.

The payoffs may be any integers, including negative ones; their ordering is not checked.

## Notes

- Only the comparison of totals decides the reward, so the match is zero-sum even though each round is not: mutual
  cooperation can at best draw, and a round only changes the standings when exactly one player defects. Players aiming
  to win should not simply maximize their own total as in the classic iterated dilemma.
