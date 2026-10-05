# Codenames

Two teams of two race to uncover their own words on a 25-word board, with each team's Spymaster giving one-word clues
that their Operative turns into guesses ([rules](https://en.wikipedia.org/wiki/Codenames_%28board_game%29)). It tests
word association, modelling a teammate's reasoning, and risk management.

<!-- BEGIN GENERATED: variants -->
**Players:** 4

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Codenames-v1` | `hardcore=False` |
| `Codenames-v1-hardcore` | `hardcore=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Codenames-v1-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Codenames-v1", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- Roles are fixed: Player 0 is the Red Spymaster, Player 1 the Red Operative, Player 2 the Blue Spymaster, and Player 3
  the Blue Operative. Red moves first.
- The board holds 25 words: 9 Red, 8 Blue, 7 neutral, and 1 Assassin. Only the Spymasters know which is which.
- Turns cycle Red Spymaster, Red Operative, Blue Spymaster, Blue Operative.
- A Spymaster gives a clue of one word and a number N from 1 to 25. The clue must not be an unrevealed board word, a
  form of one or part of a compound with one. This is checked as: the clue equals an unrevealed board word, or one of
  the two starts or ends with the other (`arms` or `firearm` with `arm` on the board, `star` with `starfish`). A board
  word only in the middle of the clue is allowed (`charming` with `arm`), and revealed words no longer count. A
  forbidden clue is not given: everyone is told why, and the team's turn ends at once without guesses.
- The Operative then guesses one word per move, up to N + 1 guesses. They must make at least one guess each turn and
  may pass after that. Guessing one of their own words lets them continue; a neutral or opposing word is revealed and
  ends the turn; the Assassin loses the game.
- A team wins as soon as all of its words are revealed, even if the opposing Operative revealed the last one.
- After `max_turns` moves in total (every clue, forbidden clue, guess and pass counts), the team with fewer of its words
  still unrevealed wins (Red starts with 9, Blue with 8), and equal counts are a draw.

The official game also lets the opposing Spymaster cover one of their own words after a forbidden clue; this version
only ends the turn.

## Actions

- **Spymaster:** a single alphabetic word followed by a number, e.g. `ocean 3`.
- **Operative:** one word from the board, e.g. `whale`, or `pass` to end the team's guessing turn after at least one
  guess.

Replies are case-insensitive. A malformed clue, a clue number outside 1–25, a guess that is not on the board, a guess
of an already revealed word, and a pass before the first guess of a turn are invalid.

## Observations

Each player first receives the rules (including the clue rule and the move limit) and their role. Before every move,
the acting player sees the board: Spymasters see every word with its label (`R`, `B`, `N`, or `A`) and which words are
revealed, while Operatives see only the words plus the labels of revealed words. While a team is guessing, the board
also shows the active clue and how many guesses are left, and every board shows the number of moves played out of
`max_turns`. Raw replies are echoed only to their author; instead, the game announces every clue, every guess result
(correct, or wrong together with the word's type), every pass and every forbidden clue to all players.

## Rewards

| Outcome | Reward |
| --- | --- |
| A team's words are all revealed | That team `+1`, other team `-1` |
| An Operative reveals the Assassin | Guessing team `-1`, other team `+1` |
| Turn limit, one team has fewer of its words unrevealed | That team `+1`, other team `-1` |
| Turn limit, equal number of words unrevealed | Everyone `0` |
| Second consecutive invalid move | Offender's team `-1`, other team `+1` |

## Parameters

<!-- BEGIN GENERATED: parameters -->
- `hardcore` (default `False`): Draw board words from the list built from NLTK's full English word list (29,345 words) instead of the one built from its Basic English list (423 words), which produces rarer words.
- `max_turns` (default `80`): The total number of moves (clues and guesses) before the turn-limit result applies. Accepts an integer of at least 1.
<!-- END GENERATED: parameters -->

## Notes

- Board words are nouns of three to seven letters, originally selected with NLTK's `words` corpus and part-of-speech
  tagger. Both lists ship with the environment in `words.json`, so boards are identical on every machine and nothing
  is downloaded.
- Slurs and sexual or vulgar terms (the shared list in `textarena/utils/data/blocked_words.txt`) are never drawn as
  board words.
