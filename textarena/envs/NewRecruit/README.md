# New Recruit

A recruiter and a job candidate negotiate an eight-term employment package, each scoring deals with a private point
table, and once a proposal is accepted the player with the higher score wins
([exercise](https://ocw.mit.edu/courses/15-668-people-and-organizations-fall-2010/6a0dea19984ff5548ea5f3197c3667ad_MIT15_668F10_lec15.pdf)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the full transcript, including every player action

| Env ID | Parameters |
| --- | --- |
| `NewRecruit-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `NewRecruit-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Player 0 is the Recruiter and Player 1 the Candidate. The Recruiter moves first and the players alternate.
- A package picks one of five options (A–E) for each of eight issues, always in this order. Points are
  Recruiter / Candidate; each player only knows their own column:

  | Issue | A | B | C | D | E |
  | --- | --- | --- | --- | --- | --- |
  | Salary | $60000 (-6000 / 0) | $58000 (-4500 / -1500) | $56000 (-3000 / -3000) | $54000 (-1500 / -4500) | $52000 (0 / -6000) |
  | Signing Bonus | 10% (0 / 4000) | 8% (1000 / 3000) | 6% (2000 / 2000) | 4% (3000 / 1000) | 2% (4000 / 0) |
  | Job Assignment | Division A (0 / 0) | Division B (-600 / -600) | Division C (-1200 / -1200) | Division D (-1800 / -1800) | Division E (-2400 / -2400) |
  | Company Car | LUX EX2 (1200 / 1200) | MOD 250 (900 / 900) | RAND XTR (600 / 600) | DE PAS 450 (300 / 300) | PALO LSR (0 / 0) |
  | Starting Date | Jun 1 (1600 / 0) | Jun 15 (1200 / 1000) | Jul 1 (800 / 2000) | Jul 15 (400 / 3000) | Aug 1 (0 / 4000) |
  | Vacation Days | 30 days (0 / 1600) | 25 days (1000 / 1200) | 20 days (2000 / 800) | 15 days (3000 / 400) | 10 days (4000 / 0) |
  | Moving Expense Reimbursement | 100% (0 / 3200) | 90% (200 / 2400) | 80% (400 / 1600) | 70% (600 / 800) | 60% (800 / 0) |
  | Insurance Coverage | Allen Insurance (0 / 800) | ABC Insurance (800 / 600) | Good Health Insurance (1600 / 400) | Best Insurance Co. (2400 / 200) | Insure Alba (3200 / 0) |

- On your turn you either propose a package, which replaces any proposal on the table, or answer the proposal you
  received: accepting ends the game, rejecting clears it and passes the turn.
- When a proposal is accepted, each player adds up their own points for it; the higher total wins and equal totals
  draw. If no proposal is accepted within `max_turns` turns (counting both players), the game is a draw.

## Actions

- **Propose:** optional free-text rationale, then a final line with `Propose` and one letter per issue in the order
  above (case-insensitive; spaces between letters are accepted):

  ```
  I can start in August if you meet me halfway on salary.
  Propose CBAAECDA
  ```

- `Accept` or `Reject` answers the proposal you received and must be the whole reply.

A reply is invalid if it is anything else: for example, text after the `Propose` line, a rationale line that is
itself a command, the wrong number of letters, or `Accept`/`Reject` when there is no proposal from your opponent.

## Observations

Each player first receives their own point table, the issue order, the actions, the scoring rule, and the turn limit.
Before every move, the acting player sees the turn counter (`Turn 2 of 10`) and, if a proposal is on the table, its
letter sequence with every option scored by their own points and the total. Both players see each other's full
replies (rationale included) and announcements of every new proposal, rejection, and acceptance. The opponent's
point table is never shown; the final result message reveals both scores.

## Rewards

| Outcome | Reward |
| --- | --- |
| Accepted proposal with a higher score | Winner `+1`, loser `-1` |
| Accepted proposal with equal scores | Both `0` |
| Turn limit without an accepted proposal | Both `0` |
| Fourth consecutive invalid move (with the default `error_allowance=3`) | Offender `-1`, opponent `+1` |

## Parameters

- `max_turns` (default `10`): turns in the whole game, counting both players.
- `error_allowance` (default `3`): consecutive invalid moves a player may make (and retry) before losing.

## Notes

- Issue types: Salary and Signing Bonus are distributive (opposed preferences), Job Assignment and Company Car are
  compatible (identical preferences), and the other four are integrative (opposed, but valued differently by each
  side, so trading them off creates value). Both point tables range from -8400 to 14800.
- Unlike the classroom exercise, the result is zero-sum: a deal only wins if it scores more for you than for your
  opponent, whose table you cannot see. Compatible issues add the same points to both sides and never decide the
  winner.
- References: M. A. Neale (1997), *New Recruit*, Dispute Resolution Research Center, Kellogg School of Management,
  Northwestern University; MIT OpenCourseWare 15.668 People and Organizations (Fall 2010),
  [New Recruit negotiation](https://ocw.mit.edu/courses/15-668-people-and-organizations-fall-2010/6a0dea19984ff5548ea5f3197c3667ad_MIT15_668F10_lec15.pdf).
