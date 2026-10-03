# UgliOrange Negotiation Environment

[UgliOrange](https://event.capconcorp.com/meeting/liheap/presentations/2019/Day-2-Wed-1st/GS_Skill%20Builder%20Interest%20Based%20Negotiation_Ugli%20Orange%20Scenarios%20(Handout).pdf) is a turn-based negotiation environment where two pharmaceutical researchers (Roland and Jones) negotiate over access to rare Ugli oranges, while an LLM judge evaluates whether players achieve their objectives. The scenario creates a classic win-win opportunity where both players can succeed if they discover they need different parts of the same oranges.

### Key Features

- **Three-player structure**: Two negotiating players plus an LLM judge
- **Hidden complementary needs**: Roland needs rinds, Jones needs juice from the same oranges
- **Time pressure**: Maximum 60 rounds of negotiation
- **Objective-based winning**: Players win by meeting specific resource and budget requirements
- **Comprehensive judge evaluation**: LLM judge analyzes deals using structured format

### The Scenario

**Dr. P.W. Roland** works for a pharmaceutical firm contracted by the government to neutralize leaking World War II nerve gas bombs. He needs the chemical from Ugli orange rinds to create a synthetic vapor that can neutralize the gas before it spreads and kills thousands of people. His firm has authorized him to spend up to $250,000 to obtain rinds from 3,000 oranges.

**Dr. J.W. Jones** works for a competing pharmaceutical firm and has developed a serum to cure Rudosen, a disease affecting pregnant women. The serum requires juice from Ugli oranges, and there's an active outbreak requiring treatment for thousands of women. Her firm has also authorized up to $250,000 to obtain juice from 3,000 oranges.

**The Supplier**: R.H. Cardoza, a South American fruit exporter, has exactly 3,000 Ugli oranges available and will sell to the highest bidder.

### The Hidden Win-Win Opportunity

The key insight is that Roland needs only the rinds while Jones needs only the juice from the same oranges. If they discover this complementary need, they can collaborate to purchase the oranges together and both achieve their objectives within budget.

## Components

- **2 negotiating players**: Roland (Player 0) and Jones (Player 1)
- **1 LLM judge**: Evaluates final deals and determines winners (Player 2)
- **60 maximum rounds**: Time pressure encourages efficient negotiation
- **Objective-based scoring**: Players must meet specific resource and budget requirements

## Turn Structure

1. **Roland and Jones alternate turns** making proposals, accepting deals, or engaging in free discussion
2. **Judge observes silently** during negotiation phase
3. **When a deal is reached** or maximum rounds exceeded, judge evaluates the outcome
4. **Judge provides structured analysis** of what each player gets and whether they meet objectives

## Rules

### Making Proposals
- Format: `[Propose] your proposal details`
- Can include any terms about orange purchase, cost sharing, resource allocation
- Proposals are auto-numbered for easy reference
- Can include free text discussion before the bracketed action

### Accepting Proposals
- Format: `[Accept]` to accept the latest proposal
- Only the latest proposal can be accepted (simplified from multi-proposal system)
- Cannot accept your own proposals
- Can include free text discussion before the bracketed action

### Free Discussion
- Any text without bracketed actions is treated as free discussion
- Players can negotiate, ask questions, share information, or build rapport
- Bracketed actions should always come at the end of messages

### Judge Evaluation
When a deal is reached, the judge analyzes it using this structured format:
```
Roland gets: rind or juice or all or nothing or unclear
Roland pays: dollar amount as number or 0 if none specified
Roland oranges: number of oranges or 3000 if not specified
Jones gets: rind or juice or all or nothing or unclear
Jones pays: dollar amount as number or 0 if none specified
Jones oranges: number of oranges or 3000 if not specified
```

## Winning Conditions

**Roland wins if:**
- He gets rind or all parts from the oranges
- He pays 250,000 dollars or less
- He gets 3,000 or more oranges

**Jones wins if:**
- She gets juice or all parts from the oranges  
- She pays 250,000 dollars or less
- She gets 3,000 or more oranges

**Both can win simultaneously** if the deal gives each player what they need within their constraints.

**If no deal is reached** after 60 rounds, the game ends in a draw.

## Usage

### Action Format Examples

**Making a proposal with discussion:**
```
Dr. Jones, I understand we're both facing urgent situations. Perhaps we could work together on this.
[Propose] We submit a joint bid of $200,000 for the 3,000 oranges and split the costs equally
```

**Accepting a proposal:**
```
That sounds like a reasonable compromise that could work for both our organizations.
[Accept]
```

**Free discussion:**
```
I'm curious about your specific needs. What exactly do you plan to do with the oranges?
```

### Example Game Flow

1. **Roland**: Opens with competitive proposal to buy all oranges for $200k
2. **Jones**: Counters with joint bid proposal for $225k, split costs
3. **Roland**: Asks about Jones's specific needs through discussion
4. **Jones**: Reveals she needs the juice, asks about Roland's needs
5. **Roland**: Reveals he needs the rinds, proposes collaboration
6. **Jones**: Accepts the collaborative proposal
7. **Judge**: Evaluates that both get what they need within budget - both win

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create the environment
env = ta.make(env_id="UgliOrange-v0")

# Reset with 3 players (Roland, Jones, Judge)
env.reset(num_players=3)
```

### Run a Simple Game

```python
import textarena as ta

# Set up agents
agents = {
    0: ta.agents.HumanAgent(),  # Roland - human player
    1: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Jones - LLM
    2: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Judge - LLM
}

# Initialize the environment
env = ta.make(env_id="UgliOrange-v0")
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
env = ta.make(env_id="UgliOrange-v0", 
              max_rounds=30,        # Shorter negotiation
              error_allowance=5)    # More lenient error handling
```

## Implementation Notes

### Key Design Decisions

1. **Simplified Accept Logic**: Only the latest proposal can be accepted, eliminating confusion about proposal numbers
2. **Comprehensive Judge Evaluation**: Single structured evaluation replaces sequential questioning for better LLM performance  
3. **Default Orange Counts**: When not specified, assumes 3000 oranges (minimum needed) rather than 0
4. **LLM-Friendly Format**: Removed special characters and complex formatting to improve LLM parsing
5. **Flexible Proposal Format**: Accepts various proposal formats including numbered variations

## Testing

Run the test suite to verify the environment works correctly:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
cd textarena/envs/UgliOrange
python3 test_env.py
```

The test suite validates:
- Proposal creation and acceptance
- Judge evaluation with structured format
- Win/loss condition logic
- Error handling for invalid actions
- Default value handling

## References

Fisher, R., Ury, W., & Patton, B. (2011). Getting to yes: Negotiating agreement without giving in (3rd ed.). Penguin Books.