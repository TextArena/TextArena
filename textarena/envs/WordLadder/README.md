# Word Ladder

Transform a start word into a target word by changing one letter at a time, where every step must be an English word
of the same length ([rules](https://en.wikipedia.org/wiki/Word_ladder)). It tests vocabulary search and planning over
a graph of word neighbors.

<!-- BEGIN GENERATED: variants -->
**Players:** 1

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `WordLadder-v0` | `min_distance=5`, `max_distance=7`, `max_turns=100` |
| `WordLadder-v0-hard` | `min_distance=13`, `max_distance=15`, `max_turns=100` |
| `WordLadder-v0-medium` | `min_distance=8`, `max_distance=12`, `max_turns=100` |

Append `-mdp` to any ID for the state-complete variant (e.g. `WordLadder-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- Puzzles are built from the 828 words of Ogden's Basic English that have 3 to 11 letters (see Notes).
- At reset, a word length is picked at random, then a start and a target word of that length whose shortest ladder
  through Basic English words alone is between `min_distance` and `max_distance` single-letter changes. Since `max_turns`
  is at least `max_distance`, every puzzle can be solved within the turn limit.
- Each turn, you submit the next word. It must have the same length as the target, differ from your current word in
  exactly one position, and be in the game's dictionary: any word in the bundled British and American English word
  lists, including plurals and other inflected forms. Proper nouns, abbreviations, and words containing anything but
  letters are rejected. Revisiting an earlier word is allowed.
- Because every dictionary word is accepted, not just Basic English ones, a ladder shorter than `min_distance` often exists.
- You win by reaching the target word.
- Each accepted word uses one turn. After `max_turns` accepted words without reaching the target, the game ends.
  A rejected word does not use a turn, but two rejected submissions in a row end the game.

## Actions

Reply with a single word made of letters only (case-insensitive) and nothing else.

Example: from `fear` to `meal`, the ladder `hear`, `heal`, `meal` takes three moves, submitted one word per turn.
Using Basic English words only, the shortest ladder takes six: `dear`, `dead`, `head`, `heat`, `meat`, `meal`.

## Observations

The player first receives the start word, the target word, the required word length, which words count, and the
number of moves allowed. After each accepted word, the player sees the ladder so far and the target, for example
`Word Ladder History: fear -> hear.  Target Word: meal`. After a rejected word, the player is told why it was
rejected (wrong length, not a recognized word, or not exactly one letter different).

## Rewards

Unless you reach the target, you score the share of the start word's ladder distance you closed: `(D − d) / D`, where
`D` is the fewest moves from the start word to the target and `d` the fewest from your current word, both through the
game's dictionary (the same words accepted as moves). The start word scores `0`, and so does any word that is no
closer to the target; letters that already match the target count only if they shorten the ladder.

| Outcome | Reward |
| --- | --- |
| Target word reached | `+1` |
| `max_turns` accepted words without reaching the target | Share of the ladder distance closed (`0` to below `1`) |
| Second consecutive invalid move | Share of the ladder distance closed |

## Parameters

- `min_distance` (default `5`) and `max_distance` (default `7`): the range for the length, in single-letter changes,
  of the shortest ladder between the start and the target that uses only Basic English words. Ladders through other
  dictionary words can be shorter.
- `max_turns` (default `100`): the number of accepted words allowed. It must be at least `max_distance`, so every
  puzzle is solvable within the limit.

## Notes

- The Basic English list (850 words) is bundled in `textarena/utils/data/`, so a seed produces the same puzzle on
  every machine.
- Moves are checked against `get_english_words()` in `textarena/utils/word_lists.py`: every word of the bundled UK and
  US Hunspell dictionaries with its affix rules applied (about 101,000 words). The same words are accepted on every
  machine, so the ladder distances behind partial credit are the same everywhere too.
- Ladders through the whole dictionary are much shorter than through Basic English: in the registered variants the
  start word is usually only 2 to 6 moves from the target, so each move along a shortest ladder is worth a large share.
