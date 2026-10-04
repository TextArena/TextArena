# Two Rooms and a Boom Environment Documentation

## Overview
**Two Rooms and a Boom** is a social deduction game where players are divided into two teams (Red and Blue) and physically separated into two rooms. Players do not initially know other players' teams or roles. The Red Team's goal is to have the Red Team Bomber and Blue Team President in the same room at the end of the game, while the Blue Team's goal is to keep them in separate rooms. The game involves discussion, identity revelation, and strategic hostage exchanges between rooms.

## Action Space

- **Format:** Actions are strings that depend on the current game phase and player role:
  - **Discussion Phase (All Players):**
    - Free-form text communication with other players in the same room
    - Role revealing: Say `reveal card` or `show role` to initiate revealing your role
  - **Role Reveal Phase (Revealing Player Only):**
    - **Select Target:** `Player 3` or `3` to select which player to reveal to
  - **Leader Selection Phase (Room Leaders Only):**
    - **Select Hostage:** `Player 3` or `3` to select a player ID in the leader's room

- **Examples:**
  - Discussion: `I am on the Blue team, and I'm not the President.`
  - Role reveal initiation: `I want to reveal my card` (triggers system prompt)
  - Role reveal target selection: `Player 3` or `3`
  - Leader selection: `Player 3` or `3`

- **Notes:** The game automatically handles hostage exchanges and room transitions. Leaders cannot select themselves as hostages.

## Observation Space

**Reset Observations**
On reset, each player receives a prompt containing their role, team, and available actions:

```plaintext
Welcome to Two Rooms and a Boom! You are Player 2.
Your role: Blue
Team: Blue Team
Description: Member of the Blue Team. Your goal is to make sure the Bomber and President are in different rooms at the end of the game.

You are currently in Room 0.
You are the Leader of your room.

The game progresses through 3 rounds:
• In each round, players in the same room can talk to each other
• Room Leaders can choose one player to trade to the other room
• During discussions, you can choose to privately reveal your card to another player
• At the end of all rounds, the game checks which room contains the President and Bomber

The Red Team wins if the President and Bomber are in the same room at the end.
The Blue Team wins if the President and Bomber are in different rooms at the end.

Role Revealing:
• During discussions, you can say 'reveal card' or 'show role' to initiate revealing your role
• The game will then prompt you to select which player to reveal to
• You can reveal your role up to 5 times per game
• This is a way to build trust, but be careful who you reveal to!
```

**Step Observations**
During gameplay, players receive observations based on the current phase and actions:

```plaintext
# Discussion Phase
[GAME] Round 1: Discussion phase has started.
You are in Room 0 with: Player 0, Player 2, Player 4, Player 6.
You can talk freely with the other players in your room.
To reveal your role to someone, say 'reveal card' or 'show role' during your turn.

Players who have revealed their roles to you:
Player 0: Blue
Player 4: Red

[Player 0] I'm on the Blue team, but I'm not the President.
[Player 4] I'm on the Red team, just a regular member.

# Role Reveal Initiation
[GAME] You've chosen to reveal your role.
Players in your room: Player 0, Player 4, Player 6
To whom would you like to reveal your role?
Reply with the player number, e.g. 'Player X' or 'X'.
Valid options: 0, 4, 6

Note: This will be your reveal #1 out of 5 allowed reveals.

# Role Reveal Confirmation
[GAME] You revealed your role (Bomber) to Player 2. You have 4 reveals remaining.

# Role Reveal Notification (to target player)
[PRIVATE] Player 6 has revealed their card to you. Their true role is: President

# Leader Selection Phase
[GAME] Round 1: As the Leader of Room 0, you must select one player to trade with the other room.
Your team: Blue Team

Known player roles:
Player 0: Blue
Player 4: Red

Reply with the player number, e.g. 'Player X' or 'X'.
Valid options: 0, 4, 6

Strategic reminder: Blue Team wants the President and Bomber in different rooms at the end.
If you know who the Bomber is, consider your strategy carefully.

[LEADER] I have selected Player 4 to be traded with the other room.

# Trade Execution
[GAME] Round 1: The Leaders have exchanged hostages.
Player 4 moved from Room 0 to Room 1.
Player 5 moved from Room 1 to Room 0.
```

## Gameplay

