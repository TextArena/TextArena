# BlindAuction Environment Documentation

## Overview
**BlindAuction** is a multi-player strategic auction game where players bid on items with different personal valuations. The game consists of two phases: a conversation phase where players can communicate openly or privately, followed by a bidding phase where each player submits blind bids for items. The goal is to maximize profit by strategically bidding on items that are worth more to you than what you pay. This environment supports flexible communication, strategic information gathering, and competitive bidding in a multi-player setting.

## Action Space

- **Format:** Actions are strings that vary based on the current game phase:
  - **Conversation Phase:**
    - **Broadcast:** `Broadcast: message`
    - **Private Message:** `Whisper to X: message` where X is a player ID
  - **Bidding Phase:**
    - **Bid:** `Bid on Item X: amount` where X is an item ID and amount is the bid in coins

- **Examples:**
  - Send a public message: `Broadcast: I'm interested in the Ancient Vase`
  - Send a private message: `Whisper to 2: Are you bidding on the Diamond Necklace?`
  - Submit a bid: `Bid on Item 0: 250`
  - Submit multiple bids on separate lines or separated by semicolons: `Bid on Item 0: 250; Bid on Item 3: 175`

- **Notes:** Players can include multiple bids in a single bidding phase action, allowing them to bid on multiple items simultaneously.

## Observation Space

**Reset Observations**
On reset, each player receives a prompt containing their starting capital, item information, and personal valuations. For example:

```plaintext
Welcome to the Blind Auction, Player 0!

You have 1000 coins to bid on 5 valuable items.

The auction has two phases:
1. Conversation Phase (3 rounds): Talk with other players to gather information or make deals.
2. Bidding Phase (1 round): Submit blind bids on items. Highest bidder wins each item.

Available Items (with their value TO YOU):
- Item 0: Ancient Vase - Value to you: 420 coins
- Item 1: Diamond Necklace - Value to you: 385 coins
- Item 2: Antique Clock - Value to you: 175 coins
- Item 3: Signed Painting - Value to you: 290 coins
- Item 4: Gold Statue - Value to you: 510 coins

Note: Each player may value items differently, up to ±20% difference!

Available Commands:
- Conversation Phase:
  'Broadcast: message' - Send a message to all players
  'Whisper to X: message' - Send a private message to Player X

- Bidding Phase:
  'Bid on Item X: amount' - Bid the specified amount on Item X
  You can submit multiple bids for different items in a single turn.

Your goal is to win items that are worth more to you than what you paid, maximizing your profit.
The winner is the player with the highest total value of items minus spent coins.
```

**Step Observations**
During gameplay, players receive various observations based on actions taken. For example:

```plaintext
[Player 1] Broadcast: Is anyone particularly interested in the Gold Statue?
[GAME] (Broadcast) Player 1 says: Is anyone particularly interested in the Gold Statue?
[Player 2] Whisper to 1: I'm more interested in the Diamond Necklace than the Gold Statue
[GAME] (Private) Player 2 says: I'm more interested in the Diamond Necklace than the Gold Statue

[GAME] Conversation phase complete! Now entering the bidding phase. Each player will have one turn to submit bids.
[GAME] Bidding Format: 'Bid on Item X: amount' - Bid the specified amount on Item X
You can submit multiple bids in a single turn. Highest bidder wins each item.

[Player 0] Bid on Item 0: 300; Bid on Item 4: 450
[GAME] Player 0 submitted bids for Items: 0, 4.

[GAME] ==================== AUCTION RESULTS ====================

🏆 ITEM RESULTS:
- Item 0 (Ancient Vase): Won by Player 0 for 300 coins
  Value to Player 0: 420 coins (Profit: 120 coins)
- Item 1 (Diamond Necklace): Won by Player 2 for 325 coins
  Value to Player 2: 405 coins (Profit: 80 coins)
...
```

## Gameplay

- **Players:** 3-15 players
- **Initial Setup:** Each player starts with an equal amount of capital (coins)
- **Item Valuation:** Each player has personal valuations for each item that vary up to ±20% from base values
- **Phases:**
  1. **Conversation Phase:** Players take turns communicating
  2. **Bidding Phase:** Players submit bids for items
- **Objective:** Maximize profit by winning items for less than their value to you
- **Game Structure:** Configurable number of conversation rounds followed by a single bidding round

## Key Rules

1. **Capital Management:**
   - Each player begins with the same starting capital
   - Players cannot bid more than their available capital
   - The total of all bids cannot exceed a player's remaining capital

2. **Communication:**
   - **Broadcasting:** Send messages visible to all players
   - **Private Messaging:** Send messages only visible to a specific player
   - Communication happens only during the conversation phase

3. **Bidding System:**
   - **Blind Bidding:** Players cannot see others' bids until results are revealed
   - **Multiple Bids:** Players can bid on as many items as they want in a single turn
   - **Highest Bid Wins:** For each item, the player with the highest bid wins
   - **Payment:** Only winning bids are paid; losing and tied bids are returned

4. **Valid Moves:**
   - During conversation phase: broadcast and whisper actions
   - During bidding phase: bid actions
   - Bids must be positive integers and cannot exceed remaining capital

5. **Winning Conditions:**
   - The player with the highest net worth at the end of the game wins
   - Net worth = remaining capital + total value of won items
   - In case of a tie, multiple players are declared winners

6. **Game Termination:**
   - The game concludes after all players have submitted their bids
   - Final scores are calculated based on each player's net worth

## Rewards

| Outcome     | Reward for Winner | Reward for Others |
|-------------|:-----------------:|:-----------------:|
| **Win**     | `+1`              | `-1`              |
| **Draw**    | `0`               | `0`               |
| **Invalid** | `-1`              | `0`               |

## Parameters

- `starting_capital` (`int`, default: `1000`):
  - **Description:** Initial amount of coins for each player
  - **Impact:** Higher values allow for more aggressive bidding strategies

- `num_items` (`int`, default: `5`):
  - **Description:** Number of items available for auction
  - **Impact:** More items create more complex bidding decisions and strategic considerations

- `conversation_rounds` (`int`, default: `3`):
  - **Description:** Number of conversation rounds before bidding
  - **Impact:** More rounds allow for better information gathering and potential deception

- `base_item_values` (`Optional[List[int]]`, default: `None`):
  - **Description:** Preset base values for items (if None, random values are generated)
  - **Impact:** Can be used to create specific auction scenarios with predetermined valuations

## Variants

| Env-id                    | starting_capital | num_items | conversation_rounds |
|---------------------------|:----------------:|:---------:|:-------------------:|
| `BlindAuction-v0`         | `1000`           | `5`       | `3`                 |
| `BlindAuction-v0-high`    | `2500`           | `8`       | `5`                 |
| `BlindAuction-v0-fast`    | `750`            | `3`       | `1`                 |
| `BlindAuction-v0-complex` | `1500`           | `12`      | `8`                 |

### Contact
If you have questions or face issues with this specific environment, please reach out directly to guertlerlo@cfar.a-star.edu.sg