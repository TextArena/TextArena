# Hanabi Environment Documentation

## Overview
**Hanabi** is cooperative card game that is played with two to five players. The players aim to build a simulated firework show by attempting to play colored cards in a specific order. But there's a catch: the players can only see other player's cards, and not their own. Because the total information, and the nature thereof, is limited, the players need to decide how to communicate strategically to maximize their scores. 

## Action Space
- **Format:** The game is turn-based, where there is a fixed rotation between players. 
  - Depending on the number of players, each player has 4-5 cards in their hand. 
  - The players start with 8 information and 4 fuse tokens. 
    - Information tokens are used to share information. 
    - Fuse tokens act as a "life", and are consumed when someone plays a card unsuccessfully. 
  - The Hanabi deck contains cards in 5 suits, (white, yellow, green, blue, and red): three 1s, two each of 2s, 3s, and 4s, and one 5.
- **Action types:**
  - **Play a card**: Players can play a card, taking it from their hand and attempting to add it to the cards that have already been played. The play is successful if it is a 1 of a suit that has not been played, or a number that is next in line to a suit that has already been played. If played successfully, the card is added to the sequence of cards that have already been played. If a card is played unsuccessfully, a fuse token is consumed and the misplayed card is discarded. Regardless of the outcome of the play, the player draws a new card (if there are any left).   
    - Example: `Play x` plays the card at index `x` in the player's hand.
  - **Give information**: Players can give information about another player's cards by naming a suit or rank that is present. A valid hint identifies every card in that hand matching the named property. Giving information consumes one information token and is limited to a specific format. 
    - Example: `Reveal player 1 card 3 color green` indicates that the card at index 3 from player 1 is green.
    - Example: `Reveal player 4 card 0 rank 4` indicates that the card at index 0 from player 4 has rank 4.
  - **Discard a card**: Players can discard a card, removing it from their hand and putting it on the discard pile. A discarded card is removed from the game, and can no longer be played. Discarding a card replenishes 1 information token and is illegal when all information tokens are already available. Players draw a new card to replace the card they've just discarded. 
    - Example: `Discard 0` discards the card at index 0.

## Observation Space
**Reset Observations**

On reset, each player receives instructions about the game structure:

```plaintext
Current observations: 
[GAME] You are Player 0 in an 2-player Hanabi game. Hanabi is a cooperative card game where players work together to create a series of fireworks by playing cards in ascending numerical order starting from 1. Each player holds their cards facing outward so that all players can see everyone else's cards but not their own.

Objective:
The objective is to play cards in sequence (1 through 5) for each color without making mistakes. There are 5 different colors and each color has cards numbered 1 to 5.

Key Rules:
On your turn, you have three types of possible actions:
1. Give a Hint (Reveal): Provide a hint to another player about their cards, specifying either a color or a number present in their hand. Hints must be accurate and can only reveal positions of cards matching the hint.
2. Discard a Card: Discard one of your own cards to potentially gain an Info token.
3. Play a Card: Attempt to play a card from your hand. If played correctly in sequence, it adds to the fireworks; if not, it reduces one fuse token.

Tokens:
Fuse Tokens: Deducted when a wrong card is played.
Info Tokens: Used to give clues.

Illegal Moves:
Playing a card that cannot be placed properly costs a fuse token. If fuse tokens reach zero, the game ends in failure.

Game End:
The game ends when all fireworks are completed (perfect score of 25), or when the deck is exhausted and each player has taken one final turn, or when the players run out of fuse tokens.

State Representation:
The game state is represented with the following details:
Fuse tokens: Number of remaining fuse tokens.
Info tokens: Number of available information tokens.
Fireworks: Current progress on each firework color.
Discards: Cards that have been discarded.

Your Role:
You are one of the players, cooperating with others to maximize the total score of the fireworks (the number of cards correctly played in sequence).
Although you cannot see your own cards, you can see the cards in the hands of your teammates.
Use hints, discards, and plays strategically to guide the team towards successful sequences.
When it's your turn, your output should be in one of the following formats between quotes:

'Reveal player N card X color C', to give a hint about color C of card X to the player at index N.
'Reveal player N card X rank R', to give hint about rank R of card X to the player at index N.
'Play X', to play the card in position X from your hand.
'Discard X', to discard the card in position X from your hand.

Remember, communication is limited to hints about colors or numbers only, and sharing illegal or extraneous information is not allowed. Work together, follow the rules, and aim for the highest cooperative score possible!
```

**Turn start**

At the start of their turn, the players receive the most recent information about the game's state (the example comes from a 2-player game, from the perspective of `Player 0`):
```plaintext
[GAME] You are player 0. 

Current game state:
Fuse tokens: there are 4 fuse tokens remaining.
Info tokens: there are 8 info tokens remaining.

Fireworks: The current progress on each firework color is:
        white: 0.
        yellow: 0.
        green: 0.
        blue: 0.
        red: 0.

Your teammates have the following cards in their hand:
- Player 1 has cards:
        card 0: a green card with rank 2
        card 1: a green card with rank 2
        card 2: a red card with rank 2
        card 3: a green card with rank 5
        card 4: a red card with rank 1

Discards: The following cards have been discarded:
```


**Actions**

Players receive messages relating to the actions of the other players. For example, if `Player 0` successfully plays the first card from their hand (`play 0`), the other players receive the following message:

