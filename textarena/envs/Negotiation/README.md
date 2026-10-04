# Negotiation Environment Documentation

## Overview
**Negotiation** is a multi-player strategic trading game where players manage resources with different personal valuations. Players can communicate openly or privately, make targeted trade offers, and accept or deny proposals from others. The goal is to maximize the total value of your resource portfolio through strategic trading and negotiation. This environment supports flexible communication options and a robust trading system for complex multi-player interactions.

## Action Space

- **Format:** Submit one bare command:
  - **Broadcast:** `Broadcast: message`
  - **Private Message:** `Whisper to X: message` where X is a player ID
  - **Trade Offer:** `Offer to X: A B -> C D` where X is a player ID, and A B -> C D represents resources offered and requested
  - **Accept/Deny Offer:** `Accept #X` or `Deny #X` where X is an offer ID

- **Examples:**
  - Send a public message: `Broadcast: I have excess Wheat to trade`
  - Send a private message: `Whisper to 2: Would you trade your Wood for my Wheat?`
  - Make a trade offer: `Offer to 3: 2 Wheat, 1 Ore -> 3 Wood`
  - Accept a pending offer: `Accept #5`

## Observation Space

**Reset Observations**
On reset, each player receives a prompt containing their resource information and personal valuations. For example:

```plaintext
You are Player 0 in a multi-player game of Negotiation with 4 players.
You have:
- 12 x Wheat (value: 6 each)
- 18 x Wood (value: 8 each)
- 8 x Sheep (value: 17 each)
- 10 x Brick (value: 23 each)
- 7 x Ore (value: 35 each)

You can broadcast messages, privately message someone, or make trade offers.
You can also accept or deny any offers you received previously.
Your personal valuations are shown above; your goal is to maximize your total resource value.
Available actions:
  'Broadcast: Some message' - Send a message to all players
  'Whisper to X: Some message' - Send a private message to a specific player
  'Offer to X: 2 Wheat -> 3 Wood' - Make a trade offer to a specific player
  'Accept #X' or 'Deny #X' - Accept or deny a trade offer
Game ends after 12 turns.
```

**Step Observations**
During gameplay, players receive various observations based on actions taken. For example:

```plaintext
[Player 1] Broadcast: I have excess Wheat and need Wood. Anyone interested in trading?
[GAME] (Broadcast) Player 1 says: I have excess Wheat and need Wood. Anyone interested in trading?
[Player 2] Whisper to 1: I can trade 3 Wood for 4 Wheat
[GAME] (Private) Player 2 says: I can trade 3 Wood for 4 Wheat
[Player 1] Offer to 2: 4 Wheat -> 3 Wood
[GAME] Offer #1 created: Player 1 -> Player 2.
[GAME] You have a new offer [ID #1] from Player 1: 4 Wheat -> 3 Wood
You can accept #1 or deny #1.
[Player 2] Accept #1
[GAME] Player 2 ACCEPTED Offer #1 from Player 1: 4 Wheat -> 3 Wood
```

## Gameplay

- **Players:** 2-15 players
- **Initial Setup:** Each player starts with random amounts of five different resources (Wheat, Wood, Sheep, Brick, Ore)
- **Resource Valuation:** Each player has personal valuations for each resource that vary slightly from base market values
- **Turns:** Players take turns communicating, making offers, and accepting/denying pending offers
- **Objective:** Maximize the total value of your resource portfolio by the end of the game
- **Maximum Turns:** Configurable, default is 3 turns per player (e.g., 12 turns for 4 players)

## Key Rules

1. **Resource Management:**
   - Each player begins with random amounts of five different resources
   - Each player has unique personal valuations for each resource
   - Players can only trade resources they possess in sufficient quantities

2. **Communication:**
   - **Broadcasting:** Send messages visible to all players
   - **Private Messaging:** Send messages only visible to a specific player
   - Both communication types do not directly affect game state but facilitate negotiations

3. **Trading System:**
   - **Making Offers:** Specify resources to give and receive with a target player
   - **Accepting Offers:** Target player can accept if both parties have the required resources
   - **Denying Offers:** Target player can deny any offer directed to them
   - **Automatic Cancellation:** Offers are canceled if the offering player no longer has sufficient resources

4. **Valid Moves:**
   - Players can perform multiple actions in a single turn (broadcast, whisper, offer, accept, deny)
   - Trade offers must specify valid resource types and quantities
   - Only the player to whom an offer was made can accept or deny it

5. **Winning Conditions:**
   - **Win:** The player with the highest total resource value at game end
   - **Draw:** Multiple players tied for the highest resource value
   - **Loss:** Having a lower total resource value than another player at game end

6. **Game Termination:**
   - The game concludes after a predetermined number of turns (default: players × turn_multiple)
   - Final scores are calculated based on each player's personal valuations of their resources

## Rewards

| Outcome     | Reward for Winner | Reward for Others |
|-------------|:-----------------:|:-----------------:|
| **Win**     | `+1`              | `-1`              |
| **Draw**    | `0`               | `0`               |
| **Invalid** | `-1`              | `0`               |

## Parameters

- `turn_multiple` (`int`, default: `3`):
  - **Description:** Sets the number of turns per player
  - **Impact:** Higher values provide more opportunities for negotiation and trading

## Variants

| Env-id                   | turn_multiple |
|--------------------------|:-------------:|
| `Negotiation-v0`         | `8`           |
| `Negotiation-v0-long`    | `15`          |


### Contact
If you have questions or face issues with this specific environment, please reach out directly to guertlerlo@cfar.a-star.edu.sg