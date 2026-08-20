# Sally Soprano Negotiation Environment

This is an implementation of a 3-player negotiation game where two parties negotiate a salary contract while a third-party LLM judge evaluates the outcome. The game simulates realistic business negotiations with private information, conflicting interests, and strategic decision-making.

## Game Description

Sally Soprano is a turn-based negotiation environment where Sally's Agent and the Lyric Opera's Business Manager negotiate Sally's salary for performing the title role in the opera "Norma". Each player has private instructions with confidential constraints and goals, creating realistic scenarios where players must balance their interests while finding mutually acceptable solutions.

### Key Features

- **Bilateral negotiation**: Two players negotiate salary with conflicting private constraints
- **Private information**: Each player has hidden goals, constraints, and acceptable ranges
- **LLM judge evaluation**: Third-party AI judge determines who got the better deal
- **Automatic draw**: No deal after max rounds results in automatic draw
- **Rich rationale system**: Players can provide reasoning for proposals and decisions
- **Performance incentives**: Support for bonus structures and non-monetary terms

### Game Scenario

The scenario involves Sally Soprano, an aging but experienced opera singer, seeking to perform the title role in Bellini's "Norma" at the Lyric Opera. The negotiation takes place after the originally scheduled soprano had to withdraw due to medical issues, creating urgency for both parties.

**The Stakeholders:**

- **Sally's Agent** (Player 0): Represents Sally Soprano, wants to maximize compensation and secure the role
- **Business Manager** (Player 1): Represents Lyric Opera, needs to control costs while securing talent
- **LLM Judge** (Player 2): Evaluates the final deal to determine who negotiated better

### Private Information

**Sally's Agent knows:**
- Sally desperately wants the role for career comeback
- She would perform for free if necessary (professional pride aside)
- TV special opportunity worth $45,000 depends on getting this role
- Her recent salaries have ranged from $10,000-$18,000 for secondary roles
- Industry salaries have nearly doubled in recent years

**Business Manager knows:**
- Lyric Opera is in desperate need after losing their original soprano
- Company is authorized to pay up to $45,000 if absolutely necessary
- Average house needs to be 85% to break even
- Poor attendance (below 80%) would lose $50,000+
- Sally's popularity has declined somewhat from her peak

## Components

- **3 players**: Sally's Agent, Business Manager, and LLM Judge
- **Salary negotiation**: Primary focus on monetary compensation
- **Non-monetary terms**: Promotional opportunities, performance bonuses, etc.
- **Private constraints**: Hidden acceptable ranges and priorities for each party
- **Maximum rounds**: Default 60 rounds for negotiation phase
- **Judge evaluation**: LLM determines winner based on confidential instructions

## Turn Structure

1. **Negotiation Phase**: Sally's Agent and Business Manager alternate turns
2. **Proposals** use format: `[Propose] 25000` (salary amount)
3. **Acceptance** using `[Accept]` to agree to current proposal
4. **Free text discussion** for arguments and non-monetary promises
5. **Judge Phase**: After deal reached, judge evaluates who won; if no deal, it's an automatic draw

## Rules

### Making Proposals
- Format: `[Propose] 25000` (amount only, no dollar signs)
- Must be a valid number
- Can include rationale before the bracketed action
- Replaces any existing proposal on the table

### Accepting Proposals
- `[Accept]` to accept the current proposal
- Can only accept when there is an active proposal
- Cannot accept your own proposal
- Can include rationale before the bracketed action

### Free Text Discussion
- Any message without bracketed actions is treated as discussion
- Use for arguments, promises, and non-monetary terms
- No turn advancement, continues negotiation

### Invalid Moves
- Invalid moves do not advance turns (player must retry)
- Invalid formats include missing numbers, wrong brackets, etc.
- Players stay on same turn until valid move is made

## Winning Conditions

The game ends when:
- A proposal is accepted by the other party
- Maximum number of rounds is reached (automatic draw)

**Judge Evaluation:**
- Judge receives both parties' confidential instructions
- Evaluates who got better deal based on private constraints
- Uses format: `[winner] Sally's Agent | Business Manager | Draw`
- Winner gets +1 reward, loser gets -1, draw gives 0 to all

## Usage

