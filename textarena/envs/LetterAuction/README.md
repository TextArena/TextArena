# Letter Auction Environment Documentation

## Overview
**Letter Auction Game** is a two-player bidding-based game where players compete to acquire letters through an auction, aiming to use the collected letters to form the highest value English word by the game's end. Each player starts with a set number of coins, which they use to bid on letters in rounds. Players strategically decide to bid or pass on each letter, aiming to outbid their opponent and secure valuable letters without depleting their coins. After all letters are auctioned, players form the highest possible value word using only the letters they've won. The player with the highest word value wins the game. This environment supports gameplay features such as automated bidding rounds, coin tracking, and final word scoring.


## Action Space
- **Format:** Actions are strings representing the player's actions. For example:
- **Example:**
    - Bid 10 coins for the round's letter: `bid 10`
    - Pass on the round's letter: `pass`
    - To submit the word "SEE" based on the letters ["S", "E", "E"]: `see`
- **Notes:** Submit exactly one bare action without surrounding prose.

## Observation Space
**Reset Observations**
On reset, each player receives a prompt containing their beginning game instructions. For example:
```plaintext
[GAME] You are Player 1. You are currently in the Letter Auction game.
The goal of the game is to strategically bid on letters to form the highest value word. This is how the game works.
You must listen to the gamemaster for guidance to play the game.
The game consists of a series of rounds. In each round, a letter will be put up for auction.
You can bid on the letter using your coins. The player with the highest bid wins the letter.
The letter will be added to your collection, and the coins you bid will be deducted from your total.
This bidding of letters will repeat till all the letters have been auctioned off. You are not rewarded for saving your coins.
After all the letters have been auctioned, you will use the letters to form the highest value english word from the letters won.
The player with the highest value word wins the game.
To bid, reply with 'bid 2', 'bid 10', or another amount.
If you do not want to bid, reply with 'pass'.
At the end of the auction, submit your highest-value word directly, e.g. 'dog'.
Here is your starting information:
Your current coins: 100
Your current letters: []

Game: Player 0 will go first. The first letter for bid: M.
Starting bid is 1 coin. You can bid any amount of coins, or choose not to bid.
```

**Step Observation:**
After each step, the players receive the latest message from the game environment that determines who gets the word, and what the next letter is for bidding. For example:
```plaintext
[Player 0] bid 5
[GAME] Player 0 bids 5 on the letter 'M'. Player 1, do you want to bid on the letter 'M' for more than 5?
```

## Gameplay

- **Players**: 2
- **Turns**: Players take turns either bidding on a letter or passing. Each turn, a player can place a bid to acquire the letter for a specified coin amount or pass, allowing the opponent to bid.
- **Board**: The game consists of a shared pool of letters, randomly ordered for auction in each session. Players have separate coin balances and letter collections.
- **Objective**: Outbid the opponent to acquire valuable letters and form the highest value word at the end of the game.
- **Difficulty Levels**:
  - **Easy**: Players start with 100 coins.
  - **Medium**: Players start with 50 coins.
  - **Hard**: Players start with 25 coins.
- **Bidding Phase**: Players alternate turns to bid or pass on each letter. If both pass, the letter is forfeited, and no player acquires it.
- **Word Formation Phase**: After the bidding phase, players use the letters they won to form a high-value English word. The value of a word is determined by the combined bid values of the letters in that word.
- **Winning Condition**: The player who creates the word with the highest value wins. In the case of a tie, the game ends in a draw.

## Key Rules

1. **Bidding**:
   - Players take turns deciding to bid on a letter or pass (e.g., `bid 10` or `pass`).
   - The player with the highest bid on a letter wins it and adds it to their collection.
   - If both players pass on a letter, it is forfeited, and neither player can use it in word formation.

2. **Valid Actions**:
   - Players must either place a bid that does not exceed their current coins or choose to pass.
   - A bid action is only valid if the player has enough coins to cover the amount. Passing forfeits the opportunity to bid on the letter for that round.

3. **Word Formation**:
   - After all letters have been auctioned, players use the letters they've won to form an English word, aiming for the highest possible value.
   - The word's value is calculated based on the sum of bid amounts for the letters used in the word.
   - Only valid English words formed with acquired letters are accepted.

4. **Winning Conditions**:
   - **Win**: The player whose word has the highest value (total of bid amounts for each letter) wins the game.
   - **Draw**: If both players create words with the same value, the game ends in a draw.

5. **Game Termination**:
   - The game ends once both players submit their final words. The player with the higher word value wins, or the game results in a draw if both values are identical.

## Rewards

| Outcome          | Reward for Player | Reward for Opponent |
|------------------|:-----------------:|:-------------------:|
| **Win**          | `+1`              | `-1`                |
| **Lose**         | `-1`              | `+1`                |
| **Draw**         | `0`               | `0`                 |
| **Invalid**      | `-1`              | `0`                 |

## Parameters

- `difficulty` (`str`):
    - **Description**: Sets the difficulty level, which determines the number of starting coins for each player.
    - **Options**:
        - `"easy"`: Players start with 100 coins, allowing for higher and more frequent bids, suitable for beginners.
        - `"medium"`: Players start with 50 coins, offering a balanced gameplay experience where players must be strategic with their bids.
        - `"hard"`: Players start with 25 coins, challenging players to manage limited resources carefully.
    - **Impact**:
        - Higher difficulty levels reduce the starting coin amount, increasing the strategic complexity of each bid and encouraging players to save coins for valuable letters.

## Variants

| Env-id                    | starting_coins |
|---------------------------|:--------------:|
| `LetterAuction-v0-easy`   | `100`          |
| `LetterAuction-v0-medium` | `50`           |
| `LetterAuction-v0-hard`   | `25`           |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to bobby_cheng@i2r.a-star.edu.sg