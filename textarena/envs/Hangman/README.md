# Hangman

Reveal a hidden English word by guessing one letter at a time, or the whole word, before six wrong guesses run out
([rules](https://en.wikipedia.org/wiki/Hangman_%28game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Hangman-v0` | `hardcore=False` |
| `Hangman-v0-hardcore` | `hardcore=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Hangman-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Hangman-v0", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, a secret word of at least three letters is drawn (see Notes for the word lists). You have 6 tries.
- Guessing a letter reveals every position where it occurs. A letter that is not in the word costs a try.
- Guessing a whole word wins at once if it is the secret word. Any other word costs a try; it does not have to be a
  real word or have the right length.
- You win when every letter is revealed or you guess the word, and lose when the tries run out.
- Repeating a letter or word you already guessed, or replying with anything other than letters, is rejected without
  costing a try. Two rejected replies in a row end the game.

## Actions

Reply with a single letter (`e`) or a whole word (`light`), letters only. Case does not matter.

## Observations

Before every guess you see the board with numbered columns and an underscore for each hidden letter, the tries left,
and the letters guessed so far:

```
Current board:

C00 C01 C02 C03
  S   _   _   _
You have 5 tries left.
Guessed letters: E, S
```

After each guess you are told whether the letter is in the word, or that the guessed word is wrong. The secret word is
revealed when you run out of tries.

## Rewards

| Outcome | Reward |
| --- | --- |
| Word completed or guessed | `+1` |
| Out of tries | Fraction of the word's letters revealed (`0` up to just below `1`) |
| Second consecutive rejected reply | Fraction of the word's letters revealed so far |

## Parameters

- `hardcore` (default `False`): draw the secret word from every dictionary headword instead of Basic English.

## Notes

- Secret words come from `textarena/utils/word_lists.py` and need no downloads. By default they are the 832 words of
  Ogden's Basic English list with three or more letters (common words such as `water`, `answer`, or `light`). In
  hardcore mode they are the headwords of the bundled UK and US dictionaries (about 38,700 base words without
  inflected forms, many of them rare). Neither list contains proper nouns, and a seed picks the same word on every
  machine.
