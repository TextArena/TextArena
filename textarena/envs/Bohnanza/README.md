# Bohnanza Bean Trading Game Environment

This is an implementation of the Bohnanza bean trading card game supporting 3-5 players.

## Game Description

[Bohnanza](https://boardgamegeek.com/boardgame/11/bohnanza) is a trading and set collection card game designed by Uwe Rosenberg where players plant, trade, and harvest beans to earn coins. The key twist is that players cannot rearrange their hand order - beans must be planted in the order they were received. See ruleset [here](https://www.riograndegames.com/wp-content/uploads/2013/02/Bohnanza-Rules.pdf).

### Components
- 154 bean cards of 8 different types
- Each bean type has different quantities and payout rates
- 2-3 bean fields per player (depending on player count)
- Supports 3-5 players

### Bean Types and Payouts
Each bean type has different quantities and coin payouts based on harvest size:

| Bean Type | Quantity | Payout Chart (coins for beans) |
|-----------|----------|--------------------------------|
| Blue      | 20       | 1→4, 2→6, 3→8, 4→10           |
| Chili     | 18       | 1→3, 2→6, 3→8, 4→9            |
| Stink     | 16       | 1→3, 2→5, 3→7, 4→8            |
| Green     | 14       | 1→3, 2→5, 3→6, 4→7            |
| Soy       | 12       | 1→2, 2→4, 3→6, 4→7            |
| BlackEyed | 10       | 1→2, 2→4, 3→5, 4→6            |
| Red       | 8        | 1→2, 2→3, 3→4, 4→5            |
| Garden    | 6        | 2→2, 3→3                       |

### Initial Setup
- Each player receives 5 cards in hand
- 3 players get 3 bean fields each
- 4-5 players get 2 bean fields each
- Remaining cards form the draw deck

### Turn Structure
Each turn consists of 4 phases:

1. **Plant Phase**: Plant at least 1 and up to 2 beans from hand (in order) into fields
2. **Draw & Trade Phase**: Draw 2 face-up cards, trade with other players
3. **Plant Mandatory Phase**: Plant all beans received from trades in any order
4. **Draw Phase**: Draw 3 cards to hand

### Key Rules

#### Hand Order
- **Cannot rearrange hand order** - this is the core rule!
- Must plant beans from the front of your hand
- New cards are always added to the back of your hand

#### Planting Rules
- Must plant at least 1 bean during Plant Phase
- Can plant up to 2 beans per Plant Phase
- Each field can only contain one type of bean
- Can harvest fields anytime during your turn to make space

#### Trading Rules
- Only occurs during Draw & Trade Phase
- Active player can trade face-up cards and hand cards
- Other players can only trade hand cards
- All traded beans must be planted immediately
- Can trade "Nothing" for gifts

#### Harvesting Rules
- Can harvest anytime during your turn
- Cannot harvest 1-bean field if other fields have 2+ beans
- Earn coins based on bean type and quantity
- Harvested beans go to discard pile

#### Game End
- Game ends after deck is reshuffled 3 times
- All remaining fields are harvested
- Player with most coins wins
- Ties broken by furthest clockwise from starting player

## Usage

### Action Format
Actions use bracketed commands:

**Plant Phase:**
- `[Plant] 1` - Plant first hand card in field 1
- `[Plant] 2` - Plant first hand card in field 2
- `[Harvest] 1` - Harvest field 1 for coins
- `[Pass]` - End plant phase (after planting at least 1 card)

**Draw & Trade Phase:**
- `[Trade] Blue for Red` - Offer Blue bean for Red bean
- `[Trade] 2 Blue for Red` - Offer 2 Blue beans for 1 Red bean
- `[Trade] Blue for Nothing` - Gift Blue bean
- `[Accept] Trade1` - Accept trade proposal #1
- `[EndTrading]` - End trading phase (active player only)

**Plant Mandatory Phase:**
- `[Plant] Blue 1` - Plant specific Blue bean in field 1
- `[Pass]` - Skip if no mandatory beans

**Draw Phase:**
- `[Draw]` - Draw 3 cards to hand

### Game State Display
```
=== BOHNANZA GAME ===
Turn: 5 | Phase: DRAW_TRADE | Active Player: 1 | Deck Cycles: 0/3

FACE-UP CARDS: Red, Blue

ACTIVE TRADES:
  Trade1: Player 2 offers Chili for Blue (open to all)

PLAYER 0 (You):
  Coins: 3
  Hand: [Green, Red, Blue, Soy, Chili] (5 cards)
  Field 1: Blue x3
  Field 2: Red x2
  Field 3: Empty

PLAYER 1 (Active):
  Coins: 2
  Hand: 4 cards
  Field 1: Green x1
  Field 2: Chili x4

PLAYER 2:
  Coins: 1
  Hand: 5 cards
  Field 1: Soy x2
  Field 2: Empty

MUST PLANT: Blue (from trade)
```

### Example Turn Sequence
```
Player 0's turn:
1. [Plant] 1          # Plant first hand card in field 1
2. [Pass]             # End plant phase
3. [Trade] Red for Blue  # Propose trade during draw/trade
4. [EndTrading]       # End trading phase
5. [Plant] Blue 2     # Plant mandatory Blue bean in field 2
6. [Pass]             # No more mandatory beans
7. [Draw]             # Draw 3 cards, advance to next player
```

## Implementation Notes

This implementation includes:
- Full 4-phase turn structure
- Authentic bean types and payout calculations
- Hand order enforcement (core Bohnanza mechanic)
- Turn-based trading system with open and targeted trades
- Mandatory planting of traded beans
- Harvest priority rules
- 3-deck-cycle game ending
- Proper tie-breaking rules

### Key Features
- **Hand Order Constraint**: Players cannot rearrange their hand
- **Trading Flexibility**: Support for complex multi-bean trades and gifts
- **Phase Management**: Proper turn structure with phase transitions
- **Bean Conservation**: All beans are tracked throughout the game
- **Authentic Payouts**: Uses official Bohnanza payout charts

### Testing
The environment includes a comprehensive test suite with 66 tests covering:
- All game phases and transitions
- Trading mechanics and validation
- Harvesting rules and coin calculations
- Error handling and edge cases
- Complete game flow scenarios

Run tests with:
```bash
pytest textarena/envs/Bohnanza/test_env.py -v
```