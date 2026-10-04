# Spelling Bee

Two players take turns naming English words built only from a shared set of letters, each word at least as long as the
previous one, until one of them cannot continue.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `SpellingBee-v0` | `num_letters=7` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SpellingBee-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("SpellingBee-v0", num_letters=...)`.
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

Reply with exactly one word made of letters only, at most 64 letters long, for example `bean`. Case does not matter.

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
- `is_word` (default: `is_english_word` from `textarena/utils/word_lists.py`): a function that receives a lowercase
  word and returns whether it counts, for example to use a custom word list. If it raises an exception, the submission
  is not counted and the player is asked to retry.

## Notes

- Words are checked against the English word list bundled in `textarena/utils/word_lists.py`: every word of the UK
  and US Hunspell dictionaries with its regular inflections (plurals, past tenses, and so on). The same words are
  accepted on every machine.
- Of the single letters, only `a` and `i` count as words.
