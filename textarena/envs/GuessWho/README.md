# Guess Who

Identify a secret character from a lineup of 24 by asking an LLM game master yes-or-no questions, then name them
with a single guess before the question budget runs out ([rules](https://en.wikipedia.org/wiki/Guess_Who%3F)). It
tests information-efficient questioning and deduction over a structured set of candidates.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `GuessWho-v1` | `max_turns=20` |

Append `-mdp` to any ID for the state-complete variant (e.g. `GuessWho-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("GuessWho-v1", max_turns=...)`.
<!-- END GENERATED: variants -->

## Rules

- At reset, a target character is drawn at random from the 24 characters of the classic lineup (Alex, Alfred, Anita,
  …, Tom). Each character has 17 traits, such as gender, age range, hair color and style, eye color, accessories,
  hat, facial hair, and glasses style.
- Each turn, you either ask one free-form question about the target or guess a name.
- An LLM game master that knows the target's traits answers every question with `Yes`, `No`, or `I don't know`.
  Each answered question uses one turn.
- You may ask up to `max_turns - 1` questions. The answer to the last one tells you that you have run out of
  questions; after that, only a guess is accepted, and asking another question is an invalid move.
- You get exactly one guess, and it ends the game: naming the target wins, and naming any other character from the
  lineup loses. A name that is not in the lineup is an invalid move and can be corrected.

## Actions

- Ask a question as plain text, for example `Does the character wear glasses?`
- Guess with `guess <name>` (or `guess: <name>`), for example `guess Anita`. The keyword and the name are
  case-insensitive, and accents, punctuation, quotes, and spacing in the name are ignored.

Any message containing a question mark is a question, even if it starts with `guess` (`Guess what, is it Alex?`).
Otherwise, a message that starts with the word `guess` is a guess, and `guess` without a name is invalid. Sender tags
such as `[GAME]` and line breaks are removed from questions before they reach the game master; a question without any
letter or digit and messages longer than 4,000 characters are invalid.

## Observations

The player first receives the rules, including the question budget and the single-guess rule, with an example guess
that uses the first name in the lineup (`guess Alex` for the bundled characters), and a description of every
character's traits. After each question, the game master's answer arrives as a separate message. Before every move,
the player also sees a status board with the number of questions asked out of `max_turns - 1` and the full
question-and-answer history. The target's name appears on the board only after the game ends.

## Rewards

| Outcome | Reward |
| --- | --- |
| Correct guess | `1` |
| Wrong guess (another character from the lineup) | `0` |
| Second consecutive invalid move (such as a question after the budget is used up, or two names outside the lineup) | `0` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `max_turns` (default `40`): The total number of turns. The player may ask `max_turns - 1` questions, and the final turn is reserved for the guess. Accepts an integer of at least 2.
- `gamemaster` (default `None`): Answers the player's questions. With None, OpenRouter `qwen/qwen3.8-27b` answers; inject one to play offline or with a different model. Accepts a callable that takes a prompt string and returns `Yes`, `No`, or `I don't know` or None.
- `characters_path` (default `None`): A JSON file with an alternative character list in the schema of the bundled `characters.json`, which None selects. Names must stay distinct once case, accents, punctuation, and spacing are ignored.
<!-- END GENERATED: parameters -->

## Notes

- The default game master is created on the first question and needs the `openai` package and `OPENROUTER_API_KEY`.
  Guessing never calls the game master.
- If the game master fails or answers with anything other than the three allowed options, the question is not
  counted and the player is asked to retry.
- The game master receives the target's full trait record and the question history, so its answers are only as
  reliable as the underlying model.
