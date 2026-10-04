# Cryptarithm

Solve an alphametic such as SEND + MORE = MONEY by giving each letter a different digit so that the sum is correct
([verbal arithmetic](https://en.wikipedia.org/wiki/Verbal_arithmetic)). It tests systematic reasoning about column
sums and carries.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Cryptarithm-v0` | `equation="SEND + MORE = MONEY"`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Cryptarithm-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Cryptarithm-v0", equation=...)`.
<!-- END GENERATED: variants -->

## Rules

- The puzzle is a sum of words, `WORD + WORD + … = WORD`, set by the `equation` parameter. There is no randomness,
  so the seed has no effect.
- Each letter stands for one digit, and different letters stand for different digits. The first letter of every word,
  including the result, cannot be 0.
- Each move assigns a digit to one letter (replacing the letter's previous digit, if any) or clears a letter, which
  frees its digit for another letter. A digit that another letter is using cannot be assigned until that letter is
  cleared or changed.
- You win as soon as every letter has a digit and the equation holds. If every letter is assigned but the sum is
  wrong, you are told so and can keep changing letters.
- A letter that is not in the puzzle, a digit used by another letter, 0 for a leading letter, clearing a letter that
  has no digit, or a malformed reply is an invalid move. It changes nothing and does not count as a move. Two invalid
  moves in a row end the game.
- The game ends after `max_turns` valid moves.

## Actions

Reply with a letter and a digit, separated by a space or a comma (case-insensitive), or with a letter and `-` to clear
that letter.

Examples: `S 9` gives S the digit 9; `S -` removes S's digit.

## Observations

The player first receives the rules, including the puzzle, its leading letters, and the move limit. Before every move,
the player sees the equation, the same equation with the assigned digits filled in (`_` for letters without a digit),
the current mapping, and how many letters have a digit:

```
SEND + MORE = MONEY
9___ + ____ = _____
Mapping:
  S → 9
Assigned: 1/8 (12%)
```

## Rewards

Unless you solve the equation, you score the fraction of letters that have the correct digit: the number of letters
whose digit matches a solution, divided by the number of letters. If the equation has several solutions, the one that
matches the most letters counts. Letters without a digit and letters with a wrong digit earn nothing, so the starting
position, and any guesses that match no solution, score `0`. A complete but wrong mapping earns credit for its correct
letters, and the score stays below `1` unless the equation is solved.

| Outcome | Reward |
| --- | --- |
| Equation solved | `1` |
| `max_turns` valid moves made | Fraction of letters with the correct digit (`0` to below `1`) |
| Second consecutive invalid move | Same as at the turn limit |

## Parameters

- `equation` (default `"SEND + MORE = MONEY"`): the puzzle, written as words of letters joined by `+`, then one `=`
  and the result (spaces optional, case-insensitive). It may use at most 10 distinct letters, 20 addends, 64 letters
  per word, and 512 characters, and must have at least one solution without leading zeros; otherwise the constructor
  raises `ValueError`. Very long sums with many addends are also rejected, so that the solvability check stays fast.
- `max_turns` (default `100`): the number of valid moves allowed.

## Notes

- The board shows how many letters have a digit, not how many are correct, so the partial score is only revealed when
  the game ends. For example, `A 1`, `B 5` in `A + B = C` scores `2/3` (1 + 5 = 6 is a solution), while `C 2` scores
  `0` (the sum of two different nonzero digits is at least 3).
