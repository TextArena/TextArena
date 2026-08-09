# Negotiate to Survive Environment

This is an implementation of a 5-player survival negotiation game where players must strategically trade resources and coins to meet individual survival conditions. The game combines resource management, economic trading, and strategic communication in a competitive or cooperative framework depending on the variant.

## Game Description

Negotiate to Survive is a turn-based resource trading environment where 5 players start with unique resources and must collect enough different resources throughout the game to survive. Players use coins to purchase resources from each other while engaging in private/public negotiations and public proposals.

### Key Features

- **Resource collection mechanics**: Players must accumulate different resources to meet survival thresholds
- **Coin-based economy**: Pure market system where resources are bought and sold for coins
- **Private communication**: Whisper system for bilateral negotiations
- **Multiple resource ownership**: Players can own and accumulate multiple resources simultaneously
- **Two game variants**: Competitive (distributive) and cooperative (integrative) survival conditions
- **Individual survival tracking**: Each player's resource possession history is publicly tracked

### Game Variants

**Distributive Variant**: Competitive survival where each player needs to possess at least 4 out of 5 different resources at some point in the game. The surviving player with the highest coins wins.

**Integrative Variant**: Cooperative survival where each player needs to possess all 5 resources at some point in the game. All surviving players win together.

### Resources and Starting Conditions

**Resources**: food, water, shelter, medicine, clothing

**Starting Setup**:
- **Player 0**: food + 50 coins
- **Player 1**: water + 50 coins  
- **Player 2**: shelter + 50 coins
- **Player 3**: medicine + 50 coins
- **Player 4**: clothing + 50 coins

## Components

- **5 players**: Each starting with one unique resource and 50 coins
- **5 resources**: food, water, shelter, medicine, clothing
- **Coin economy**: Players trade coins for resources in a pure market system
- **Resource history tracking**: Public record of which resources each player has owned
- **Private whisper system**: Bilateral communication with public notifications
- **Maximum rounds**: Default 100 rounds with error allowance of 3 invalid moves per player

## Turn Structure

1. Players take turns in order (0 → 1 → 2 → 3 → 4 → 0...)
2. Each turn consists of:
   - **Free text communication** (broadcast to all players)
   - **One bracketed action**: Whisper, Propose, Accept, or Pass
3. Game continues until survival conditions are met or maximum rounds reached

## Actions

### Whisper (Private Communication)
- **Format**: `[Whisper] <player_id> <message>`
- **Privacy**: Only target player sees message content
- **Public notification**: Other players see "Player X whispered to Player Y"
- **Restrictions**: Cannot whisper to yourself

### Propose (Resource Trading)
- **Format**: `[Propose] <coins> for <resource>`
- **Public**: All players see the proposal with unique ID
- **Validation**: Must have sufficient coins, valid resource name
- **Ownership**: Only current resource owner can accept

### Accept (Complete Trade)
- **Format**: `[Accept] <proposal_id>`
- **Trade execution**: Coins and resource transfer simultaneously
- **Restrictions**: Must own the requested resource, cannot accept own proposals
- **Result**: Proposer gets resource, accepter gets coins and loses resource

### Pass
- **Format**: `[Pass]`
- **Effect**: Skip turn with no action

## Rules

### Trading Mechanics
- **Pure coin economy**: Only coins can be offered for resources (no bartering)
- **Resource accumulation**: Players can own multiple resources simultaneously
- **Ownership transfer**: When a resource is sold, it transfers to the buyer
- **No resource destruction**: All 5 resources always have exactly one owner

### Survival Conditions
- **Distributive**: Need to have owned 4+ different resources at any point
- **Integrative**: Need to have owned all 5 resources at any point
- **History tracking**: Public record shows which resources each player has possessed
- **Individual requirement**: Each player must meet conditions independently

### Communication Rules
- **Free text**: Always broadcast to all players
- **Whispers**: Private between sender and receiver only
- **Public proposals**: All trading proposals are visible to everyone
- **Sender identification**: Whisper recipients know who sent the message

### Invalid Moves
- Players have 3 invalid moves allowed before automatic default action ([Pass])
- Invalid moves include incorrect formats, insufficient coins, or self-interaction attempts
- Error escalation system provides feedback and retry opportunities

## Winning Conditions

### Distributive Variant
The game ends when any player has owned 4+ different resources:
- **Winner**: Surviving player with the highest coins
- **Tie-breaking**: Multiple survivors share victory if tied on coins
- **Failure**: If no one survives by max rounds, everyone loses

### Integrative Variant  
The game ends when any player has owned all 5 resources:
- **Winner**: All players who have met survival conditions win together
- **Cooperative victory**: Success is shared among all survivors
- **Failure**: If no one survives by max rounds, everyone loses

## Usage

### Action Format Examples

**Making a proposal with negotiation:**
```
I need medicine to complete my collection. This is a fair offer.
[Propose] 25 for medicine
```

**Private negotiation:**
```
Let's work together on this trade.
[Whisper] 3 I'll pay 30 coins for your medicine if you accept my next proposal
```

**Accepting a trade:**
```
That's a reasonable price for my water.
[Accept] 2
```

**Strategic passing:**
```
I'll wait to see what other offers come up.
[Pass]
```

### Example Game Flow

