# Word Chains

Two players take turns naming English words that start with the last letter of the previous word and are exactly one
letter longer; the first player who cannot continue loses. It tests vocabulary breadth under a constraint that
tightens every turn.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `WordChains-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `WordChains-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a starting word of one to five letters is drawn from Ogden's Basic English list. It is always one that has
  at least one valid successor in the bundled dictionaries.
- Players alternate, starting with Player 0. Each word must:
  - start with the last letter of the previous word,
  - be exactly one letter longer than the previous word,
  - be a valid English word (UK and US spellings are both accepted; proper nouns are not), and
  - not have been used earlier in the game, including the starting word.
- An invalid word is rejected and the same player tries again. A player who makes two invalid submissions in a row
  loses, which is how a player who cannot find a word is eliminated.
- There is no turn limit and no draw; the words simply get longer until someone fails.

## Actions

Reply with a single word made of letters only (case-insensitive) and nothing else.

Example: if the previous word is `map`, then `pear` is valid (starts with `p`, four letters long).

## Observations

Each player first receives the rules and the starting word. Before every move, the acting player sees the required
first letter and the required length of the next word. Both players see every submission, and each accepted word is
announced as `Player 0 played: 'pear'`. There is no hidden information.

## Rewards

| Outcome | Reward |
| --- | --- |
| Second consecutive invalid submission | Offender `-1`, opponent `+1` |

## Notes

- Words are checked against the shared English dictionary in `textarena/utils/word_lists.py`: the bundled UK and US
  Hunspell word lists, plus the NLTK `words` corpus (`nltk.download('words')`) when it is installed.
- The starting words come from the bundled copy of Basic English (850 words, the same list as NLTK's `en-basic`) in
  `textarena/utils/data/`, and the successor check uses only the bundled UK and US lists. A seed therefore picks the
  same starting word on every machine, with or without NLTK data.
