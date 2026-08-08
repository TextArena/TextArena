# Win as Much as You Can Environment

This is an implementation of the classic [Win as Much as You Can](https://www.pibetaphi.org/Admin/PiBetaPhi/media/About-Us/Programs/Collegiate-Leading-With-Values/Win-as-Much-as-You-Can.pdf) game, a strategic decision-making environment that explores cooperation vs competition dynamics in multi-player settings. The game is based on the prisoner's dilemma framework but extended to 4 players with communication phases and variable scoring multipliers.

## Game Description

Win as Much as You Can is a 4-player strategic game where players must choose between two options (X or Y) across 10 rounds to maximize their individual scores. The game features alternating phases of decision-making and communication, with increasing point multipliers in later rounds that make cooperation and negotiation increasingly important.

### Key Features

- **4-player strategic gameplay**: Fixed player count with zero-indexed players (0, 1, 2, 3)
- **10 scoring rounds**: Complete game with escalating stakes
- **Dual-phase structure**: Action phases for decisions, talk phases for negotiation
- **Communication system**: Public broadcasts and private whispers
- **Variable scoring multipliers**: 1x, 3x, 5x, and 10x point multipliers
- **Prisoner's dilemma dynamics**: Individual vs. collective optimization

### Game Objective

Each player aims to **earn the most points possible** over 10 rounds by strategically choosing between X and Y, while navigating the tension between individual gain and collective benefit.

## Scoring System

The scoring rubric creates a classic social dilemma where individual and group interests conflict:

| X Count | Y Count | X Players | Y Players |
|---------|---------|-----------|-----------|
| 1 X | 3 Y | **+3 points** | **-1 point each** |
| 2 X | 2 Y | **+2 points each** | **-2 points each** |
| 3 X | 1 Y | **+1 point each** | **-3 points** |
| 4 X | 0 Y | **-1 point each** | **0 points** |
| 0 X | 4 Y | **0 points** | **+1 point each** |

### Strategic Implications

- **Cooperation (all Y)**: Everyone gets +1 point - safe but modest gains
- **Defection (choosing X)**: Risk/reward increases with fewer X players
- **Mass defection (all X)**: Everyone loses points - worst collective outcome
- **Mixed strategies**: Create winners and losers with varying point spreads

## Round Structure

### Rounds 1-4: Pure Action Phases
- **Phase**: Act only
- **Multiplier**: 1x points
- **Actions**: Each player chooses `[Choose X]` or `[Choose Y]`
- **Scoring**: Standard rubric applied

### Round 5: Communication + High Stakes
- **Talk Phase**: Up to 40 conversation rounds (10 per player max)
- **Act Phase**: Players choose X or Y
- **Multiplier**: **3x points** - first major escalation

### Rounds 6-7: Return to Basics
- **Phase**: Act only
- **Multiplier**: 1x points
- **Purpose**: Test if communication agreements hold

### Round 8: Strategic Communication
- **Talk Phase**: Up to 40 conversation rounds (10 per player max)
- **Act Phase**: Players choose X or Y  
- **Multiplier**: **5x points** - significant stakes increase

### Round 9: Penultimate Decision
- **Phase**: Act only
- **Multiplier**: 1x points
- **Tension**: Final chance before the climactic round

### Round 10: Ultimate Stakes
- **Talk Phase**: Up to 40 conversation rounds (10 per player max)
- **Act Phase**: Final choices
- **Multiplier**: **10x points** - maximum impact round

## Communication System

### Talk Phase Rules

**Turn-based communication** where players take turns to:
- Send public messages visible to all players
- Send private messages to specific players
- Pass to end their participation in the talk phase

**Phase Termination:**
- Maximum 40 total conversation rounds reached, OR
- All players have passed

### Communication Actions

**Public Broadcasting:**
```
[Broadcast] Let's all choose Y for mutual benefit!
```
- Everyone sees the sender and message content
- Builds trust through transparency
- Coordinates group strategies

**Private Messaging:**
```
[Whisper to 2] I'll choose Y if you do the same
```
- Only sender and receiver know the content
- Others see "A private message was sent between two players"
- Enables secret alliances and side deals

**Passing:**
```
[Pass]
```
- Ends participation in current talk phase
- Cannot send more messages this phase
- Phase ends when all players pass

## Action Phase Rules

### Making Choices
Players simultaneously choose their actions:

**Choose X (Competitive):**
```
[Choose X]
```

**Choose Y (Cooperative):**
```
[Choose Y]
```

### Simultaneous Resolution
- All players make choices before any are revealed
- Choices are revealed simultaneously after all players decide
- Points calculated and awarded based on the distribution
- Round results announced to all players

## Winning Conditions

**Game End:** After all 10 rounds are completed

**Winner Determination:**
- Player with the highest total score wins
- Ties are possible and result in shared victory
- Scores can be negative due to the scoring rubric

**Strategic Considerations:**
- Early rounds establish patterns and trust
- Communication rounds allow for negotiation and alliance-building
- High-multiplier rounds can dramatically shift final standings
- Final round (10x multiplier) often determines the ultimate winner

## Usage

### Action Format Examples

**During Act Phases:**
```
[Choose X]
[Choose Y]
```

**During Talk Phases:**
```
[Broadcast] I propose we all choose Y this round for +1 each
[Whisper to 1] Want to form an alliance? We both choose Y?
[Pass]
```

### Example Game Flow

**Round 1 (Act Phase - 1x):**
- Player 0: `[Choose Y]`
- Player 1: `[Choose Y]` 
- Player 2: `[Choose X]`
- Player 3: `[Choose Y]`
- **Result**: 1X, 3Y → Player 2: +3, Others: -1 each

**Round 5 (Talk + Act Phase - 3x):**
- **Talk Phase:**
  - Player 0: `[Broadcast] That X choice hurt us all. Let's cooperate this time.`
  - Player 2: `[Broadcast] Sorry about that. I'll choose Y this round.`
  - Player 1: `[Whisper to 3] Don't trust Player 2. Want to both choose X?`
  - Player 3: `[Whisper to 1] Agreed. X it is.`
  - All players: `[Pass]`
- **Act Phase:**
  - All choose Y except Players 1&3 choose X
  - **Result**: 2X, 2Y → X players: +6 each, Y players: -6 each

**Round 10 (Talk + Act Phase - 10x):**
- High-stakes negotiation determines final winner
- 10x multiplier makes this round often decisive

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create the environment
env = ta.make(env_id="WinAsMuchAsYouCan-v0")

# Reset with 4 players (required)
env.reset(num_players=4)
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
}

