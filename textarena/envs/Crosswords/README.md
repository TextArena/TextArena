# Crosswords

Fill in a small crossword grid one letter at a time, using clues that give each word's starting cell and direction.
It tests vocabulary, clue interpretation, and keeping track of positions on a text grid.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Crosswords-v0` | `hardcore=False`, `max_turns=30`, `num_words=3` |
| `Crosswords-v0-hardcore` | `hardcore=True`, `max_turns=30`, `num_words=3` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Crosswords-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, `num_words` words are drawn from the bundled word list. Each word gets a random direction (across or
  down) and one of its ten clues, chosen at random.
- The words are placed on a square grid, crossing on shared letters where possible. Letter cells start hidden as `_`;
  `.` cells are blocked.
- Each turn, you guess one letter for one cell. A correct letter is revealed on the board.
- A wrong letter, a blocked or out-of-bounds cell, or a cell that is already filled is an invalid move and leaves the
  board unchanged. Two invalid moves in a row end the game.
- You win by filling every letter cell.
- There is no turn limit. Each correct guess fills one cell and counts as a turn, so a game takes exactly as many
  turns as the puzzle has letter cells, which is never more than `max_turns` (see Parameters). Invalid moves do not
  count as turns.

## Actions

Reply with `row column letter`: the 0-indexed row and column (as labeled `R..` and `C..` on the board), separated by
spaces, followed by a single letter (case-insensitive). Only one guess per turn is accepted; commas, multiple letters,
or extra text make the move invalid.

Examples: `0 0 d` or `8 2 A`.

## Observations

The player first receives the rules. Before every guess, the player sees the grid with rows labeled `R00`, `R01`, …
and columns `C00`, `C01`, …, where `_` is an unfilled letter cell, `.` is a blocked cell, and correctly guessed
letters appear in uppercase. Below the grid is the numbered clue list. Each clue ends with the word's starting cell
and direction, and most clues state the word length, for example:

```
3. The part of a building that provides shelter from the sun. (4 letters): (6, 7, 'down')
```

## Rewards

| Outcome | Reward |
| --- | --- |
| Every letter cell filled | `+1` |
| Second consecutive invalid move (including a wrong letter) | Fraction of letter cells filled, from `0` to `1` |

## Parameters

- `hardcore` (default `False`): draw from the hardcore half of the word list (rare or technical words such as
  `palinurid` or `deambulatory`) instead of everyday vocabulary.
- `max_turns` (default `100`): caps the puzzle size. The sampled words' total length never exceeds it, so every game
  finishes within `max_turns` correct guesses. It is not enforced as a separate turn limit, which could never be
  reached. Construction fails if the `num_words` shortest words do not fit.
- `num_words` (default `5`): the number of words placed on the grid.

## Notes

- The words and clues live in `words_clues.jsonl`: 100 words (50 standard, 50 hardcore), each with ten clues.
- `utils/words_clues_generator.py` regenerates that file by sampling words from the NLTK `words` corpus and asking an
  LLM for clues through OpenRouter (requires `OPENROUTER_API_KEY`). Playing the game needs neither.
