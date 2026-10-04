# Codenames

Two teams of two race to uncover their own words on a 25-word board, with each team's Spymaster giving one-word clues
that their Operative turns into guesses ([rules](https://en.wikipedia.org/wiki/Codenames_%28board_game%29)). It tests
word association, modelling a teammate's reasoning, and risk management.

<!-- BEGIN GENERATED: variants -->
**Players:** 4

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `Codenames-v0` | `hardcore=False` |
| `Codenames-v0-hardcore` | `hardcore=True` |

Append `-mdp` to any ID for the state-complete variant (e.g. `Codenames-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("Codenames-v0", hardcore=...)`.
<!-- END GENERATED: variants -->

## Rules

- Roles are fixed: Player 0 is the Red Spymaster, Player 1 the Red Operative, Player 2 the Blue Spymaster, and Player 3
  the Blue Operative. Red moves first.
- The board holds 25 words: 9 Red, 8 Blue, 7 neutral, and 1 Assassin. Only the Spymasters know which is which.
- Turns cycle Red Spymaster, Red Operative, Blue Spymaster, Blue Operative.
- A Spymaster gives a clue of one word and a number N from 1 to 25. A clue word that contains, or is contained in, any
  board word (for example `sea` when `seal` is on the board) immediately loses the game for that team.
- The Operative then guesses one word per move, up to N + 1 guesses, and may pass at any time. Guessing one of their own
  words lets them continue; a neutral or opposing word is revealed and ends the turn; the Assassin loses the game.
- A team wins as soon as all of its words are revealed, even if the opposing Operative revealed the last one.
- After `max_turns` moves in total (every clue and every guess counts), the team with more of its words revealed wins,
  and equal counts are a draw.

## Actions

- **Spymaster:** a single alphabetic word followed by a number, e.g. `ocean 3`.
- **Operative:** one word from the board, e.g. `whale`, or `pass` to end the team's guessing turn.

Replies are case-insensitive. A malformed clue, a clue number outside 1–25, a guess that is not on the board, and a
guess of an already revealed word are invalid.

## Observations

Each player first receives the rules (including the clue rule and the move limit) and their role. Before every move,
the acting player sees the board: Spymasters see every word with its label (`R`, `B`, `N`, or `A`) and which words are
revealed, while Operatives see only the words plus the labels of revealed words. While a team is guessing, the board
also shows the active clue and how many guesses are left, and every board shows the number of moves played out of
`max_turns`. Raw replies are echoed only to their author; instead, the game announces every clue, every guess result
(correct, or wrong together with the word's type), and every pass to all players.

## Rewards

| Outcome | Reward |
| --- | --- |
| A team's words are all revealed | That team `+1`, other team `-1` |
| An Operative reveals the Assassin | Guessing team `-1`, other team `+1` |
| A clue overlaps a board word | Clue giver's team `-1`, other team `+1` |
| Turn limit, one team has more of its words revealed | That team `+1`, other team `-1` |
| Turn limit, equal number of words revealed | Everyone `0` |
| Second consecutive invalid move | Offender's team `-1`, other team `+1` |

## Parameters

- `hardcore` (default `False`): draws board words from the list built from NLTK's full English word list (29,406
  words) instead of the one built from its Basic English list (423 words), which produces rarer words.
- `max_turns` (default `80`): total number of moves (clues and guesses) before the turn-limit result applies.

## Notes

- Board words are nouns shorter than eight letters, originally selected with NLTK's `words` corpus and part-of-speech
  tagger. Both lists ship with the environment in `words.json`, so boards are identical on every machine and nothing
  is downloaded.
- Slurs and sexual or vulgar terms (the shared list in `textarena/utils/data/blocked_words.txt`) are never drawn as
  board words.
