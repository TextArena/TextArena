# VendorNegotiation Environment

## Overview
**VendorNegotiation** is a two-player negotiation game where a Brand Specialist negotiates with a Vendor over discount rates for products in an upcoming sales event. Both players can win by achieving their respective objectives through cooperative-competitive dynamics.

## Action Space
- **Format:** Actions are strings with optional conversation before bracketed commands:
  - `[Propose] X%, Y%, Z%, ...` - Propose discount rates (positional format)
  - `[Accept]` - Accept current proposal
  - `[Reject]` - Reject current proposal
  - Free text conversation (no brackets)
- **Example:**
  - `"I think moderate discounts work well [Propose] 20%, 15%, 20%, 20%, 15%"`
  - `"This looks reasonable to me [Accept]"`
  - `"Hello, let's discuss the discount rates"`

## Observation Space

### Player Roles
- **Player 0 (Brand Specialist)**: Sees sales data, wants to achieve target sales
- **Player 1 (Vendor)**: Sees sales + profit data, wants to beat baseline profit

### Initial Observation
```plaintext
ROLE: Brand Specialist at E-commerce Platform
OBJECTIVE: Achieve total sales ≥ $130,200 (715% of maximum possible)

NEGOTIATION STYLE: Balanced
[Role-specific instructions]

PRODUCTS & SALES DATA:
Gaming_Mouse ($60/unit):
  0%: 200 units (±20) → $12,000 sales (±$1,200)
  15%: 280 units (±28) → $15,960 sales (±$1,596)
  20%: 400 units (±40) → $21,600 sales (±$2,160)
  30%: 600 units (±60) → $28,800 sales (±$2,880)

PRODUCT ORDER: Gaming_Mouse, Premium_Laptop, USB_Hub, Power_Bank, Phone_Charger

ACTIONS:
[Propose] X%, Y%, Z%, ... (follow product order above)
[Accept]
[Reject]
```

### Turn Observation
```plaintext
ROUND 3/20

CURRENT PROPOSAL:
Gaming_Mouse:20%, Premium_Laptop:20%, USB_Hub:30%, Power_Bank:20%, Phone_Charger:30%
Proposed by: Player 0

PROPOSAL ANALYSIS (estimated using means ± variance):
Expected Profit: $70,960 - BEATS BASELINE
Your Baseline: $44,600

RECENT CONVERSATION:
Player 0: I think moderate discounts work well
Player 1: This looks reasonable to me

RECENT HISTORY:
R2: Player 0 proposed Gaming_Mouse:20%, Premium_Laptop:20%, ...
```

## Gameplay
- **Players**: 2 (Brand Specialist vs Vendor)
- **Turns**: 20 maximum rounds
- **Product Selection**: 5 random products per game
- **Information Asymmetry**: Brand sees sales data, Vendor sees sales + profit data
- **Win Conditions**: Both players can win by achieving their objectives

## Key Rules
1. **Proposal Format**: Must specify discount for all products in order
2. **Allowed Discounts**: 0%, 15%, 20%, 30%
3. **Conversation**: Free text allowed, captured before bracketed actions
4. **Error Allowance**: 3 invalid moves before penalty

## Rewards
| Outcome                    | Brand Specialist | Vendor |
|----------------------------|:----------------:|:------:|
| **Both achieve objectives** | `0` (draw)      | `0`    |
| **Only Brand achieves**     | `+1`            | `-1`   |
| **Only Vendor achieves**    | `-1`            | `+1`   |
| **Neither achieves**        | `0` (draw)      | `0`    |

## Parameters
- `num_products` (`int`): Number of products to negotiate (default: 5)
- `max_rounds` (`int`): Maximum negotiation rounds (default: 20)
- `brand_target_percentage` (`float`): Brand Specialist's target as % of max sales (default: 0.8)
- `vendor_baseline_multiplier` (`float`): Vendor's target as times of their profit at 0% discount (default: 1.2)
- `num_simulations` (`int`): Monte Carlo simulation runs (default: 1000)
- `brand_role` (`str`): Brand Specialist negotiation style (default: "default")
- `vendor_role` (`str`): Vendor negotiation style (default: "default")

## Variants

| Env-id                          | num_products | max_rounds | num_simulations |
|---------------------------------|:------------:|:----------:|:---------------:|
| `VendorNegotiation-v0`          | `5`          | `20`       | `1000`          |
| `VendorNegotiation-v0-lite`    | `3`          | `10`       | `1000`          |
| `VendorNegotiation-v0-heavy`  | `8`          | `30`       | `1000`          |

## Role Customization

### Brand Roles
- `default` - Balanced negotiator
- `aggressive` - Push for maximum discounts
- `collaborative` - Win-win focused
- `data_driven` - Heavy statistics use

### Vendor Roles
- `default` - Balanced negotiator
- `profit_focused` - Maximize margins
- `volume_seeker` - Flexible on discounts
- `relationship_builder` - Long-term partnership focus

## Testing
Run comprehensive tests:
```bash
python textarena/envs/VendorNegotiation/test_env.py
```