- **Players:** 6-20 players, with `num_players` equal to `2 * cards_per_room`
- **Initial Setup:** Players are assigned roles and divided into two rooms with a leader for each room
- **Game Progression:** Multiple rounds of discussion followed by hostage exchanges
- **Objective:**
  - **Red Team:** Have the Bomber and President in the same room at the end
  - **Blue Team:** Keep the Bomber and President in different rooms at the end

## Key Rules

1. **Roles:**
   - **Blue Team Member:** Regular Blue Team member
   - **Red Team Member:** Regular Red Team member
   - **President:** Special Blue Team role (target for the Red Team)
   - **Bomber:** Special Red Team role (must reach the President for Red Team to win)
   - **Leader:** A player in each room designated as the leader (can be any role)

2. **Communication:**
   - Players can only communicate with others in the same room
   - Players can reveal their true role to specific players using the reveal mechanism
   - Each player is limited to 5 role reveals per game
   - Ordinary discussion does not expose authoritative role or team metadata

3. **Hostage Exchange:**
   - Each round, leaders select one player from their room to trade
   - Selected players swap rooms
   - Leaders cannot select themselves as hostages
   - If a leader is traded, a new leader is automatically appointed in that room

4. **Room Balance:**
   - Both rooms start with the configured number of players
   - Each completed exchange swaps one hostage from each room, preserving room sizes
   - If a leader fails to select a hostage, the system selects an eligible hostage at random

5. **Victory Conditions:**
   - **Red Team Wins:** The Bomber and President are in the same room at the end
   - **Blue Team Wins:** The Bomber and President are in different rooms at the end

## Rewards

| Outcome          | Reward for Winners | Reward for Others |
|------------------|:------------------:|:-----------------:|
| **Red Team Win** | `+1`               | `-1`              |
| **Blue Team Win**| `+1`               | `-1`              |

An invalid action is retried once. A second consecutive invalid action forfeits
that turn without eliminating the player or changing team rewards.

## Parameters

- `num_rounds` (`int`, default: `3`):
  - **Description:** Number of rounds to play
  - **Impact:** More rounds give players more information but also more opportunities for strategic moves

- `cards_per_room` (`int`, default: `3`):
  - **Description:** Exact number of player cards initially placed in each room; must be between 3 and 10
  - **Impact:** Reset requires exactly twice this many players

- `discussion_rounds` (`int`, default: `2`):
  - **Description:** Number of discussion turns each player gets per round
  - **Impact:** Controls how much communication occurs between hostage exchanges

## Game Phases

1. **Discussion:** Players in each room discuss freely to gather information and can initiate role reveals
2. **Role Reveal:** When a player chooses to reveal their role, they enter this phase to select a target player
3. **Leader Selection:** Room leaders select a hostage to trade
4. **Trade Execution:** Selected hostages swap rooms and the game either advances to the next round or ends

## Implementation Notes

- The game maintains two rooms with distinct sets of players
- Special roles (President and Bomber) are assigned to random players on the respective teams
- One leader is designated for each room, preferring regular team members over special roles
- The game automatically handles hostage exchanges and tracking which players are in which room
- Communication is strictly limited to players in the same room
- Role reveals use a system-guided two-step process (initiate, then select target)
- Role reveals are limited to 5 per player and only work within the same room
- Balanced room sizes are preserved by exchanging exactly one hostage each way
- The environment includes robust error recovery mechanisms
- Message history is capped at 200 messages per room and replayed only to players who witnessed each message
- Winning is determined by the final positions of the President and Bomber
- Player selections use `Player 3` or simply `3`.

## Example Game Flow

1. Game starts with players randomly assigned to roles and rooms
2. Leaders are randomly assigned in each room
3. Players discuss within their rooms
4. A player may say "reveal card" to initiate the role reveal process
5. The system prompts that player to select a target, who then receives the true role information
6. Leaders select hostages to trade
7. Hostages swap rooms
8. Steps 3-7 repeat for the specified number of rounds
9. Game ends and winner is determined based on President and Bomber locations

## Variants

| Env-id                     | num_rounds | cards_per_room | discussion_rounds |
|----------------------------|:----------:|:--------------:|:-----------------:|
| `TwoRoomsAndABoom-v0`      |    `3`     |      `3`       |        `2`        |

### Credit
Based on the party game "Two Rooms and a Boom" by Tuesday Knight Games.

### Contact
If you have questions or face issues with this specific environment, please reach out directly to [benjaminliu.eecs@gmail.com](mailto:benjaminliu.eecs@gmail.com).
