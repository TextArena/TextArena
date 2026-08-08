# Ultimate Texas Hold'em

A single-player poker variant where you play against the dealer in a structured betting game with multiple phases and strategic decision-making.

## Game Overview

Ultimate Texas Hold'em is a casino poker game where you compete against the dealer using standard poker hand rankings. The game features multiple betting phases, dealer qualification rules, and strategic decision-making about when and how much to bet.

## Game Rules

### Setup
- **Starting chips**: 1000
- **Ante amount**: 25 chips per round
- **Deck**: Standard 52-card deck with ranks (2-A) and suits (♠♥♦♣)
- **Max rounds**: 1000 (configurable)

### Game Phases

#### 1. PRE-ROUND
- You are dealt 2 cards (visible)
- Dealer is dealt 2 cards (hidden)
- 5 community cards are dealt (hidden)
- **Mandatory bets**: 
  - ANTE: 25 chips
  - BLIND: 25 chips

#### 2. PRE-FLOP
- **Options**:
  - `[4x]` or `[play bet 4x]`: Bet 100 chips (4x ante) - reveals first 3 community cards
  - `[check]` or `[c]`: No additional bet - reveals first 3 community cards

#### 3. FLOP
- If you bet 4x at PRE-FLOP: Only `[skip]` or `[s]` available (auto-reveals last 2 community cards)
- Otherwise, **options**:
  - `[2x]` or `[play bet 2x]`: Bet 50 chips (2x ante) - reveals last 2 community cards
  - `[check]` or `[c]`: No additional bet - reveals last 2 community cards

#### 4. RIVER
- If you made any play bet (4x or 2x): Only `[skip]` or `[s]` available (auto-proceeds to showdown)
- Otherwise, **options**:
  - `[1x]` or `[play bet 1x]`: Bet 25 chips (1x ante) - proceeds to showdown
  - `[fold]` or `[f]`: Give up hand - lose ANTE and BLIND bets

#### 5. SHOWDOWN
- All cards are revealed and evaluated
- Best 5-card hand from 7 cards (2 hole + 5 community) is determined
- Each bet type is evaluated separately according to payout rules
- Game automatically progresses to next round or ends

### Dealer Qualification

**Important Rule**: The dealer must have at least a PAIR (2 cards of same rank) to qualify, using their 2 hole cards and the 5 community cards. Dealer qualification will affect bet payouts, as will be explained later.

### Bet Evaluation & Payouts

#### ANTE BET
- **Dealer doesn't qualify**: PUSH (bet returned)
- **Dealer qualifies & you win**: 1:1 payout (bet + winnings)
- **Dealer qualifies & you lose**: Bet lost
- **Tie**: PUSH (bet returned)

#### BLIND BET
- **Unaffected by dealer qualification**
- **You win**: Bet returned + additional payout based on hand strength
- **You lose**: Bet lost
- **Tie**: PUSH (bet returned)

#### BLIND BET PAY TABLE
- **Royal Flush**: 500:1 (12,500 chips)
- **Straight Flush**: 50:1 (1,250 chips)
- **Four of a Kind**: 10:1 (250 chips)
- **Full House**: 3:1 (75 chips)
- **Flush**: 3:1 (75 chips)
- **Straight**: 1:1 (25 chips)
- **Less than Straight**: No additional payout

#### PLAY BET
- **Unaffected by dealer qualification**
- **Direct comparison**: Your best hand vs Dealer's best hand
- **You win**: 1:1 payout (bet + winnings)
- **You lose**: Bet lost
- **Tie**: PUSH (bet returned)

### Poker Hand Rankings (Best to Worst)

1. **Royal Flush**: A-K-Q-J-10 of same suit
2. **Straight Flush**: 5 consecutive cards of same suit
3. **Four of a Kind**: 4 cards of same rank
4. **Full House**: 3 of a kind + 2 of a kind
5. **Flush**: 5 cards of same suit
6. **Straight**: 5 consecutive cards
7. **Three of a Kind**: 3 cards of same rank
8. **Two Pair**: 2 pairs of different ranks
9. **One Pair**: 2 cards of same rank
10. **High Card**: Highest card wins

### Game End Conditions

- **OVERALL LOSS**: Reach 0 chips or below at the start of a round
- **OVERALL WIN**: Complete 1000 rounds with chips remaining

## Action Commands

All actions must be enclosed in square brackets:

### Primary Actions
- `[4x]` or `[play bet 4x]` - Place 4x ante PLAY bet (100 chips)
- `[2x]` or `[play bet 2x]` - Place 2x ante PLAY bet (50 chips)
- `[1x]` or `[play bet 1x]` - Place 1x ante PLAY bet (25 chips)

### Game Control
- `[check]` or `[c]` - Check (no additional bet)
- `[fold]` or `[f]` - Fold (give up hand, lose ANTE and BLIND)
- `[skip]` or `[s]` - Skip to next phase (when no action needed)

### Important Notes
- **Only ONE PLAY bet per round** - choose timing strategically
- **Folding** is only available at RIVER if no prior PLAY bet was made
- **Folding** results in losing ANTE and BLIND bets

## Strategy Tips

- **Strong starting hands** (pairs, high cards) often justify 4x bets
- **Consider dealer qualification** - weak hands may push if dealer doesn't qualify
- **BLIND bet can be very profitable** with strong hands (Royal Flush = 500:1!)
- **Watch your chip stack** - if it goes to 0 or below at start of round, you lose

## Example Game Flow

1. **PRE-ROUND**: Place 50 chips (ante + blind), receive 2 cards
2. **PRE-FLOP**: Choose `[4x]` or `[check]`
3. **FLOP**: If you checked, choose `[2x]` or `[check]`
4. **RIVER**: If you checked, choose `[1x]` or `[fold]`
5. **SHOWDOWN**: All cards revealed, bets evaluated automatically
6. **Next Round**: Start over with new cards

## Usage

```python
import textarena as ta 

agents = {
    0: ta.agents.HumanAgent()
}

# initialize the environment
env = ta.make(env_id="UltimateTexasHoldem-v0")
env.reset(num_players=len(agents))

# main game loop
done = False 
while not done:
  player_id, observation = env.get_observation()
  action = agents[player_id](observation)
  done, step_info = env.step(action=action)
rewards, game_info = env.close()
print(rewards)
print(game_info)
```

## Technical Details

- **Environment**: Single-player TextArena environment
- **State Management**: Tracks chips, rounds, phases, bets, and game completion
- **Action Parsing**: Flexible regex patterns for various action formats
- **Bet Calculation**: Separate functions for ANTE, BLIND, and PLAY bet evaluation
- **Hand Evaluation**: Standard 5-card poker hand ranking algorithms 