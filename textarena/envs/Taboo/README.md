# Taboo

Two teams take turns in which a Clue Giver describes a secret word without saying it or any of its taboo words while
teammates try to guess it; the team with more correct guesses wins
([rules](https://en.wikipedia.org/wiki/Taboo_%28game%29)). It tests constrained description, word association, and
team coordination.

<!-- BEGIN GENERATED: variants -->
**Players:** 4+

**`-mdp` observation:** the prompt, the full transcript including every player action, and the latest board

| Env ID | Parameters |
| --- | --- |
| `Taboo-v1` | `max_rounds=4`, `max_attempts_per_player=6`, `categories=['things']` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Taboo-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Taboo-v1", max_rounds=...)`.
<!-- END GENERATED: variants -->

## Rules

- The players (an even number, at least four) form two equal teams: Team 0 is the first half of the player ids and
  Team 1 the second half. The first player of each team (Player 0 and Player N/2) is its Clue Giver; the rest are
  Guessers.
- Each team works through its own shuffled sequence of target words from the selected categories. Every target comes
  with a list of taboo words.
- A round is one turn for Team 0 followed by one turn for Team 1. During a team turn, the team's members act in
  rotation (Clue Giver, each Guesser, Clue Giver again, ...) for `max_attempts_per_player` × team size actions in total.
- A correct guess scores 1 point; the team moves on to its next word, and the Clue Giver acts next. A word that is not
  guessed carries over to the team's next turn.
- The game ends after `max_rounds` rounds, or earlier if a team runs out of words, and the team with more points wins.

## Actions

- **Clue Giver:** any non-empty clue, e.g. `You pour hot water through it to make your morning drink.` A clue that
  contains the target, any significant word of the target on its own (`duck` or `Amazon` for `Amazon duck`, `Kabul`
  for `Kabul (Afghanistan)`; short function words such as `the`, `of`, or `you` and words inside parentheses stay
  allowed), or one of its taboo words is invalid. Matching works on whole words and ignores case, accents, invisible
  characters, common look-alike letters (such as Cyrillic `а`), and punctuation or underscores inside or between words
  (`ca-mel`, `U.S.A.`, `the_camel`, `ice-cream`, `icecream`); words spelled out letter by letter (`c a m e l`) also
  match. Sender tags such as `[GAME]` are removed from the clue before it is checked and relayed.
- **Guesser:** the guess alone on a single line, e.g. `coffee filter`. The guess must name the whole target, but case,
  accents, punctuation, spacing, and a leading `the`, `a`, or `an` are ignored, a qualifier in parentheses may be left
  out (`Kabul` for `Kabul (Afghanistan)`, `Budweiser` for `Budweiser (beer)`), and an inverted official name may be
  shortened (`Palestine` for `Palestine, State of`). Wrong guesses are valid moves; empty or multi-line replies and
  replies without any letter or digit are invalid.

## Observations

Each player first receives their role, their team, the clue or guess rules for that role, the scoring, the number of
rounds, and how many actions they get per team turn. A Clue Giver privately receives the target word and its taboo
words at the start of each of their team's turns and after every correct guess; Guessers never see them. Clues and
guesses are shown only to the members of the acting team, with sender tags such as `[GAME]` removed. Everyone is told
when a team scores (with the current score) and when play passes to the other team.

## Rewards

| Outcome | Reward |
| --- | --- |
| More points at the end | Members of that team `+1`, other team `-1` |
| Equal points | Everyone `0` |
| Clue Giver's second consecutive invalid clue | The team skips its current word and its turn ends at once; no direct penalty |
| Guesser's second consecutive invalid guess | That action is forfeited and play passes to the next teammate; no direct penalty |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `categories` (default `['things']`): One category or a list whose words are combined, chosen from `animals`, `cars`, `city/country`, `food`, `literature`, `people`, `things`, and `tv` (84 to 495 targets each). Accepts a category name or a non-empty list of category names.
- `max_rounds` (default `4`): The number of rounds, i.e. turns per team. Accepts an integer of at least 1.
- `max_attempts_per_player` (default `6`): The actions each player takes during each of their team's turns. Accepts an integer of at least 1.
- `data_path` (default `None`): An optional JSON file of the form `{"category": {"target": ["taboo", ...]}}` that replaces the bundled `words.json`. Every target must contain at least one letter or digit.
<!-- END GENERATED: parameters -->