1. **Player 0** (food): `I need to diversify my resources [Propose] 15 for water`
2. **Player 1** (water): `[Whisper] 0 Can you go up to 20 coins?`
3. **Player 2** (shelter): `I'm also interested in water [Propose] 18 for water`
4. **Player 3** (medicine): `Looking to trade as well [Pass]`
5. **Player 4** (clothing): `I'll wait for better opportunities [Pass]`
6. **Player 0**: `I can do 20 coins [Propose] 20 for water`
7. **Player 1**: `Deal! [Accept] 3`
8. **Trade executed**: Player 0 now has [food, water] and 30 coins, Player 1 has [] and 70 coins

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create distributive variant (competitive)
env = ta.make(env_id="NegotiateToSurvive-v0-distributive")

# Or create integrative variant (cooperative)
env = ta.make(env_id="NegotiateToSurvive-v0-integrative")

# Reset with 5 players (required)
env.reset(num_players=5)
```

### Run a Simple Game

```python
import textarena as ta

# Set up agents
agents = {
    0: ta.agents.HumanAgent(),  # Human player
    1: ta.agents.OpenRouterAgent(model_name="your-model-name"),
    2: ta.agents.OpenRouterAgent(model_name="your-model-name"),
    3: ta.agents.OpenRouterAgent(model_name="your-model-name"),
    4: ta.agents.OpenRouterAgent(model_name="your-model-name"),
}

# Initialize the environment
env = ta.make(env_id="NegotiateToSurvive-v0-distributive")
env.reset(num_players=len(agents))

# Main game loop
done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action=action)

# Get final results
rewards, game_info = env.close()
print(f"Rewards: {rewards}")
print(f"Game Info: {game_info}")
```

### Custom Configuration

```python
# Create environment with custom settings
env = ta.make(env_id="NegotiateToSurvive-v0-distributive",
              max_rounds=50,        # Shorter game
              starting_coins=100,   # More coins to start
              error_allowance=5)    # Allow more invalid moves

# Reset and play
env.reset(num_players=5)
```

## Game State Information

### Public Information
- **Current resource ownership**: Who owns which resources right now
- **Resource possession history**: Complete record of who has owned each resource
- **Active proposals**: All current trading proposals with IDs and details
- **Player coins**: Everyone's current coin totals
- **Survival progress**: Each player's progress toward survival conditions

### Private Information
- **Whisper content**: Only sender and receiver see message content
- **Strategic planning**: Players' internal decision-making processes

### Example Game State Display

```
INDIVIDUAL SURVIVAL PROGRESS (need 4 resources to survive):
Player 0: 2 out of 5 resources
Player 1: 1 out of 5 resources  
Player 2: 1 out of 5 resources
Player 3: 3 out of 5 resources
Player 4: 1 out of 5 resources

CURRENT RESOURCE OWNERSHIP:
==============================
Food: Player 0
Water: Player 0  
Shelter: Player 2
Medicine: Player 3
Clothing: Player 4

RESOURCE POSSESSION HISTORY:
==============================
Food: Player 0
Water: Player 1 -> Player 0
Shelter: Player 2
Medicine: Player 3
Clothing: Player 4

ACTIVE PROPOSALS:
==============================
Proposal 1: Player 3 offers 25 coins for clothing (Player 4 can accept) - Round 8

YOUR STATUS:
===============
Your resources: food, water
Your coins: 30
```

## Strategic Considerations

### Resource Collection Strategy
- **Early trading**: Acquire diverse resources quickly to meet survival thresholds
- **Coin management**: Balance spending on resources vs. maintaining coins for victory
- **Market timing**: Buy when prices are low, sell when demand is high

### Communication Strategy  
- **Private negotiations**: Use whispers to negotiate prices and coordinate trades
- **Public signaling**: Broadcast intentions to create market dynamics
- **Information gathering**: Learn about other players' needs and resources

### Variant-Specific Tactics

**Distributive (Competitive)**:
- Focus on reaching 4 resources first while maximizing remaining coins
- Consider blocking others from completing their collections
- Balance cooperation (trading) with competition (coin preservation)

**Integrative (Cooperative)**:
- Coordinate with others to ensure everyone can collect all resources
- Share information about resource needs and trading plans
- Optimize collective success rather than individual advantage

## Implementation Notes

### Technical Features
- **Robust action parsing**: Handles free text with bracketed actions
- **Resource ownership tracking**: Ensures all resources always have exactly one owner
- **Whisper privacy system**: Secure private communication with public notifications
- **Comprehensive validation**: Prevents self-trading, insufficient funds, and invalid formats
- **Error handling**: Graceful escalation system for invalid actions
- **History tracking**: Complete audit trail of all resource transfers

### Validation Systems
- **Self-interaction prevention**: Cannot whisper to self or accept own proposals
- **Resource ownership validation**: Only current owners can sell resources
- **Coin sufficiency checks**: Cannot propose more coins than possessed
- **Proposal lifecycle management**: Automatic cleanup and ID tracking
- **Format validation**: Strict parsing with helpful error messages

### Testing Coverage
The environment includes 28 comprehensive tests covering:
- Action format validation and edge cases
- Trading mechanics and resource tracking  
- Whisper functionality and privacy
- End game logic for both variants
- Self-interaction validation
- Error handling and recovery
- Integration testing

## Available Variants

- **NegotiateToSurvive-v0-distributive**: Competitive variant (4/5 resources needed, highest coins wins)
- **NegotiateToSurvive-v0-integrative**: Cooperative variant (5/5 resources needed, all survivors win)

# Reference

Sotak, K. L., & Abraham, S. E. (2021). Negotiate to survive: An exercise to help develop students’ understanding of negotiations. Journal of Education for Business, 96(4), 269-273.