# GermanWhist Environment Documentation

## Overview

**GermanWhist** simulates the classic 2-player trick-taking card game *German Whist*. Players compete over 26 tricks in two phases. During the first 13 tricks, players draw cards after each trick—one face-up for the winner and one face-down for the loser. The final 13 tricks are played without draws, using the hands formed during the first half.

The player who wins the majority of tricks (14 or more) wins the game.


## Gameplay

- **Players:** 2
- **Deck:** Standard 52-card deck
- **Trump Suit:** Chosen at the start by revealing the top card of the deck
- **Phases:**
  - **Learning Phase (First 13 tricks):** Draws occur after each trick
  - **Endgame Phase (Last 13 tricks):** No more draws; tricks directly contribute to win


## Trick Rules

- The leader plays a card, then the follower responds
- You must **follow suit if you can**
- If both players follow suit, the higher-ranked card wins
- If one player cannot follow suit, they may play any card:
  - A **trump card beats any non-trump**
  - Among trump cards, highest trump wins


## Card Ranks (Power)

| Card | Power |
|------|--------|
| A    | 13     |
| K    | 12     |
| Q    | 11     |
| J    | 10     |
| 10   | 9      |
| ...  | ...    |
| 2    | 1      |

- Trump suit is fixed for the whole game

## Actions

Each turn, players must play a card using the following format:

```text
play X
```
where `X` is the 1-based index of the card in the player's hand.

Example:
```bash
play 3
```

## Turn Prompt Example
```bash
[GAME] You are playing German Whist - Player 0.
LEARNING PHASE: Win tricks to get the visible next card. You can see what you're competing for!
Goal: Win the majority of tricks (14+ out of 26 total).
Card Power: A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2
Trump cards beat non-trump cards. You must follow suit if possible.

Action: 'play X' where X is the position (1-13) of the card in your hand

[GAME] German Whist game started!
Trump suit: ♠ (Trump card: 4♠)

LEARNING PHASE: Win tricks to get the face-up card from the deck. The winner sees the next card, the loser gets it blind.
[GAME] Your hand:
  ♠ (TRUMP):
    12. Q♠
    10. 6♠
    4. 3♠
  ♥:
    5. K♥
  ♦:
    8. 9♦
    2. 5♦
  ♣:
    6. K♣
    3. J♣
    13. 10♣
    11. 7♣
    9. 6♣
    1. 4♣
    7. 3♣

No cards played yet this trick.

Next card for trick winner: 4♠ (TRUMP)

Tricks won - Player 0: 0 | Player 1: 0
Phase: LEARNING (26 cards left in deck)

Play a card using `play X`
```


## End Condition

- Game ends after 26 tricks
- The player with 14 or more tricks wins
- A tie is possible at 13–13

## Available Environments

| Env-id               | Mode      |
|----------------------|-----------|
| `GermanWhist-v0`     | 2 players |

## Contact

For issues or feedback related to this environment, contact:

**Email:** `chengxy@i2r.a-star.edu.sg`
