# Hanabi

Two to five players cooperate to build five fireworks from 1 to 5 while seeing every hand except their own, which they
learn about only through a limited supply of hints ([rules](https://en.wikipedia.org/wiki/Hanabi_%28card_game%29)).

<!-- BEGIN GENERATED: variants -->
**Players:** 2–5

**`-mdp` observation:** game messages and the latest board (no raw player actions)

| Env ID | Parameters |
| --- | --- |
| `Hanabi-v0` | defaults |

Append `-mdp` to any ID for the state-complete variant (e.g. `Hanabi-v0-mdp`).
<!-- END GENERATED: variants -->

## Rules

- The deck has 50 cards in five colors (white, yellow, green, blue, red); each color has three 1s, two each of 2s, 3s
  and 4s, and one 5. Each player holds 5 cards with two or three players and 4 cards with four or five. Everyone sees
  their teammates' cards but never their own.
- The team shares `info_tokens` information tokens (8 by default, also the maximum) and `fuse_tokens` fuse tokens
  (3 by default).
- Player 0 starts and turns pass in order. On your turn you do exactly one of:
  - **Hint:** point at a card in a teammate's hand and name its color or its rank. The hint tells that teammate the
    positions of *all* their cards of that color or rank. It costs one information token, so it needs at least one.
  - **Discard** one of your cards to regain an information token. Discarding is not allowed while all information
    tokens are available.
  - **Play** one of your cards. If it is the next rank of its color's firework (a 1 starts a firework), it is added;
    completing a firework with its 5 returns an information token (up to the maximum). Otherwise the card is
    discarded and the team loses a fuse token.
- After playing or discarding you draw a replacement card while the deck lasts. Hand positions are numbered from 0; a
  new card goes to the end of the hand, and the cards after a played or discarded card move down one position.
- The game ends when:
  - the last fuse token is lost (the team scores 0);
  - all five fireworks are complete (the team scores 25); or
  - the deck has run out and every player, including the one who drew the last card, has taken one more turn (the
    team scores the number of cards on the fireworks).
- Two invalid replies in a row skip that player's turn; nobody is eliminated. If every player skips a turn in a row,
  with no valid action in between, the game ends and the team scores the cards on the fireworks.

## Actions

Reply with exactly one command (case-insensitive). Card positions start at 0.

- `play X` plays your card at position `X`.
- `discard X` discards your card at position `X`.
- `reveal player N card X color C` hints Player `N` about the color of their card `X` (`C` is `white`, `yellow`,
  `green`, `blue` or `red`).
- `reveal player N card X rank R` hints Player `N` about the rank of their card `X` (`R` is 1–5).

Examples: `play 0`, `discard 4`, `reveal player 1 card 3 color green`, `reveal player 2 card 0 rank 1`.

The named card must really have the color or rank you name, and you cannot hint yourself.

## Observations

Each player first receives the rules. Before every turn the acting player sees the fuse and information tokens, the
number of cards left in the deck (with a notice once the final round has begun), how many cards they hold and what
the hints so far have told them about each position (known colors and ranks, and the ones ruled out), the fireworks,
every teammate's cards together with what each teammate knows about them, and the discard pile. Everyone sees every
hint (which positions match), every play and every discard. A player's raw reply is echoed only to themselves.

## Rewards

Every player receives the same reward.

| Outcome | Reward |
| --- | --- |
| All five fireworks complete | `1` |
| Deck exhausted and the final round played | Team score `/ 25` |
| Every player skips a turn in a row for repeated invalid moves | Team score `/ 25` |
| Last fuse token lost | `0` |

## Parameters

- `info_tokens` (default `8`): starting and maximum number of information tokens.
- `fuse_tokens` (default `3`): fuse tokens; the game is lost when the last one is used.

## Notes

- In the physical game players must remember the hints they received; here the board keeps track of them for each
  card position.
