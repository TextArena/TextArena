# Two Dollar

Two players negotiate in free text over how to split $2.00, each following secret role instructions such as a minimum
acceptable share or a strict word limit ([source](https://ocw.mit.edu/courses/15-667-negotiation-and-conflict-management-spring-2001/pages/lecture-notes/)).
Based on the classic negotiation-course exercise, it tests persuasion, bargaining under asymmetric information, and
following private constraints.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `TwoDollar-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `TwoDollar-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, each player is secretly assigned a role: two different roles drawn at random from the 17 in `roles/`,
  unless `player_roles` fixes them. Only the owner sees their role's instructions.
- Players alternate messages, starting with Player 0. Each message is optional persuasion text followed by exactly
  one decision:
  - A proposal names the amount you want for yourself; your opponent would get the rest. A new proposal replaces the
    standing one, so you can counter-offer without rejecting first.
  - Accepting takes the opponent's standing proposal and ends the game with that split.
  - Rejecting withdraws the opponent's standing proposal, so the next player has to make a new one.
  - You can only accept or reject a standing proposal made by your opponent.
- Each message counts as one round. If no proposal has been accepted by the end of round `max_rounds`, there is no
  deal and both players get $0. A proposal made in the final round cannot be accepted.
- When a deal is struck, enforced roles are checked, and a player who failed theirs has their share set to $0:
  - `50_cents`, `80_cents`, `1_dollar`, `1_30_dollar`, `1_60_dollar`: a share below $0.50, $0.80, $1.00, $1.30, or
    $1.60, respectively, becomes $0.
  - `x_rounds`: the player is told they only have `max_rounds // 2` rounds. Their share becomes $0 unless the deal
    was accepted within that many rounds. It doesn't matter who accepted, so having their own proposal accepted in
    time counts.
- Two roles are enforced on every message instead, by treating a violation as an invalid move. The message is
  rejected and the player must resend. Like any invalid move, `error_allowance + 1` rejected messages in a row (4 by
  default) forfeit the game. Violations separated by a valid move don't add up. The role texts state this threshold.
  - `say_little`: more than 15 words of persuasion text before the decision.
  - `high_tension`: lowering your own previous proposal by more than $0.01. Amounts are compared in whole cents, so
    a 1-cent concession is always allowed.
- The other nine roles (`another_chance`, `battle_ax`, `dependent`, `hard_time`, `imaginative`, `public_figure`,
  `tape_recorder`, `untrustworthy`, `vanilla`) are intentionally never checked. They only shape the player's persona.
  Their stated victory and failure conditions, such as "maintain good relationship", are shown to the player but
  don't affect rewards.

## Actions

End every message with exactly one decision on its own line (case-insensitive), with any persuasion text before it:

- `Propose $X.XX` asks for `$X.XX` for yourself, from $0.00 up to the total, with the dollar sign and at most two
  decimals. `Propose $1` and `Propose: $1.25` also work.
- `Accept` accepts the opponent's standing proposal.
- `Reject` rejects the opponent's standing proposal.

Example:

```
I covered the bus fare last time, so a little more for me seems fair.
Propose $1.20
```

A trailing `.` or `!` after a decision is fine. A line counts as a decision only if its first word is exactly the
command. Lines such as `Proposed split: …`, `Propose that we split it`, or `Accept this?` are persuasion text, and so
are the words "accept" and "reject" inside a sentence. A `Propose` line whose remainder is empty or starts with `$` or
a digit is a proposal attempt, and it must be well-formed: `Propose 1.50` without the dollar sign is invalid. A
message is invalid if it has no decision, more than one decision, or any text after the decision.

## Observations

Each player first receives the rules, the total, the round limit, and their own secret role instructions, including
the role's stated victory and failure conditions; the opponent's role is never shown. Before every move, the acting
player sees the round counter (`ROUND 3 of 20`) and the standing proposal, if any. The opponent receives each valid
message as its persuasion text followed by a description of the decision, such as
`Player 0 proposes: $1.50 for themselves, $0.50 for their opponent`. Invalid messages are never shown to the
opponent. At the end, both players see the final amounts after role checks.

## Rewards

| Outcome | Reward |
| --- | --- |
| Deal with unequal final shares | Larger share `+1`, smaller share `-1` |
| Deal with equal final shares (including both zeroed by role checks) | Both `0` |
| No deal after `max_rounds` rounds | Both `0` |
| Fourth consecutive invalid move (with the default `error_allowance=3`) | Offender `-1`, opponent `+1` |

Final shares are taken after role checks, so a player who fails a threshold or deadline role ends with $0 and cannot
win, even if the agreed split favored them. A $2.00 / $0.00 split is a win for the player who keeps the $2.00.

## Parameters

- `player_roles` (default `None`): two role names, such as `["vanilla", "50_cents"]`, for Players 0 and 1. `None`
  draws two different roles at random. Requesting `x_rounds` with `max_rounds` below 4 raises a `ValueError`.
- `total_amount` (default `2.00`): the amount to split. It must be positive, with at most two decimals.
- `max_rounds` (default `20`): the number of messages, counting both players, before the game ends without a deal.
  It also sets the `x_rounds` deadline to `max_rounds // 2`.
- `error_allowance` (default `3`): the number of consecutive invalid moves a player is warned about before the next
  one forfeits the game.

## Notes

- Each role is a JSON file in `roles/enforceable` or `roles/non_enforceable` with its instructions and its stated
  victory and failure conditions. These conditions are shown to the player, but rewards depend only on the final
  amounts.
- All amounts are tracked internally in whole cents, so thresholds and concessions are compared exactly.
- The earliest possible deal is accepted in round 2, so `x_rounds` needs a deadline of at least 2 rounds, which means
  `max_rounds` of at least 4. Below that, random assignment never draws `x_rounds`. Asking for it by name raises a
  `ValueError`, both at construction and at `reset()` if `max_rounds` was lowered in between.
