# ScorableGames Negotiation Environment

This is an implementation of a multi-player negotiation game based on the "Scorable Games" framework originally developed by [L. E. Susskind (1985)](https://web.mit.edu/publicdisputes/teach/scorablegames.pdf) and later adapted by [LLM-Deliberation](https://arxiv.org/pdf/2309.17234). The game simulates complex multi-stakeholder negotiations where players have private scoring functions and must reach consensus on multiple interconnected issues.

## Game Description

ScorableGames is a turn-based negotiation environment where multiple players (typically 6-7) represent different stakeholders negotiating over several issues. Each player has private preferences (point values) for different options, creating realistic scenarios where players must balance their own interests while finding mutually acceptable solutions.

### Key Features

- **Multi-issue negotiation**: Players negotiate simultaneously over 5 interconnected issues
- **Private scoring functions**: Each player has hidden preferences and minimum acceptable scores
- **Flexible voting rules**: Configurable acceptance thresholds and veto powers
- **Unanimity bonuses**: Special rewards for achieving full consensus
- **Rich rationale system**: Players can provide reasoning for their proposals and votes

### Default Game Scenario (Base Configuration)

The default scenario involves "SportCo" seeking to build a "Harbour Sport Park" in England. The stakeholders include:

- **SportCo** (Player 1 - Veto Power): The company proposing the project
- **Department of Tourism** (Player 2 - Veto Power): Government funding agency
- **Environmental League**: Environmental advocacy group
- **Local Labour Union**: Represents local workers
- **Mayor**: Local government representative
- **Other Cities**: Competing regional interests

### Issues and Options

**Issue A: Infrastructure Mix** (3 options)
- A1 "water-based": New buildings freely built on water with artificial islands
- A2 "water/land-based": Limited water-based buildings
- A3 "land-based": Facilities built primarily on existing land

**Issue B: Ecological Impact** (3 options)
- B1 "some damage": Permanent damage within federal guidelines
- B2 "maintain balance": Special precautions to maintain wildlife populations
- B3 "improve": Include efforts to improve the environment

**Issue C: Employment Rules** (4 options)
- C1 "unlimited union preference": Jobs reserved for Local Labour Union
- C2 "union quota of 2:1": 2:1 ratio favoring union members
- C3 "union quota of 1:1": Equal ratio of union to non-union workers
- C4 "no union preference": No special quotas for union members

**Issue D: Federal Loan** (4 options)
- D1 "$3 billion": SportCo receives $3 billion federal loan
- D2 "$2 billion": SportCo receives $2 billion federal loan
- D3 "$1 billion": SportCo receives $1 billion federal loan
- D4 "no federal loan": SportCo receives no federal loan

**Issue E: Compensation to Other Cities** (5 options)
- E1 "$600 million": SportCo pays $600 million to other cities
- E2 "$450 million": SportCo pays $450 million to other cities
- E3 "$300 million": SportCo pays $300 million to other cities
- E4 "$150 million": SportCo pays $150 million to other cities
- E5 "no compensation": SportCo pays no compensation to other cities

## Components

- **6 players** (default): Each representing a different stakeholder
- **5 negotiation issues** with 3-5 options each
- **Private scoring functions**: Hidden point values for each option per player
- **Minimum acceptable scores**: Each player has a threshold they must meet
- **Configurable voting rules**: Default requires 5/6 acceptance with P1/P2 veto power
- **Maximum rounds**: Default 120 rounds with error allowance of 3 invalid moves per player

## Turn Structure

1. Players take turns making proposals or voting on existing proposals
2. **Proposals** must cover all 5 issues using `Propose A1 B2 C3 D1 E4`
3. **Voting** uses `Accept` or `Reject`
4. Players can include rationale before the command line
5. Game continues until a proposal is accepted or maximum rounds reached

## Rules

### Making Proposals
- Format: `Propose A1 B2 C3 D1 E4` (one option for each issue A-E)
- Must cover all issues with valid options
- Put optional rationale before the command, which must start its own line
- If identical to current proposal, treated as acceptance

### Voting
- `Accept` to accept the current proposal
- `Reject` to reject the current proposal
- Can only vote when there is an active proposal
- Put optional rationale before the command line

### Voting Rules (Configurable)
- **Default**: Requires 5 out of 6 players to accept
- **Veto Power**: Both P1 (SportCo) and P2 (Department of Tourism) must accept
- **Unanimity Bonus**: P1 gets +10 points if all players accept

### Invalid Moves
- Players have 3 invalid moves allowed before automatic default action
- Invalid moves include incorrect formats, missing keywords, or incomplete proposals
- Default action is `Accept` (configurable)

## Winning Conditions

The game ends when:
- A proposal is accepted according to voting rules
- Maximum number of rounds is reached

**Scoring:**
- Players receive points based on their private scoring functions
- Must meet minimum acceptable score thresholds
- Winner is the player with highest score among those meeting their threshold
- If no deal reached, all players receive their minimum acceptable scores

## Usage

### Action Format Examples

**Making a proposal with rationale:**
```
I believe this proposal balances economic growth with environmental protection.
Propose A2 B2 C3 D2 E3
```

**Accepting a proposal:**
```
This meets our environmental standards and provides fair compensation.
Accept
```

**Rejecting a proposal:**
```
The ecological impact is too severe for our constituents to accept.
Reject
```

### Example Game Flow

1. **SportCo** proposes: `Propose A1 B1 C4 D1 E5`
2. **Environmental League** rejects with rationale followed by `Reject` on its own line
3. **Department of Tourism** proposes: `Propose A2 B2 C3 D2 E3`
4. **Mayor** submits `Accept`
5. **Local Labour Union** submits `Accept`
6. **Other Cities** submits `Accept`
7. **Environmental League** submits `Accept`
8. **SportCo** submits `Accept`
9. Game ends - deal accepted with unanimity bonus for SportCo

## Quick Start Guide

### Initialize the Environment

```python
import textarena as ta

# Create the environment with default settings
env = ta.make(env_id="ScorableGames-v0")

# Reset with 6 players (base game)
env.reset(num_players=6)
```

### Run a Simple Game

```python
import textarena as ta

# Set up agents
agents = {
    0: ta.agents.HumanAgent(),  # SportCo - human player
    1: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Department of Tourism
    2: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Environmental League
    3: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Local Labour Union
    4: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Mayor
    5: ta.agents.OpenRouterAgent(model_name="your-model-name"),  # Other Cities
}

# Initialize the environment
env = ta.make(env_id="ScorableGames-v0")
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
env = ta.make(env_id="ScorableGames-v0", 
              game_config="game1",           # Use different scenario
              max_rounds=50,                 # Shorter game
              required_votes=4,              # Need 4 accepts instead of 5
              veto_roles=["p1"],            # Only P1 has veto power
              unanimity_bonus_role="p2",     # P2 gets unanimity bonus
              starting_role="p2",            # P2 starts the game
              invalid_move_default="Reject",   # Default to reject
              error_allowance=5)             # Allow 5 invalid moves
```

## Creating Custom Game Descriptions

You can create your own negotiation scenarios by adding new game configurations in the `games_descriptions/` directory. Each game configuration requires:

### Directory Structure
```
games_descriptions/
└── your_game_name/
    ├── global_instructions.txt
    ├── config.txt
    ├── scores_files/
    │   ├── player1.txt
    │   ├── player2.txt
    │   └── ...
    └── individual_instructions/
        └── cooperative/  (or greedy, targeted_adv, etc.)
            ├── player1.txt
            ├── player2.txt
            └── ...
```

### File Templates

**global_instructions.txt** - Describes the scenario and all issues. Keep the comma formatting.

```
"Company X" is negotiating with stakeholders about a new project.

The parties are: "Company X", "Government Agency", "Community Group".

Issue A: "Budget Allocation"
A1 "high budget": $10 million allocated
A2 "medium budget": $5 million allocated  
A3 "low budget": $2 million allocated

================

Issue B: "Timeline"
B1 "fast": 6 months completion
B2 "normal": 12 months completion
B3 "slow": 18 months completion

================
```

**config.txt** - Defines players and their roles:
```
Company X,company,p1,cooperative,gpt-4
Government Agency,government,p2,cooperative,gpt-4
Community Group,community,player,cooperative,gpt-4
```

Format: `agent_name,file_name,role,incentive_type,model`

**scores_files/player.txt** - Private scoring for each player:
```
10, 5, 0
0, 5, 10
25
```

Format: One line per issue with comma-separated scores, last line is minimum threshold.

**individual_instructions/cooperative/player.txt** - Personal instructions:
```
You represent Company X.

Your preferences:
- Issue A: You prefer higher budgets (#A1_NUM points for A1)
- Issue B: You prefer faster timelines (#B1_NUM points for B1)

Your minimum acceptable score is #THRESHOLD points.
```

Use placeholders like `#A1_NUM`, `#A_MAX_NUM`, `#THRESHOLD` which get replaced with actual values.

### Available Game Configurations

- **base**: Default 6-player SportCo scenario
- **base_7players**: 7-player version with heritage stakeholder
- **base_rewritten**: Alternative 6-player version
- **game1**: Construction/tourism scenario
- **game2**: International development project
- **game3**: Nuclear facility negotiation

## Implementation Notes

### Differences from LLM-Deliberation Version

This TextArena adaptation includes several modifications for better game flow:

1. **No incentive roles**: Instead of greedy/cooperative personality types, all players default to minimum acceptable scores if no deal is reached
2. **No initial deal**: Games start with no proposal on the table
3. **No final offer mechanism**: When max turns reached, game ends immediately
4. **No scratch pad**: Players handle their own planning and note-taking

### Technical Features

- **Robust action parsing**: Handles rationale text, multiple keywords, and formatting variations
- **Flexible voting systems**: Configurable acceptance thresholds and veto powers
- **Error handling**: Graceful handling of invalid actions with escalation system
- **Rich observations**: Players see current deals, voting status, and their private scores
- **History tracking**: Complete record of all proposals and votes with rationales

## References

- Susskind, L. E. (1985). Scorable games: A better way to teach negotiation. *Negotiation Journal*, 1(3), 205-210. [PDF](https://web.mit.edu/publicdisputes/teach/scorablegames.pdf)

- Abdelnabi, S., Gomaa, A., Sivaprasad, S., Schönherr, L., & Fritz, M. (2024). Cooperation, competition, and maliciousness: Llm-stakeholders interactive negotiation. Advances in Neural Information Processing Systems, 37, 83548-83599. [PDF](https://proceedings.neurips.cc/paper_files/paper/2024/file/984dd3db213db2d1454a163b65b84d08-Paper-Datasets_and_Benchmarks_Track.pdf)