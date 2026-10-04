# Spite and Malice Environment Documentation

## Overview
**Spite and Malice** is a two-player competitive card game that combines elements of solitaire and strategic play. Each player has their own payoff pile that they aim to deplete first to win. Players can play cards to shared center piles in ascending sequence (Ace to Queen), with Kings serving as wild cards. The game involves careful resource management, opportunistic card placement, and strategic blocking to prevent your opponent from emptying their payoff pile. This implementation features a complete deck management system, discard piles, and a hand limit of five cards.

## Action Space

- **Format:** Submit one or more bare commands:
  - **Draw:** `draw` - Draw cards to refill your hand to 5 cards
  - **Play:** `play Card Index` - Play a card to a center pile (e.g. `play A♠ 0`)
  - **Discard:** `discard Card Index` - Discard a card to end your turn (e.g. `discard 3♥ 2`)

- **Examples:**
  - Draw cards at the beginning of a turn: `draw`
  - Play the Ace of Spades to center pile 0: `play A♠ 0`
  - Discard the Three of Hearts to discard pile 2: `discard 3♥ 2`

- **Notes:** Players can include multiple actions in a single turn (except after discarding, which ends the turn). A typical turn consists of first drawing cards, then playing one or more cards, and finally discarding to end the turn.

## Observation Space

**Reset Observations**
On reset, each player receives a prompt containing the game rules and their initial game state. For example:

```plaintext
You are Player 0 in a two-player game of Spite and Malice. Your goal is to be the first to empty your payoff pile.

### Game Overview:
- The objective is to clear your payoff pile by playing cards to the center piles.
- You can play cards from three sources:
  1. Your **hand** (you start each turn with up to 5 cards in hand).
  2. The **top card of your payoff pile**.
  3. The **top card of any of your discard piles**.

### Playing Rules:
- You may play a card to a center pile if it is **one rank higher** than the top card on that pile (center piles start with Ace and go up to Queen; Kings are wild - they can be played on any card but do not change the rank sequence. This means if a King is used after 4, then that King is ranked 5 and the next card must be a 6).
- If you can't play any more cards, you must **discard a card** to one of your discard piles to end your turn.
- If a center pile reaches Queen, it will be cleared automatically.
- The rank order is: A=1, 2=2, ..., 9=9, J=10, Q=11, K as wild.

### Actions:
1. **Draw**: At the start of your turn, enter **draw** to fill your hand up to 5 cards.
2. **Play a Card**: Enter **play A♠ 0**, where `A♠` is the card and `0` is the center-pile index.
3. **Discard**: Enter **discard A♠ 1** to discard from your hand and end your turn. You cannot discard from the payoff pile.

Here is the current game state:
--- Center Piles ---
Pile 0: []
Pile 1: []
Pile 2: []
Pile 3: []

--- Player 0's View ---
Payoff Pile (Top Card): 7♠, Payoff Pile Length: 20
Hand: ['A♥', 'K♦', '3♣', 'Q♠', '5♦']
Discard Piles: [[], [], [], []]
```

**Step Observations**
During gameplay, players receive updates about their actions and the current game state. For example:

```plaintext
[Player 0] draw
[GAME] You drew cards. Your updated view:
--- Center Piles ---
Pile 0: []
Pile 1: []
Pile 2: []
Pile 3: []

--- Player 0's View ---
Payoff Pile (Top Card): 7♠, Payoff Pile Length: 20
Hand: ['A♥', 'K♦', '3♣', 'Q♠', '5♦']
Discard Piles: [[], [], [], []]

[Player 0] play A♥ 0
[GAME] You played A♥ on center pile 0. Your updated view:
--- Center Piles ---
Pile 0: ['A♥']
Pile 1: []
Pile 2: []
Pile 3: []

--- Player 0's View ---
Payoff Pile (Top Card): 7♠, Payoff Pile Length: 20
Hand: ['K♦', '3♣', 'Q♠', '5♦']
Discard Piles: [[], [], [], []]

[Player 0] discard Q♠ 1
[GAME] You have discarded Q♠ to discard pile 1, which also means you have finished their turn. Your updated view:
--- Center Piles ---
Pile 0: ['A♥']
Pile 1: []
Pile 2: []
Pile 3: []

--- Player 0's View ---
Payoff Pile (Top Card): 7♠, Payoff Pile Length: 20
Hand: ['K♦', '3♣', '5♦']
Discard Piles: [[], ['Q♠'], [], []]
```

## Gameplay

- **Players:** 2 players
- **Initial Setup:** Each player starts with a 20-card payoff pile, 5 cards in hand, and 4 empty discard piles
- **Center Piles:** 4 shared center piles where cards are played in ascending sequence (Ace to Queen)
- **Turns:** Players take turns drawing, playing cards, and discarding
- **Objective:** Be the first to empty your payoff pile

## Key Rules

1. **Card Sources:**
   - Players can play cards from their hand, the top card of their payoff pile, or the top card of any of their discard piles
   - Cards can only be discarded from the hand, not from the payoff pile or discard piles

2. **Card Sequence:**
   - Center piles must be built in ascending sequence: A, 2, 3, 4, 5, 6, 7, 8, 9, J, Q (where J=10, Q=11)
   - Kings are wild cards and can be played on any card but don't change the required sequence
   - Empty center piles can only be started with an Ace (or King representing an Ace)

3. **Pile Management:**
   - When a center pile reaches a Queen (or completes a sequence from A to Q), it is cleared automatically
   - Players must discard to one of their four discard piles at the end of their turn if they cannot play any more cards
   - Players draw cards at the start of their turn to refill their hand to 5 cards

4. **Turn Structure:**
   - **Draw Phase:** Draw cards to refill hand to 5 cards
   - **Play Phase:** Play as many valid cards as possible to center piles
   - **Discard Phase:** Discard one card from hand to end the turn

5. **Winning Conditions:**
   - **Win:** The first player to empty their payoff pile
   - **Loss:** Failing to empty your payoff pile before your opponent

6. **Game Termination:**
   - The game concludes when one player completely empties their payoff pile

## Rewards

| Outcome     | Reward for Winner | Reward for Loser |
|-------------|:-----------------:|:----------------:|
| **Win**     | `+1`              | `-1`             |
| **Invalid** | `-1`              | `0`              |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg