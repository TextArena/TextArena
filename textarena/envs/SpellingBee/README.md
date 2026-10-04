# Spelling Bee

Two players take turns naming English words built only from a shared set of letters, each word at least as long as the
previous one, until one of them cannot continue.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `SpellingBee-v0` | `num_letters=7` |
| `SpellingBee-v0-large` | `num_letters=10` |
| `SpellingBee-v0-small` | `num_letters=4` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SpellingBee-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, `num_letters` different letters are drawn, weighted by how common they are in English (so `e`, `t`, and
  `a` show up far more often than `q` or `z`). Both players use the same letters.
- Player 0 starts and the players alternate. Each word must:
  - use only the allowed letters (any letter may be used any number of times),
  - be in the game's dictionary (UK and US spellings are accepted, proper nouns are not),
  - be at least as long as the previous word, and
  - not have been played before in the game.
- An invalid word is rejected and the same player tries again. A second invalid word in a row loses the game, which is
  how a player who cannot find a word is eliminated.
- There is no turn limit and no draw. The game always ends because words cannot repeat, but with many letters it can
  run long: a set of 10 letters typically allows over a thousand dictionary words.

## Actions

Reply with exactly one word made of letters only, at most 64 letters long, for example `bean`. Case does not matter,
and the word may be wrapped in square brackets.

## Observations

Each player first receives the allowed letters and the rules. Before every move, the acting player sees a board with the
allowed letters and the full word history (which player played each word, and its length). Both players see every
submission, and each accepted word is announced as `Player 0 submitted the word: bean`. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Second consecutive invalid word | Offender `-1`, opponent `+1` |

## Parameters

- `num_letters` (required, from 1 to 26): the size of the letter set.
- `dictionary` (default: the bundled dictionary): any object with an `is_english_word(word)` method, for example a
  custom word list. If the lookup raises an exception, the submission is not counted and the player is asked to retry.

## Notes

- Words are checked against the UK and US Hunspell word lists bundled in `textarena/utils/word_lists.py`, including
  their regular inflections (plurals, past tenses, and so on). The optional NLTK `words` corpus is not used, so the same
  words are accepted on every machine.
- The bundled dictionary lists every single letter as a word, so any allowed letter is a valid one-letter opening.
