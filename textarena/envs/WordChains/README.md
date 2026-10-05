# Word Chains

Two players take turns naming English words that start with the last letter of the previous word and are exactly one
letter longer; the first player who cannot continue loses. It tests vocabulary breadth under a constraint that
tightens every turn.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `WordChains-v1` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `WordChains-v1-mdp`).
<!-- END GENERATED: variants -->

## Rules

- At reset, a starting word of one to five letters is drawn from Ogden's Basic English list. It is always one that has
  at least one valid successor in the game's dictionary.
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

- Words are checked against the English word list bundled in `textarena/utils/word_lists.py`: every word of the UK
  and US Hunspell dictionaries with its regular inflections (plurals, past tenses, and so on).
- The starting words come from the bundled copy of Basic English (850 words) in `textarena/utils/data/`, and the
  successor check uses the same word list as move validation, so a seed picks the same starting word on every machine.
