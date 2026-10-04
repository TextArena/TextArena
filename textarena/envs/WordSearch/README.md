# Word Search

Find five listed words hidden across or down in a grid of random letters by naming the start and end cells of each
word. It tests scanning a text grid and reporting coordinates precisely.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `WordSearch-v0` | `hardcore=False` |
| `WordSearch-v0-hardcore` | `hardcore=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `WordSearch-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("WordSearch-v0", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, five words are drawn from a bundled list of common words (or from every dictionary headword in hardcore
  mode; see Notes). Each is placed in a square grid either across (left to right) or down (top to bottom), sometimes
  crossing another word on a shared letter. The remaining cells are filled with random letters.
- The player is told which words to find.
- Each turn, you name the start and end cells of one word. A guess is correct only if the two cells are exactly the
  endpoints of a hidden word; they may be given in either order.
- You have 20 incorrect attempts. An in-bounds new guess that does not match a word uses one; a correct guess never
  does.
- Repeating an earlier guess (in either order), naming a cell outside the grid, or a malformed reply is an invalid
  move. It uses neither a guess nor an incorrect attempt, but two invalid moves in a row end the game.
- The game ends when all five words are found or when the 20th incorrect attempt is used, so a game lasts at most
  24 guesses. An explicit `max_turns` below 25 can end it earlier (see Parameters).

## Actions

Reply with `start_row start_col end_row end_col` and nothing else: four 0-indexed numbers (as labeled `R..` and
`C..` on the board), separated by spaces.

Examples: `0 0 0 3` selects a word across row 0 from column 0 to column 3; `2 5 6 5` selects a word down column 5 from
row 2 to row 6.

## Observations

The player first receives the rules, including the number of incorrect attempts (and the total-guess cap when one is
set below 25). Before every guess, the player sees the grid with rows labeled `R00`, `R01`, … and columns `C00`,
`C01`, …, with the letters of found words in square brackets, followed by the list of words to find and the number
of incorrect attempts remaining. After each guess, the player is told whether it was correct (and which word it
found) or incorrect.

## Rewards

| Outcome | Reward |
| --- | --- |
| All five words found | `+1` |
| All 20 incorrect attempts used, or an explicit `max_turns` reached | Fraction of words found (`0` to `0.8`) |
| Second consecutive invalid move | Fraction of words found |

## Parameters

- `hardcore` (default `False`): draw the words from every dictionary headword (about 38,700 words, many of them rare)
  instead of the 14,700 common words.
- `max_turns` (default `None`): an optional cap on the total number of guesses, correct or incorrect. The default cap
  is 25 (five words plus 20 incorrect attempts), which a game can never reach; it only guarantees termination. A
  smaller value can end the game while incorrect attempts remain, and the prompt then states it.

## Notes

- Both word lists are bundled in `textarena/utils/word_lists.py`: `get_common_words()` (about 14,700 base words of 3
  to 8 letters that both the UK and the US dictionary contain and that take a regular inflection) and, in hardcore
  mode, `get_headwords()` (about 38,700 base words of 3 or more letters). A seed produces the same board on every
  machine.
