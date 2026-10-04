# Twenty Questions

Identify a hidden word from a known theme (a place, a person, or a thing) by asking an LLM game master up to 20
yes-or-no questions, then make a single final guess ([rules](https://en.wikipedia.org/wiki/Twenty_questions)). It
tests strategic questioning that narrows a large space of candidates.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `TwentyQuestions-v0` | `hardcore=False` |
| `TwentyQuestions-v0-hardcore` | `hardcore=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `TwentyQuestions-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("TwentyQuestions-v0", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, a theme (`places`, `people`, or `things`) is drawn at random, then a target word from that theme. The
  theme is revealed; the word is not. Targets can be one or two words, such as `police officer`.
- Each turn, you either ask one free-form question or make your guess.
- An LLM game master that knows the target answers every question with `Yes`, `No`, or `I don't know`.
- You may ask up to `max_turns - 1` questions (20 by default). The answer to the last one tells you that you have run
  out of questions; after that, only a guess is accepted, and asking another question is an invalid move.
- You get exactly one guess, and it ends the game. It must name the whole target, ignoring case, accents, punctuation,
  quotes, spacing, and a leading `a`, `an`, or `the` (so `guess a yoyo.` matches `yo-yo`); a partial match such as
  `apple` for `pineapple` is wrong.

## Actions

- Ask a question as plain text, for example `Is it found indoors?`
- Guess with `guess <word>` (or `guess: <word>`), for example `guess pharmacist` or `guess police officer`. The
  keyword and the word are case-insensitive.

Any message containing a question mark is a question, even if it starts with `guess` (`Guess what, is it alive?`).
Otherwise, a message that starts with the word `guess` is your final guess, and `guess` without a word is invalid.
Sender tags such as `[GAME]` and line breaks are removed from questions before they reach the game master; a question
without any letter or digit and messages longer than 4,000 characters are invalid.

## Observations

The player first receives the rules, the difficulty (Basic or Hardcore), the theme, and the number of questions
allowed. After each question, the game master's answer arrives as a separate message. Before every move, the player
also sees a status board with the number of questions asked out of the budget and the full question-and-answer
history. When the game ends, the board reveals the target word.

## Rewards

| Outcome | Reward |
| --- | --- |
| Correct guess | `+1` |
| Wrong guess | `0` |
| Second consecutive invalid move (such as a question after the budget is used up) | `-1` |

## Parameters

- `hardcore` (default `False`): draw from the hardcore list (150 uncommon words such as `astrolabe`, `sommelier`, or
  `catacombs`) instead of the basic list (257 everyday words such as `library`, `nurse`, or `banana`).
- `max_turns` (default `21`, minimum `2`): the total number of turns. The player may ask `max_turns - 1` questions,
  and the final turn is reserved for the guess.
- `gamemaster` (default: OpenRouter `openai/gpt-4o`): any callable that takes a prompt string and returns `Yes`,
  `No`, or `I don't know`. Inject one to play offline or with a different model.
- `words_path` (default: the bundled `twenty_questions_words.json`): an alternative word file with `basic` and
  `hardcore` sections, each mapping theme names to lists of words.

## Notes

- The default game master is created on the first question and needs the `openai` package and `OPENROUTER_API_KEY`.
  Guesses are checked locally and never call the game master.
- If the game master fails or answers with anything other than the three allowed options, the question is not
  counted and the player is asked to retry.
