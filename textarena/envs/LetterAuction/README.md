# Letter Auction

Two players bid coins on the 26 letters of the alphabet, one letter at a time, and then each spells an English word
from the letters they won; the word whose letters cost the most wins. It tests resource allocation, valuation, and
planning toward an uncertain goal.

<!-- BEGIN GENERATED: variants -->
**Players:** 2

**`-mdp` observation:** the prompt, every game message and the latest board (raw player actions are left out)

| Env ID | Parameters |
| --- | --- |
| `LetterAuction-v0` | `starting_coins=100` |
| `LetterAuction-v0-hard` | `starting_coins=25` |

Append `-mdp` to any ID for the state-complete variant (e.g. `LetterAuction-v0-mdp`). Parameters can be overridden in `ta.make`, e.g. `ta.make("LetterAuction-v0", starting_coins=...)`.
<!-- END GENERATED: variants -->

## Rules

- Both players start with `starting_coins` coins. The letters A–Z are shuffled and auctioned one at a time; only the
  current letter is known.
- Player 0 opens the first letter. The opener either bids at least 1 coin or passes. Players then alternate, and every
  new bid must be higher than the current one.
- Passing after the opponent has bid gives them the letter at their bid. If the opener passes, the other player can take
  the letter with any bid or pass as well, in which case nobody gets it.
- The winner of a letter pays their bid. The player who did not get the letter opens the next one (after a double pass,
  the second player to pass opens).
- After all 26 letters, each player in turn submits one English word spelled only with letters they won, or passes to
  submit no word. Every letter is auctioned once, so a word can use each letter at most once.
- A word's value is the total of the bids paid for its letters, and the higher value wins. Submitting no word is worth
  `0`, so it loses to any word (every won letter cost at least 1 coin). Leftover coins are worth nothing.
- If `max_turns` is set and that many turns pass before both words are in, the game ends as a draw.

## Actions

During the auction, reply with exactly one command:

- `bid <amount>` bids a positive whole number of coins that you can afford, e.g. `bid 10`.
- `pass` declines to bid on the current letter.

After the auction, reply with your word alone, e.g. `dog`, or with `pass` to submit no word. Commands are
case-insensitive. Bids above your coins, bids that do not exceed the current bid, zero bids, extra text, words not in
the dictionary, and words that need letters you did not win are all invalid.

## Observations

Each player first receives the rules, their starting coins, the first letter, and the opening bid. Raw replies are
echoed only to their author; instead, the game announces every bid and pass to both players, who won each letter and
for how much, and whose turn it is next, including the minimum bid. When the auction ends, a message asks for the
words (or `pass`), and each submitted word or pass is announced with its value. There is no board, so players have to
keep track of their coins and letters from these messages.

## Rewards

| Outcome | Reward |
| --- | --- |
| Higher word value (no word counts as `0`) | Winner `+1`, loser `-1` |
| Equal word values, including both players passing | Both `0` |
| `max_turns` reached before both words are submitted | Both `0` |
| Second consecutive invalid move (including two invalid words) | Offender `-1`, opponent `+1` |

## Parameters

- `starting_coins` (default `100`): coins each player starts with.
- `max_turns` (default `None`): optional cap on the total number of turns (bids, passes, and word submissions; invalid
  attempts do not count). `None` means no cap; the game always ends because bids must rise and coins are limited. A cap
  must be at least `54`, the length of the shortest complete game (two turns per letter plus two word submissions).

## Notes

- Words are checked against the English word list bundled in `textarena/utils/word_lists.py`: every word of the UK
  and US Hunspell dictionaries with its regular inflections (plurals, past tenses, and so on), the same on every
  machine. Proper nouns are rejected, and of the single letters only `a` and `i` count as words.
- `pass` is reserved for submitting no word; it can never be spelled anyway, since it needs two S tiles.
