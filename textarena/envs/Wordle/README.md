# Wordle

Guess a secret English word in a limited number of tries, using per-letter feedback that marks each letter as correct,
misplaced, or absent ([rules](https://en.wikipedia.org/wiki/Wordle)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Wordle-v1` | `hardcore=False`, `word_length=5`, `num_guesses=6` |
| `Wordle-v1-hardcore` | `hardcore=True`, `word_length=5`, `num_guesses=6` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Wordle-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Wordle-v1", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, a secret word of `word_length` letters is drawn (see Notes for the word lists). You have `num_guesses`
  guesses.
- Each guess must be a `word_length`-letter word from the game's dictionary, and you cannot repeat a guess.
- Every letter of an accepted guess gets feedback: `G` (green) for the right letter in the right position, `Y` (yellow)
  for a letter that is elsewhere in the word, and `X` for a letter that is not in the word. Repeated letters work as in
  the original game: greens are marked first, then yellows from left to right, and each letter of the secret word
  accounts for at most one `G` or `Y`.
- You win as soon as a guess is all green. Otherwise the game ends after `num_guesses` accepted guesses.
- A rejected guess (wrong length, not in the dictionary, already guessed, or not a single word of letters) does not use
  up a guess. Two rejected guesses in a row end the game.
- `hardcore` only changes the list the secret word is drawn from. It is not the Hard Mode of the original game:
  revealed hints never restrict later guesses.

## Actions

Reply with a single word made of letters only, for example `crane`. Case does not matter.

## Observations

The prompt states the word length, the number of guesses, and the rules. After each accepted guess that is not the
answer, you see the guess, its feedback, and the guesses left:

```
You submitted 'crane'.
Feedback:
C R A N E
X X X Y Y
You have 5 guesses left.
```

A rejected guess is answered with the reason. If you run out of guesses, the secret word is revealed.

## Rewards

| Outcome | Reward |
| --- | --- |
| Secret word guessed | `+1` |
| All guesses used | Score of your best guess, (greens + 0.5 × yellows) / `word_length`, from `0` to `1` |
| Second consecutive rejected guess | Score of your best guess so far (`0` before any accepted guess) |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `word_length` (default `5`): The number of letters in the secret word and in every guess. Accepts an integer of at least 1.
- `num_guesses` (default `6`): The number of accepted guesses allowed. Accepts an integer of at least 1.
- `hardcore` (default `False`): Draw the secret word from every headword of the dictionary instead of Basic English.
<!-- END GENERATED: parameters -->

## Notes

- Guesses are checked against the English word list bundled in `textarena/utils/word_lists.py`: every word of the UK
  and US Hunspell dictionaries with its regular inflections (plurals, past tenses, and so on), about 101,000 words.
  Proper nouns are rejected, and the same guesses are accepted on every machine.
- Secret words come from the same module and need no downloads. By default they are the words of the right length in
  Ogden's Basic English list (850 words, 192 of them with five letters and 81 with seven). In hardcore mode they are
  the dictionary headwords of the right length (base words without inflections, about 3,300 with five letters and
  5,500 with seven). A length that the chosen list lacks falls back to any dictionary word of that length.