# Initialize the environment
env = ta.make(env_id="WinAsMuchAsYouCan-v0")
env.reset(num_players=len(agents))

# Main game loop
done = False
while not done:
    player_id, observation = env.get_observation()
    action = agents[player_id](observation)
    done, step_info = env.step(action=action)

# Get final results
rewards, game_info = env.close()
print(f"Final Scores: {rewards}")
print(f"Game Info: {game_info}")
```

### Custom Configuration

```python
# Create environment with custom error allowance
env = ta.make(env_id="WinAsMuchAsYouCan-v0", 
              error_allowance=5)  # Allow 5 invalid moves per player
```

## Strategic Analysis

### Cooperation vs. Competition

**Pure Cooperation (All Y):**
- Guaranteed +1 point per round for everyone
- Safe but limits maximum gains
- Builds trust for future rounds

**Strategic Defection:**
- Choosing X when others choose Y maximizes individual gain
- Risk: Others may retaliate in future rounds
- High reward in multiplier rounds

**Communication Impact:**
- Talk phases allow coordination and trust-building
- Private messages enable secret alliances
- Public commitments create accountability

### Psychological Dynamics

**Trust Building:**
- Early cooperation establishes positive patterns
- Communication phases allow relationship building
- Reputation effects across rounds

**Betrayal and Retaliation:**
- Unexpected X choices can trigger revenge cycles
- Communication allows explanation and forgiveness
- Final rounds may see increased defection

**Alliance Formation:**
- Private messaging enables 2-3 player coalitions
- Temporary alliances may shift based on scores
- Endgame alliances often determine winners

## Implementation Notes

### Technical Features

- **Privacy-preserving whispers**: Private messages are truly private
- **Turn-based communication**: Orderly conversation flow
- **Simultaneous action resolution**: Prevents information advantages
- **Comprehensive scoring tracking**: Full history of all rounds
- **Flexible communication limits**: Configurable talk phase parameters

### Game Balance

- **Escalating stakes**: Multipliers create increasing tension
- **Communication timing**: Strategic placement of talk phases
- **Score transparency**: All players see current standings
- **No elimination**: All players participate through all 10 rounds

### Error Handling

- **Invalid move allowance**: Default 3 invalid moves per player before penalties
- **Action format validation**: Clear feedback on incorrect formats
- **Graceful degradation**: Game continues despite individual player errors


## Citation

Pi Beta Phi. (n.d.). Win as Much as You Can. [PDF]. Pi Beta Phi. Retrieved from https://www.pibetaphi.org/Admin/PiBetaPhi/media/About-Us/Programs/Collegiate-Leading-With-Values/Win-as-Much-as-You-Can.pdf