```plaintext
[Player 0] Player 0 attempts to play a blue card with rank 1. The card was played successfully.
```

Lastly, the `Game Board` is updated, indicating the game's process. 

```plaintext
                                                                   ┌────────────────────────── Game Board ──────────────────────────┐                                                                    
                                                                   │ ╭── Hanabi ──────────────────────────────────────────────────╮ │                                                                    
                                                                   │ │   Deck size: 39   │   Info tokens: 8   │  Fuse tokens: 4   │ │                                                                    
                                                                   │ ╰────────────────────────────────────────────────────────────╯ │                                                                    
                                                                   │ ┌─ 🎆 Fireworks ─────────────────────────────────────────────┐ │                                                                    
                                                                   │ │ white     : 0  │ D>                                        │ │                                                                    
                                                                   │ │ yellow    : 0  │ D>                                        │ │                                                                    
                                                                   │ │ green     : 0  │ D>                                        │ │                                                                    
                                                                   │ │ blue      : 1  │ D=>                                       │ │                                                                    
                                                                   │ │ red       : 0  │ D>                                        │ │                                                                    
                                                                   │ └────────────────────────────────────────────────────────────┘ │                                                                    
                                                                   │ ┌─ 🚮 Discard pile ──────────────────────────────────────────┐ │                                                                    
                                                                   │ └────────────────────────────────────────────────────────────┘ │
                                                                   └────────────────────────────────────────────────────────────────┘                                                                    
╭────────────────────────────────────────────────────────────────────────────────────────────── Player 0 ───────────────────────────────────────────────────────────────────────────────────────────────╮
│ Player 0 attempts to play a blue card with rank 1. The card was played successfully.                                                                                                                  │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

If the action fails, the board is updated accordingly:

```plaintext
                                                                   ┌────────────────────────── Game Board ──────────────────────────┐                                                                    
                                                                   │ ╭── Hanabi ──────────────────────────────────────────────────╮ │                                                                    
                                                                   │ │   Deck size: 38   │   Info tokens: 8   │  Fuse tokens: 3   │ │                                                                    
                                                                   │ ╰────────────────────────────────────────────────────────────╯ │                                                                    
                                                                   │ ┌─ 🎆 Fireworks ─────────────────────────────────────────────┐ │                                                                    
                                                                   │ │ white     : 0  │ D>                                        │ │                                                                    
                                                                   │ │ yellow    : 0  │ D>                                        │ │                                                                    
                                                                   │ │ green     : 0  │ D>                                        │ │                                                                    
                                                                   │ │ blue      : 1  │ D=>                                       │ │                                                                    
                                                                   │ │ red       : 0  │ D>                                        │ │                                                                    
                                                                   │ └────────────────────────────────────────────────────────────┘ │                                                                    
                                                                   │ ┌─ 🚮 Discard pile ──────────────────────────────────────────┐ │                                                                    
                                                                   │ │ a green card with rank 2                                   │ │                                                                    
                                                                   │ └────────────────────────────────────────────────────────────┘ │                                                                    
                                                                   └────────────────────────────────────────────────────────────────┘                                                                    
                                                                                                                                                                                                         
╭────────────────────────────────────────────────────────────────────────────────────────────── Player 1 ───────────────────────────────────────────────────────────────────────────────────────────────╮
│ Player 1 attempts to play a green card with rank 2. The card did not match the current state of the fireworks. This costs one fuse token. There are 3 fuse tokens remaining.                          │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
│                                                                                                                                                                                                       │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```

## Gameplay
- **Players:** 2-5.
- **Rounds:** Flexible. The game ends immediately if all fuse tokens are used up, or when all 5s have been played successfully. If the deck has run out, the game continues for another round before ending. 
- **Turn Structure:**
  - The players receive information about the board and game state. 
  - The players may submit `play`, `reveal`, or `discard` based on the game state.
  - All players receive feedback and prepare for the next round
  
- **Objective:** Maximize the score before the game has ended. The score is calculated by summing the values of the highest cards that have been played for each suit. The maximal score is 25. 

## Key Rules
1. **Action Selection:**
   - Each player must submit exactly one action per turn
   - Valid actions begin with `play`, `reveal`, or `discard`.
   
2.**Game Duration:**
- The game duration depends on the number of rounds. 

3.**Invalid Moves:**
- During decision turns, only `play`, `reveal`, or `discard` actions are valid.
- Invalid moves may count as defection or be penalized (implementation-specific)

4.**Winning Conditions:**
- The players "win" (receiving the maximal score) if all 5s are played. 

## Strategic elements
1. **Communication:** Players may use the information tokens to communicate relevant information to their teammates. 
2. **Reasoning:** Players have to reason about their own cards given the hints from their teammates. Furthermore, players need to decide what to communicate, for communication tokens are limited. 

## Parameters

- `num_players` (`int`):
    - **Description**: The number of players in the game
    - **Default**: None
    - **Impact**: Determines how many players play the game. Implicitly determines how many cards the players have. Players in games with three or fewer players hold 5 cards, four or more players have 4 cards

- `info_tokens` (`int`):
    - **Description**: The initial number of information tokens
    - **Default**: 8
    - **Impact**: Affects how much the players can communicate

- `fuse_tokens` (`int`):
    - **Description**: The total number of fuse tokens
    - **Default**: 4
    - **Impact**: Affects how often the players may make mistakes when building firework sequences. Regulates the game length.