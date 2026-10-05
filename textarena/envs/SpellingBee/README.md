# Spelling Bee

Two players take turns naming English words built only from a shared set of letters, each word at least as long as the
previous one, until one of them cannot continue or the turn limit is reached.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `SpellingBee-v1` | `num_letters=7` |

Append `-mdp` to any ID for the state-complete variant (e.g. `SpellingBee-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("SpellingBee-v1", num_letters=...)`.
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
- After `max_turns` accepted words (default 50, counting both players) the game ends in a draw. Rejected words do not
  count toward the limit.

## Actions

Reply with exactly one word made of letters only, at most 64 letters long, for example `bean`. Case does not matter.

## Observations

Each player first receives the allowed letters and the rules. Before every move, the acting player sees a board with the
allowed letters and the full word history (which player played each word, and its length). Both players see every
accepted word, announced as `Player 0 submitted the word: bean`; a rejected word and its reason are shown only to the
player who submitted it. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Second consecutive invalid word | Offender `-1`, opponent `+1` |
| `max_turns` accepted words without a loss | Both `0` (draw) |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `num_letters` (default `7`): The size of the letter set. Accepts an integer from 1 to 26.
- `max_turns` (default `50`): The number of accepted words, counting both players, before the game ends in a draw. Accepts an integer of at least 1.
- `is_word` (default `is_english_word`): A function that receives a lowercase word and returns whether it counts, for example to use a custom word list. The default is `is_english_word` from `textarena/utils/word_lists.py`. If it raises an exception, the submission is not counted and the player is asked to retry. Accepts a function that takes a word and returns whether it counts.
<!-- END GENERATED: parameters -->

## Notes

- Words are checked against the English word list bundled in `textarena/utils/word_lists.py`: every word of the UK
  and US Hunspell dictionaries with its regular inflections (plurals, past tenses, and so on). The same words are
  accepted on every machine.
- Of the single letters, only `a` and `i` count as words.
- Despite the name, this is not the New York Times Spelling Bee, a single-player puzzle where every word must contain a
  required center letter and have at least four letters, and words score points (with a bonus for pangrams that use
  all seven letters). Here two players duel with no center letter, no minimum length and no points; the only
  constraints between words are the non-decreasing length and no repeats. The letters are drawn at random, so a set
  is not guaranteed to contain a vowel or a pangram.
