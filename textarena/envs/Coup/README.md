# Coup

## Rules:


[PDF](https://www.qugs.org/rules/r131357.pdf)
[Video](https://www.youtube.com/watch?v=xUNWl5fWfEY)


## keep this open WHILE you're reading:

The cheatsheet is useful to have on you while going through the code, as much is structured to match as much as possible.
https://hexagamers.com/wp-content/uploads/2016/04/Coup-Cheat-Sheet.jpg



## Known Issues:
  - [ ] There is a weird bug in offline play where a single LLM will all of a sudden play an entire game and then ends before the board advances even once? The reply from the LLM seems to have a word barf of an entire game being played. I can't reliably recreate it or debug, so I am hoping someone else reading this can.
  - [ ] See `QueryForReveal` TODO below.


## Environment Structure:

The `CoupEnv` class is primarily understandable by first breaking down the game into four game phases:

 - `Play`: a player plays an initial action (ex: Income, Foreign Aid, etc...)

 - `QueryForBlockOrChallenge`: if an action is blockable or challengeable, we ask players (in order) if they wish to block or challenge. For blockable actions like foreign aid, all players get asked. For targeted actions (steal/assassinate), the target gets asked first, then other players can challenge.

 - `QueryToChallengeTheBlocker`: if someone claims to block an action, query all players if they wish to challenge that block claim.

 - `QueryWhichToKeep`: this is a special case, if an exchange is happening, we can't skip immediately to the `Play` phase because the play phase happens once per player per turn, we must first go to an intermediate "QUERY FOR KEEP" phase which asks the player which card(s) they wish to keep  

#### `TODO` for Influence Loss: In Coup, when you lose an influence or someone successfully calls bullshit, you must choose a card to reveal. **Currently, this is not implemented** - the system automatically reveals the last card in the player's hand. This simplification doesn't significantly affect gameplay. If we wanted full fidelity, we'd add a `QueryForReveal` phase to let players choose which card to flip over.


The logic for each phase is executed by the branch in `step()` function, which goes to one of these update methods:
- `_update_action_metadata_for_play_phase()`: Handles initial actions like Income, Tax, Coup, etc.
- `_update_action_metadata_for_query_for_block_or_challenge_phase()`: Processes block attempts and bullshit calls
- `_update_action_metadata_for_query_to_challenge_the_blocker_phase()`: Handles challenges to block claims
- `_update_action_metadata_for_query_which_to_keep_phase()`: Manages card selection after Exchange


## Actions:

In the cheatsheet above you'll notice there are actions and counteractions. Actions are things like Income, Tax, Coup, Assassinate. Counteractions are essentially blocks to actions.

In the code we don't disambiguate between them, they're all the same, just different cases in the `CoupActionType` enum:
- **Core Actions**: Income, ForeignAid, Tax, Steal, Assassinate, Exchange, Coup
- **Block Actions**: BlockForeignAid, BlockStealAmbassador, BlockStealCaptain, BlockAssassinate  
- **Meta Actions**: BULLSHIT (challenge a claim), PASS (decline to block/challenge), Keep (select cards after Exchange)

### Note on Special Ambassador Logic:

Playing an Ambassador needs two LLM calls, or two `CoupActionType`'s. So the way we do it is as follows:

 - Turn 1: Player is in `Play` phase and does an `Exchange` action. We switch to `QueryForBlockOrChallenge` phase, allowing players to challenge.
 - Turn 2: If no one challenges, the player draws 2 cards and we switch to `QueryWhichToKeep` phase. The player must use the `Keep` action to specify which cards to keep.
 - After keeping cards, we return the non-kept cards to the pile, shuffle, and switch back to `Play` phase with the next player. 




## `env.py` file:


The file is split into five logical blocks of functions:


### Block 1: Core Environment Methods

 - `__init__()`: Standard constructor
 - `reset()`: Initializes game state, shuffles deck, deals cards to players
 - `get_board_str()`: Returns the rendered board state
 - `step()`: Main game loop - routes to appropriate phase handler based on current game phase

### Block 2: Action Metadata Update Methods

These methods validate and update game state based on player actions in each phase:

 - `_update_action_metadata_for_play_phase()`: Handles initial player actions (Income, Tax, Coup, etc.)
 - `_update_action_metadata_for_query_for_block_or_challenge_phase()`: Processes PASS, BULLSHIT, or block actions
 - `_update_action_metadata_for_query_to_challenge_the_blocker_phase()`: Handles challenges to block claims
 - `_update_action_metadata_for_query_which_to_keep_phase()`: Manages card selection after Exchange

### Block 3: Action Execution Methods

These are the "sink" functions that execute actions after all blocking/challenging is resolved:

 - `_execute_current_action()`: Executes the main action (Income, Tax, Steal, etc.)
 - `_execute_showdown_on_bullshit()`: Resolves challenges to main actions
 - `_execute_showdown_on_blocker_bullshit()`: Resolves challenges to block claims
 - `_execute_exchange_action()`: Completes the Exchange action after cards are chosen
 - `_broadcast_observations()`: Sends messages to multiple players

### Block 4: Prompt Generation and Game Flow

 - `_gen_initial_prompt()`: Creates the initial game prompt for each player
 - `_make_last_action_msg()`: Generates message about the last action taken
 - `_make_player_observations_prompt()`: Shows player their cards, coins, and game state
 - `_send_call_to_action_prompt()`: Prompts current player for their action
 - `_action_to_card()`: Maps actions to their required cards
 - `_make_player_lose_a_card()`: Removes a card from player's hand when they lose influence
 - `_advance_turn()`: Manages turn progression between players and phases
 - `_get_winner()`: Checks if only one player remains

### Block 5: Parsing and Rendering

 - `_parse_action()`: Converts player text input into CoupActionType enum values
 - `_render_board()`: Creates a colorful ASCII representation of the game state


# Limitations:

 - Players don't choose which card to reveal when they lose an influence - we automatically reveal the last card in their hand (see: `_make_player_lose_a_card()`)
 - In real life, people can challenge at any time, including BEFORE a potentially affected player gets the chance to counteract. We enforce a strict order: affected players get first chance to block, then all players can challenge


# Tasklist: 

  - [X] Implement Exchange action logic
  - [ ] Maybe remove the coins_remaining state variable?

# Things Tested:
  - [X] exchange and keep end-to-end
  - [ ] forces a coup when coins >=10
  - [X] you still lose your coins if your assassination is blocked
  - [X] fake block an assassination with 2 cards remaining (double hit, insta-eliminate)
  - [X] fake block an assassination with 1 cards remaining (double hit, but shouldn't crash)
  - [X] incorrect block (`block foreign aid` when last played was a `tax`)
  - [X] two players end-to-end
  - [X] three players end-to-end
  - [X] four players end-to-end
  - [X] five players end-to-end
  - [X] six players end-to-end
  - [X] invalid steal target player (`steal 7`)
  - [X] target player on a steal doesn't have enough coins
  - [X] invalid coup
  - [X] recovery from invalid move