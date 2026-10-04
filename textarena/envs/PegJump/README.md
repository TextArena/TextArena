# Peg Jump

Jump pegs over one another on a 15-hole triangular board until only one peg is left
([rules](https://en.wikipedia.org/wiki/Peg_solitaire)). It is the classic triangular peg solitaire, also known as the
Cracker Barrel peg game.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `PegJump-v1` | `initial_empty=5` |

Append `-mdp` to any ID for the state-complete variant (e.g. `PegJump-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("PegJump-v1", initial_empty=...)`.
<!-- END GENERATED: variants -->

## Rules

- The board is a triangle of 15 holes in rows of 1 to 5, numbered row by row from the apex:

  ```
          1
        2   3
      4   5   6
    7   8   9  10
  11  12  13  14  15
  ```

- Every hole starts with a peg except `initial_empty`.
- A move jumps one peg over an adjacent peg into the empty hole directly beyond it, in a straight line along a row or
  a diagonal. The jumped peg is removed. For example, with hole 5 empty, `12 5` jumps the peg in hole 12 over hole 8.
- The game ends when one peg remains (a win) or when no jump is possible. Every move removes a peg, so a game lasts
  at most 13 moves and needs no turn limit. Every starting hole has a solution that leaves one peg.
- A malformed reply or an illegal jump is an invalid move. Illegal jumps include a hole number outside 1–15, holes
  that are not two apart in a straight line, a missing peg in the source or middle hole, and an occupied target. An
  invalid move changes nothing, and the feedback says what was wrong. Two invalid moves in a row end the game.

## Actions

Reply with `source target`: the hole the jumping peg starts in and the empty hole it lands in, separated by a space or
a comma.

Examples: `12 5` and `14 5` are the two legal openings of `PegJump-v1`, where hole 5 starts empty.

## Observations

The player first receives the rules, including a legal opening move for the configured board. Before every move, the
player sees the number of pegs left, the triangle with each hole's number followed by `●` (peg) or `○` (empty), and
the list of legal jumps:

```
Pegs left: 14
              1●
           2●   3●
        4●   5○   6●
     7●   8●   9●  10●
 11●  12●  13●  14●  15●
Legal jumps: 12 5, 14 5
```

## Rewards

| Outcome | Reward |
| --- | --- |
| One peg left | `1` |
| No legal jump, more than one peg left | Fraction of the 13 jumps a full solution needs: `(14 − pegs left) / 13` |
| Second consecutive invalid move | `(14 − pegs left) / 13` (`0` before the first jump) |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `initial_empty` (default `1`): The hole that starts empty. Accepts an integer from 1 to 15.
<!-- END GENERATED: parameters -->
