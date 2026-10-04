# NewRecruit Negotiation Environment

This is an implementation of a 2-player negotiation game simulating a job negotiation between a recruiter and a candidate, with reference to the version available on [MIT Open Courseware](https://ocw.mit.edu/courses/15-668-people-and-organizations-fall-2010/6a0dea19984ff5548ea5f3197c3667ad_MIT15_668F10_lec15.pdf).

## Game Description

NewRecruit is a turn-based negotiation game where players take on the roles of a recruiter and a candidate negotiating over 8 different issues related to a job offer. Each player has different preferences (point values) for each choice, creating a realistic negotiation scenario where players must find a mutually beneficial agreement.

### Issues and Categories

The game includes 8 negotiation issues across three categories:

**Distributive Issues** (competing interests):
- Salary: $60,000 to $52,000
- Signing Bonus: 10% to 2%

**Compatible Issues** (shared interests):
- Job Assignment: Division A to Division E
- Company Car: LUX EX2 to PALO LSR

**Integrative Issues** (trade-off opportunities):
- Starting Date: Jun 1 to Aug 1
- Vacation Days: 30 days to 10 days
- Moving Expense Reimbursement: 100% to 60%
- Insurance Coverage: Allen Insurance to Insure Alba

Each issue has 5 possible choices (labeled A through E), and each choice has different point values for each player. Players can only see their own point values, not their opponent's.

## Components

- 2 players: Recruiter (Player 0) and Candidate (Player 1)
- 8 negotiation issues with 5 choices each (A-E)
- Different point values for each choice per player
- Maximum number of turns (default: 10)
- Error allowance for invalid moves (default: 3)

## Turn Structure

1. Players take turns making proposals or responding to proposals
2. A proposal consists of 8 letters (A-E), one for each issue
3. When a proposal is made, the other player can either:
   - Accept the proposal, ending the game
   - Reject the proposal, allowing negotiation to continue
4. Players can include a rationale with their proposals to persuade the other player

## Rules

### Making Proposals
- Proposals must use `Propose XXXXXXXX`, where each X is a letter A-E.
- Each letter corresponds to a choice for an issue (in order)
- Players can include a rationale before the proposal to persuade the other player

### Accepting/Rejecting
- To accept a proposal: `Accept`
- To reject a proposal: `Reject`
- Players can only accept or reject when there is a current proposal

### Invalid Moves
- Players have a limited number of invalid moves allowed (default: 3)
- Exceeding the error allowance results in losing the game
- Invalid moves include:
  - Incorrect proposal format
  - Using letters outside A-E
  - Missing an `Accept`, `Reject`, or `Propose` keyword
  - Accepting/rejecting when there is no proposal

## Winning Conditions

- The game ends when:
  - A proposal is accepted
  - The maximum number of turns is reached
  - A player exceeds the error allowance

- Scoring:
  - When a proposal is accepted, each player receives points based on their preferences
  - The player with the higher total score wins
  - If scores are equal, the game ends in a draw
  - If no proposal is accepted before the turn limit, both players receive 0 points

## Usage

### Action Format Examples

**Making a proposal:**
```
Propose ABCDEABC
```

**Accepting a proposal:**
```
Accept
```

**Rejecting a proposal:**
```
Reject
```

### Example Game Flow

1. Player 0 (Recruiter) makes a proposal: `Propose ABCDEABC`
2. Player 1 (Candidate) rejects: `Reject`
3. Player 1 makes a counter-proposal: `Propose EDCBAABC`
4. Player 0 rejects: `Reject`
5. Player 0 makes another proposal: `Propose BCDEAABC`
6. Player 1 accepts: `Accept`
7. Game ends, scores are calculated, and a winner is determined

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create the environment
env = ta.make(env_id="NewRecruit-v0")

# Reset with 2 players
env.reset(num_players=2)
```

### Run a Simple Game

```python
import textarena as ta
import os

# Set up agents
agents = {
    0: ta.agents.HumanAgent(),  # Recruiter - human player
    1: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Candidate - llm player
}

# Initialize the environment
env = ta.make(env_id="NewRecruit-v0")
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

## Implementation Notes

The current implementation includes:
- Full negotiation mechanics with proposals, acceptance, and rejection
- Different point values for each player
- Support for including rationale with proposals
- Turn limit and error allowance
- Comprehensive test suite

Future enhancements could include:
- Randomized and/or dynamic point values
- Support for more than 2 players
- Additional negotiation issues
- Time pressure mechanics
- Different negotiation scenarios beyond job recruitment

## Reference 
- Neale M. A. 1997. New recruit. Evanston, IL: Northwestern University, Kellogg School of Management, Dispute Resolution Research Center.
- Massachusetts Institute of Technology, OpenCourseWare. 2010. New Recruit Negotiations. MIT OpenCourseWare, 15.668 People and Organizations, Fall 2010. Available at: https://ocw.mit.edu/courses/15-668-people-and-organizations-fall-2010/6a0dea19984ff5548ea5f3197c3667ad_MIT15_668F10_lec15.pdf