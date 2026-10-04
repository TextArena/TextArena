# Mastermind

Crack a hidden code of numbers by guessing and reading black-and-white peg feedback after each guess
([rules](https://en.wikipedia.org/wiki/Mastermind_%28board_game%29)). Black pegs count correct numbers in the correct
position; white pegs count correct numbers in the wrong position.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Mastermind-v0` | `code_length=4`, `num_numbers=6`, `max_turns=20`, `duplicate_numbers=False` |
| `Mastermind-v0-extreme` | `code_length=6`, `num_numbers=12`, `max_turns=50`, `duplicate_numbers=True` |
| `Mastermind-v0-hard` | `code_length=4`, `num_numbers=8`, `max_turns=30`, `duplicate_numbers=False` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Mastermind-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a secret code of `code_length` numbers from 1 to `num_numbers` is drawn. With `duplicate_numbers=False`
  all of its numbers are different; otherwise numbers may repeat.
- On your turn, guess the whole code. The feedback gives one black peg for each number in the correct position and one
  white peg for each remaining number that appears elsewhere in the code. Each number of the code is matched at most
  once, so repeated numbers are never over-counted.
- A guess must contain exactly `code_length` numbers between 1 and `num_numbers`. When duplicates are disabled, a
  guess may not repeat a number either, and no guess may repeat an earlier one. Breaking any of these rules, or a
  malformed reply, is an invalid move: it does not use a turn, but two invalid moves in a row end the game.
- You win by guessing the code exactly. Otherwise the game ends after `max_turns` guesses.

## Actions

Reply with the guess as `code_length` numbers separated by spaces (commas also work).

Examples: `1 2 3 4` for `Mastermind-v0`; `3 12 3 7 1 9` for `Mastermind-v0-extreme`, whose six-number codes use 1–12
and may repeat numbers.

## Observations

The player first receives the rules: the code length, the number range, whether numbers may repeat, and the guess
limit. Before every guess, the player sees the board: the hidden code as `[?]` slots and the history of guesses, with
🎯 for each black peg, ⚪ for each white peg, and ▫️ for each empty slot. After every guess that does not crack the
code, a message states the feedback in words, for example `Submitted '1 2 3 4'. Feedback: 0 black peg(s), 3 white
peg(s).` The final board reveals the code.

## Rewards

| Outcome | Reward |
| --- | --- |
| Code cracked | `1` |
| `max_turns` guesses used | Score of the last guess: `(black + 0.5 × white) / code_length` (below `1`) |
| Second consecutive invalid move | Score of the last guess (`0` if no guess was made) |

## Parameters

- `code_length` (default `4`): the number of positions in the code, from 1 to 256.
- `num_numbers` (default `6`): numbers range from 1 to this value, at most 1,000,000.
- `duplicate_numbers` (default `False`): allow repeated numbers in the code and in guesses. When `False`,
  `code_length` cannot exceed `num_numbers`.
- `max_turns` (default `20`): the maximum number of guesses.

## Notes

- Partial credit uses the most recent guess, not the best one, so an unlucky final guess can lower the score.
