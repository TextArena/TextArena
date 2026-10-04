base_prompt = """Welcome to **Coup**!  
You are **Player #<PLAYER_ID>**. All players start with **2 coins** (in a two-player game the starting player, Player #0, gets only **1 coin**) and **2 hidden influence cards**. A standard deck has **15 cards (3 of each role)**.

---

## OBJECTIVE  
Knock every rival out of the game by stripping them of *both* influence cards.  
- **Short-term goals:** build a cash edge, sow doubt, and avoid losing influence.  
- **Medium-term goals:** reach 7 coins to threaten an unblockable **coup X** and force others into defensive play.
- **Deception is legal:** you may *claim* any role when you act or block, even if you don’t hold it. Opponents can respond with **BULLSHIT** (a *challenge*). The loser of a challenge immediately loses an influence: they choose one of their hidden cards and flip it face-up (permanently lost).

---

## INFLUENCE CARDS (roles)  

| Role | Action | Counteraction | Notes |
|------|--------|---------------|-------|
| **Duke** | **Tax** – take 3 coins (**tax**) | Blocks **foreign aid** | Pure economy  |
| **Assassin** | **Assassinate** – pay 3 coins, target loses 1 influence (**assassinate X**) | — | Blockable by Contessa |
| **Captain** | **Steal** – steal 2 coins from a target player X (**steal X**) | Blocks another Steal | Also blocked by Ambassador |
| **Ambassador** | **Exchange** – draw 2 random cards from the Court deck, choose which of your face-down cards and the drawn cards to keep (as many as your current influence), and return the rest to the Court deck (**exchange**) | Blocks Steal | Refreshes your hand |
| **Contessa** | — | Blocks **assassinate** | Purely defensive  |

---

## ACTIONS ON **YOUR** TURN  

| Type | Cost | Blockable? | Command |
|------|------|-----------|---------|
| **Income** | 0 | No | **income** |
| **Foreign Aid** | 0 | Yes (Duke) | **foreign aid** |
| **Coup** | 7 coins (you must coup someone if you have ≥ 10 coins) | No | **coup X** |
| **Tax** *(Duke)* | 0 | No | **tax** |
| **Assassinate** *(Assassin)* | 3 coins | Yes (Contessa) | **assassinate X** |
| **Steal** *(Captain)* | 0 | Yes (Captain / Ambassador) | **steal X** |
| **Exchange** *(Ambassador)* | 0 | No | **exchange** |
| **Keep Two Cards After An Exchange* | 0 | No | keep Duke Duke |

*(Replace **X** with the target player number.)* 

YOU ARE NOT ALLOWED TO PASS IF IT IS YOUR TURN. YOU MUST MAKE AN ACTION FROM THE ABOVE LIST.

---

## IF ASKED TO CHALLENGE YOU MAY RESPOND WITH:

1. BULLSHIT => challenge the last claim
2. PASS => neither block nor challenge

## YOU ARE ASKED IF YOU WOULD ALSO LIKE TO BLOCK, YOU MAY RESPOND WITH:

1. block xxx THIS IS ONLY ALLOWED IF THE LAST ACTION WAS THE ONE YOU ARE BLOCKING.
   - **block foreign aid** *(as Duke)*
   - **block steal captain** *(as Captain or Ambassador)*  NOTE: YOU MUST ALWAYS INCLUDE EITHER CAPTAIN OR AMBASSADOR IF YOU BLOCK A STEAL
   - **block assassinate** *(as Contessa)*
2. BULLSHIT => if you think the acting player is lying.
3. PASS => do nothing. YOU MAY ONLY DO THIS IF SOMEONE ELSE HAS TAKEN AN ACTION AGAINST YOU.

## IF YOU MUST LOSE AN INFLUENCE, RESPOND WITH:

You lose an influence when you are couped, successfully assassinated, or lose a challenge (whether you challenged or were challenged, on an action or on a block). You choose which hidden card to give up:

1. reveal <card> => flip that hidden card face-up; it is permanently lost (e.g. **reveal Duke**)

If you have only one hidden card left, it is revealed automatically and you are out of the game.

---

## TURN FLOW
1. **Active player chooses an ACTION** → opponents may **block …** or call **BULLSHIT**.
2. **Resolve any challenge** (the loser chooses a card to flip with **reveal <card>**; the winner, if challenged, replaces the shown card then proceeds). A successfully challenged action fails entirely and any coins paid for it are returned; a blocked action still costs its coins.
3. **If uncontested or block succeeds, apply the effect.**  
4. **Next player clockwise.**  

---

## COMMAND EXAMPLES  

income => take 1 coin
coup 3 => pay 7 coins, force Player #3 to lose 1 influence
steal 4 => attempt to do a steal from Player #4
block assassinate => claim Contessa to save yourself
block steal ambassador => block a steal by claiming to have an Ambassador
BULLSHIT => challenge the last claim
PASS => neither block nor challenge
reveal Captain => when you must lose an influence, give up your Captain

Keep your coin count and revealed cards in mind when choosing an action. Reply with exactly one command from the list above.


There are <NUM_PLAYERS> players in the game.

The current state of the game is:

<PLAYER_OBSERVATIONS>
"""


# What we give to the LLM after every turn
base_reprompt = """The current state of the game is:

<PLAYER_OBSERVATIONS>

It is now your turn.

<CALL_TO_ACTION_OR_CHALLENGE>
"""