### Action Format Examples

**Making a proposal with rationale:**
```
Given Sally's experience and the urgency of your situation, I believe $30,000 is fair compensation.
[Propose] 30000
```

**Accepting a proposal:**
```
This meets our budget constraints and secures Sally for the role.
[Accept]
```

**Free text negotiation:**
```
I'm willing to discuss performance bonuses if Sally's shows exceed 85% attendance.
```

### Example Game Flow

1. **Sally's Agent**: `I propose $30,000 given Sally's experience. [Propose] 30000`
2. **Business Manager**: `That's too high for our budget. [Propose] 25000`
3. **Sally's Agent**: `Let's meet in the middle at $27,500. [Propose] 27500`
4. **Business Manager**: `I can do $26,000 with a performance bonus. [Propose] 26000`
5. **Sally's Agent**: `The bonus structure sounds good. [Accept]`
6. **Judge**: Evaluates deal and determines winner based on private constraints

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create the environment with default settings
env = ta.make(env_id="SallySoprano-v0")

# Reset with 3 players (required)
env.reset(num_players=3)
```

### Run a Simple Game

```python
import textarena as ta

# Set up agents
agents = {
    0: ta.agents.HumanAgent(),  # Sally's Agent - human player
    1: ta.agents.HumanAgent(),  # Business Manager - human player  
    2: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-haiku-20240307-v1:0', region_name='us-west-2'),  # Judge
}

# Initialize the environment
env = ta.make(env_id="SallySoprano-v0")
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
env = ta.make(env_id="SallySoprano-v0", 
              max_rounds=30,     # Shorter negotiation
              error_allowance=5) # Allow more invalid moves
```

## LLM Agent Configuration

### Agent Setup Examples

```python
# High-performance setup
agents = {
    0: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0', region_name='us-west-2'),
    1: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0', region_name='us-west-2'),
    2: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-5-sonnet-20241022-v2:0', region_name='us-west-2'),
}

# Cost-effective setup
agents = {
    0: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-haiku-20240307-v1:0', region_name='us-west-2'),
    1: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-haiku-20240307-v1:0', region_name='us-west-2'),
    2: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-haiku-20240307-v1:0', region_name='us-west-2'),
}

# Mixed human-AI setup
agents = {
    0: ta.agents.HumanAgent(),  # Human plays Sally's Agent
    1: ta.agents.HumanAgent(),  # Human plays Business Manager
    2: ta.agents.AWSBedrockAgent(model_id='anthropic.claude-3-haiku-20240307-v1:0', region_name='us-west-2'),  # AI Judge
}
```

## Implementation Notes

### Game Mechanics

1. **Turn Management**: Only negotiating players (0, 1) count toward max_rounds
2. **Judge Observing**: Judge silently observes during negotiation phase
3. **Round Counter**: Displays `[Round X/Y]` format automatically
4. **Invalid Move Handling**: Invalid moves don't advance turns, player must retry
5. **Automatic Draw**: No deal after max rounds results in draw for all players

### Technical Features

- **Robust action parsing**: Handles various proposal formats and rationale text
- **Clean conversation flow**: Prevents redundant messages and formatting issues
- **LLM instruction compliance**: CRITICAL instructions prevent common LLM errors
- **Flexible judge evaluation**: Supports multiple decision formats with fallback parsing
- **Comprehensive testing**: 18 test cases covering all game mechanics

## Testing

Run the comprehensive test suite:

```bash
cd /path/to/TextArena
source .venv/bin/activate
python3 -m pytest textarena/envs/SallySoprano/test_env.py -v
```

The test suite includes 18 tests covering:
- Environment initialization and configuration
- Player turn management and role assignment
- Proposal and acceptance mechanics
- Invalid move handling
- Judge decision processing
- Round counter functionality
- Game ending conditions

## Files Structure

```
SallySoprano/
├── README.md                 # This documentation
├── __init__.py              # Environment registration
├── env.py                   # Main environment implementation
├── renderer.py              # Game state rendering
├── test_env.py             # Comprehensive test suite
└── offline_play.py         # Example usage script
```

## References

Jacker, N. S., & Gordon, M. N. (2018). Sally Soprano I. Program on Negotiation at Harvard Law School.