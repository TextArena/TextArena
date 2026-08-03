import re, random
from typing import Optional, Dict, Any, List, Tuple, Union
from textarena.envs.Coup.coup_types import CoupActionType, GamePhase, ActionMetadata

import textarena as ta
from textarena.envs.Coup import base_coup_prompts

from rich.text import Text




class CoupEnv(ta.Env):
    """
    A minimal text-based implementation of the Coup card game using textarena.

    Example actions a player might enter:
      - [<action> <target_player_id> ]
      - [PASS]                 -> The player makes an action.
      - [BULLSHIT]             -> The player challenges the last play.
      - [block foreign aid]    -> The player counteracts the last play.
    """

    

    def __init__(self):
        super().__init__()

    def reset(self, num_players: int, seed: Optional[int] = None) -> None:
        """ Reset the environment for a new Coup game """
        self.state = ta.State(num_players=num_players, min_players=2, max_players=6)
        self.state.error_allowance = 3

        # Create deck with three of each card
        deck = ["Duke", "Assassin", "Ambassador", "Captain", "Contessa"] * 3
        random.shuffle(deck)

        # Initialize game state
        game_state = {
            "phase": GamePhase.Play,

            "hidden_hand": {},  # The cards each player has in their hand
            "revealed_hand": {},  # The cards each player has revealed/lost
            "pile": [],  # The cards in the pile in the middle
            
            "coins": {pid: 2 for pid in range(num_players)},  # Each player starts with 2 coins
            "treasury_coins": 50 - 2*num_players, # Max 50 coins in the pot, minus the coins each player starts with

            "action_metadata": None, # The metadata about the current action that is being taken (can span multiple "turns")
        }

        # Deal two cards to each player
        for player_id in range(num_players):
            game_state["hidden_hand"].setdefault(player_id, [])
            game_state["revealed_hand"].setdefault(player_id, [])
            game_state["hidden_hand"][player_id].append(deck.pop())
            game_state["hidden_hand"][player_id].append(deck.pop())

        # Pile has whatever is left in the deck
        game_state["pile"] = deck
        
        # Add the rendered board to the game state
        game_state["rendered_board"] = self._render_board(game_state)
        
        # Initialize textarena state
        self.state.reset(seed=seed, game_state=game_state, player_prompt_function=self._gen_initial_prompt)

        # Always start with player 0
        self.state.manually_update_current_player(new_player_id=0)
        self._send_call_to_action_prompt()
            
    
    def get_board_str(self):
        return self.state.game_state["rendered_board"]

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """ Process a single step/action from the current player """
        # Log the player's raw input by sending the action_str to player with id -1
        self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=action, for_logging=True)

        # Start with the assumption that we can move to the next player. (is set to True if we detect an invalid move)
        self.state.prevent_player_change = False

        # Game phase is either in play (a player is doing an initial action like income, foreign aid, etc)
        # or challenge (we are querying one or more players about a potential counteraction)
        try:

            action_type, other_stuff = self._parse_action(action)
            if self.state.game_state["phase"] == GamePhase.Play:
                self._update_action_metadata_for_play_phase(action_type, other_stuff)  # other stuff here is the target player id
            elif self.state.game_state["phase"] == GamePhase.QueryForBlockOrChallenge:
                self._update_action_metadata_for_query_for_block_or_challenge_phase(action_type)
            elif self.state.game_state["phase"] == GamePhase.QueryToChallengeTheBlocker:
                self._update_action_metadata_for_query_to_challenge_the_blocker_phase(action_type)
            elif self.state.game_state["phase"] == GamePhase.QueryWhichToKeep:
                self._update_action_metadata_for_query_which_to_keep_phase(action_type, other_stuff)
            else:
                raise Exception(f"Unexpected game phase: {self.state.game_state['phase']}")

            
            if self.state.prevent_player_change:
                return False, {"reason": "Invalid move"}
            
            adv_turn = self._advance_turn()

            # Render after we've updated the action metadata and advanced the turn
            self.state.game_state["rendered_board"] = self._render_board()
            
            # This tells the current player it's their turn and asks them what they want to do.
            if not adv_turn[0]:  # Game not over
                self._send_call_to_action_prompt()

            return adv_turn
        except ValueError as e:
            self.state.set_invalid_move(player_id=self.state.current_player_id, reason=str(e))
            return False, {"reason":str(e)}

        
    def _update_action_metadata_for_play_phase(self, action_type: CoupActionType, action_target_player_id: Optional[int] = None):
        """
        This validates state and updates state as needed. NOTE THAT ONLY ALLOWABLE ACTIONS HERE ARE THE ONES FROM THE OFFICIAL CHEATSHEET "ACTION" COLUMN (see README.md)
        """
        if self.state.game_state["coins"][self.state.current_player_id] >= 10 and action_type is not CoupActionType.Coup:
            self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot do anything other than coup when you have 10 or more coins. Please pick a player id to Coup and respond with: [coup x].")
            return
        if action_type is CoupActionType.Income:
            self.state.game_state["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=self.state.current_player_id, target_player_id=action_target_player_id)
            self._execute_current_action()
        elif action_type is CoupActionType.Coup:
            if self.state.game_state["coins"][self.state.current_player_id] < 7:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You don't have enough coins to coup.")
                return
            if self.state.game_state["hidden_hand"][action_target_player_id] == []:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. Can't coup player {action_target_player_id} because they are already eliminated from play.")
                return
            
            self.state.game_state["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=self.state.current_player_id, target_player_id=action_target_player_id)
            self._execute_current_action()

        elif action_type is CoupActionType.Exchange or action_type is CoupActionType.Tax:  # Exchange and Tax are not blockable, so we just skip to QueryForBlockOrChallenge phase
            self.state.game_state["phase"] = GamePhase.QueryForBlockOrChallenge
            active_players = [pid for pid in range(self.state.num_players) if len(self.state.game_state["hidden_hand"][pid]) > 0 and pid != self.state.current_player_id]
            self.state.game_state["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=self.state.current_player_id, players_to_query=active_players)
        
        elif action_type is CoupActionType.ForeignAid or action_type is CoupActionType.Assassinate or action_type is CoupActionType.Steal:
            if action_type is CoupActionType.Assassinate and self.state.game_state["coins"][self.state.current_player_id] < 3:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You don't have enough coins to assassinate.")
                return
            if action_type is CoupActionType.Steal and action_target_player_id is not None and action_target_player_id == self.state.current_player_id:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot steal from yourself, the second value in the [steal x] response must be a valid player id.")
                return
            if action_type is CoupActionType.Steal and action_target_player_id is None and action_target_player_id >= self.state.num_players:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. The second value in the [steal x] response must be a valid player id.")
                return
            if action_type is CoupActionType.Steal and self.state.game_state["coins"][action_target_player_id] < 2:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. Player {action_target_player_id} doesn't have enough coins to steal from.")
                return
            if action_type is CoupActionType.Steal and self.state.game_state["hidden_hand"][action_target_player_id] == []:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot steal from Player {action_target_player_id} because they are already eliminated from play.")
                return

            # For assassination, deduct the cost immediately (per rules, you pay even if blocked)
            if action_type is CoupActionType.Assassinate:
                self.state.game_state["coins"][self.state.current_player_id] -= 3
                self.state.game_state["treasury_coins"] += 3

            self.state.game_state["phase"] = GamePhase.QueryForBlockOrChallenge
            # Only query active players (those with cards remaining)
            active_players = [pid for pid in range(self.state.num_players) if len(self.state.game_state["hidden_hand"][pid]) > 0 and pid != self.state.current_player_id]
            # For targeted actions, ensure target is first in query list if they're active
            if action_target_player_id is not None and action_target_player_id in active_players:
                active_players.remove(action_target_player_id)
                active_players = [action_target_player_id] + active_players
            self.state.game_state["action_metadata"] = ActionMetadata(action_type=action_type, source_player_id=self.state.current_player_id, target_player_id=action_target_player_id, players_to_query=active_players)

    def _update_action_metadata_for_query_for_block_or_challenge_phase(self, action: CoupActionType):
        # If the player passes (they don't want to challenge), then we don't need to do anything, just advance (this is handled in step())
        if action is CoupActionType.PASS:
            return
        elif action is CoupActionType.BULLSHIT:
            self.state.game_state["action_metadata"].challenger_player_id = self.state.current_player_id
            self._execute_showdown_on_bullshit()
        elif action is CoupActionType.BlockForeignAid or action is CoupActionType.BlockStealAmbassador or action is CoupActionType.BlockStealCaptain or action is CoupActionType.BlockAssassinate:
            if (action is CoupActionType.BlockStealAmbassador or action is CoupActionType.BlockStealCaptain) and self.state.game_state["action_metadata"].action_type is not CoupActionType.Steal:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot call [block steal x] when the last played action is a {self.state.game_state['action_metadata'].action_type.name}.")
                return
            if action is CoupActionType.BlockAssassinate and self.state.game_state["action_metadata"].action_type is not CoupActionType.Assassinate:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot call [block assassinate] when the last played action is a {self.state.game_state['action_metadata'].action_type.name}.")
                return
            if action is CoupActionType.BlockForeignAid and self.state.game_state["action_metadata"].action_type is not CoupActionType.ForeignAid:
                self.state.set_invalid_move(player_id=self.state.current_player_id, reason=f"Invalid move. You cannot call [block foreign aid] when the last played action is a {self.state.game_state['action_metadata'].action_type.name}.")
                return
            self.state.game_state["phase"] = GamePhase.QueryToChallengeTheBlocker
            self.state.game_state["action_metadata"].blocker_player_id = self.state.current_player_id
            self.state.game_state["action_metadata"].block_type = action  # Track which specific block was used

            # This is a bit of a hack to ensure that the source player is always first in the query list.
            active_players = [self.state.game_state["action_metadata"].source_player_id] + [pid for pid in range(self.state.num_players) if len(self.state.game_state["hidden_hand"][pid]) > 0 and pid != self.state.current_player_id and pid != self.state.game_state["action_metadata"].source_player_id]
            self.state.game_state["action_metadata"].players_to_query = active_players
        else:  # Anything other than PASS or BULLSHIT or BlockXXXX is invalid in this phase
            block_options_str = "[block steal captain], [block steal ambassador], " if self.state.game_state["action_metadata"].action_type is CoupActionType.Steal and self.state.game_state["action_metadata"].target_player_id == self.state.current_player_id else \
                ("[block assassinate], " if (self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate  and self.state.game_state["action_metadata"].target_player_id == self.state.current_player_id) else \
                ("[block foreign aid], " if self.state.game_state["action_metadata"].action_type is CoupActionType.ForeignAid else ""))
            bullshit_str = "call [BULLSHIT], " if self.state.game_state["action_metadata"].action_type is not CoupActionType.ForeignAid else "" # you can't bullshit on foreign aid
            raise ValueError(f"Invalid action: {action}, Player #{self.state.game_state['action_metadata'].source_player_id} is attempting to {self.state.game_state["action_metadata"].action_type}, you must either {block_options_str}{bullshit_str}or [PASS]")

    def _update_action_metadata_for_query_to_challenge_the_blocker_phase(self, action: CoupActionType):
        if action is CoupActionType.PASS:
            return
        elif action is CoupActionType.BULLSHIT:
            self.state.game_state["action_metadata"].blocker_challenger_player_id = self.state.current_player_id
            self._execute_showdown_on_blocker_bullshit()
        else:
            raise ValueError(f"Invalid action: {action}, you must either [PASS] or call [BULLSHIT]")

    def _update_action_metadata_for_query_which_to_keep_phase(self, action_type: CoupActionType, cards_to_keep: Optional[List[str]] = None):
        """
        Handle the phase where player is choosing which cards to keep after an exchange
        """
        if action_type is not CoupActionType.Keep:
            cards_str = "<card1> <card2>" if len(self.state.game_state["revealed_hand"][self.state.current_player_id]) == 0 else "<card>"
            raise ValueError(f"Invalid action: {action_type}, you must respond with [keep {cards_str}] to specify the card(s) to keep")
        
        if cards_to_keep is None:
            raise ValueError("You must specify which cards to keep")
            
        # Check how many cards the player should keep based on their remaining influences
        player_id = self.state.current_player_id
        expected_cards_to_keep = 2 - len(self.state.game_state["revealed_hand"][player_id])
        
        if len(cards_to_keep) != expected_cards_to_keep:
            if expected_cards_to_keep == 2:
                raise ValueError("You must specify exactly two cards to keep")
            else:
                raise ValueError("You must specify exactly one card to keep (since you have lost an influence)")
        
        # Store the cards to keep in metadata
        self.state.game_state["action_metadata"].cards_to_keep = [c.title() for c in cards_to_keep]
        
        # Complete the exchange action
        self._execute_exchange_action()

    ######################################################################################################################################################################
    # These are all the "sink" states for a single turn. Either we execute the action, or we resolve a block or challenge and then potentially execute the action still. #
    ######################################################################################################################################################################
    def _execute_current_action(self):
        curr_action = self.state.game_state["action_metadata"]
        
        # This means no-op, a challenge/block was successful and we're not executing the action
        if curr_action.action_type is CoupActionType.PASS:
            return
        
        source_player_observation, target_player_observation, other_player_observations = None, None, None
        
        if curr_action.action_type is CoupActionType.Income:
            self.state.game_state["coins"][curr_action.source_player_id] += 1
            self.state.game_state["treasury_coins"] -= 1
            source_player_observation = f"You just successfully played income. You now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played income. They now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"
            
        elif curr_action.action_type is CoupActionType.Coup:
            self.state.game_state["coins"][curr_action.source_player_id] -= 7
            self.state.game_state["treasury_coins"] += 7

            # Make the target player lose a card
            lost_card = self._make_player_lose_a_card(curr_action.target_player_id)

            remaining_cards_with_target = "now have 1 card remaining." if len(self.state.game_state["hidden_hand"][curr_action.target_player_id]) > 0 else "now have no cards remaining and are eliminated from play."
            source_player_observation = f"You just successfully played coup on Player #{curr_action.target_player_id}. They lost a card and revealed a {lost_card}. They {remaining_cards_with_target}"
            target_player_observation = f"You just lost a card and revealed a {lost_card} card. You {remaining_cards_with_target}"
            other_player_observations = f"Player #{curr_action.source_player_id} just played coup on Player #{curr_action.target_player_id}. They lost a card and revealed a {lost_card} card. They {remaining_cards_with_target}"
            
        elif curr_action.action_type is CoupActionType.ForeignAid:
            self.state.game_state["coins"][curr_action.source_player_id] += 2
            self.state.game_state["treasury_coins"] -= 2

            source_player_observation = f"You just successfully played foreign aid. You now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played foreign aid. They now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Tax:
            self.state.game_state["coins"][curr_action.source_player_id] += 3
            self.state.game_state["treasury_coins"] -= 3

            source_player_observation = f"You just successfully played tax. You now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just played tax. They now have {self.state.game_state['coins'][curr_action.source_player_id]} coins"

        elif curr_action.action_type is CoupActionType.Assassinate:
            # Check for if player is already out, do nothing if so.
            if len(self.state.game_state["hidden_hand"][curr_action.target_player_id]) == 0:
                return
            
            # Make the target player lose a card
            lost_card = self._make_player_lose_a_card(curr_action.target_player_id)
            remaining_cards_with_target = "now have 1 card remaining." if len(self.state.game_state["hidden_hand"][curr_action.target_player_id]) > 0 else "now have no cards remaining and are eliminated from play."
            source_player_observation = f"You just successfully played assassinate on Player #{curr_action.target_player_id}. They lost a card and revealed a {lost_card}. They {remaining_cards_with_target}"
            target_player_observation = f"You just lost a card and revealed a {lost_card} card. You {remaining_cards_with_target}"
            other_player_observations = f"Player #{curr_action.source_player_id} just played assassinate on Player #{curr_action.target_player_id}. They lost a card and revealed a {lost_card}. They {remaining_cards_with_target}"
            
        elif curr_action.action_type is CoupActionType.Steal:
            self.state.game_state["coins"][curr_action.source_player_id] += 2
            self.state.game_state["coins"][curr_action.target_player_id] -= 2

            source_player_observation = f"You just successfully stole two coins from Player #{curr_action.target_player_id}. You now have {self.state.game_state['coins'][curr_action.source_player_id]} coins. Player #{curr_action.target_player_id} has {self.state.game_state['coins'][curr_action.target_player_id]} coins"
            target_player_observation = f"Player #{curr_action.source_player_id} just stole two coins from you. You now have {self.state.game_state['coins'][curr_action.target_player_id]} coins. Player #{curr_action.source_player_id} has {self.state.game_state['coins'][curr_action.source_player_id]} coins"
            other_player_observations = f"Player #{curr_action.source_player_id} just stole two coins from Player #{curr_action.target_player_id}. Player #{curr_action.source_player_id} has {self.state.game_state['coins'][curr_action.source_player_id]} coins. Player #{curr_action.target_player_id} has {self.state.game_state['coins'][curr_action.target_player_id]} coins"
            
        elif curr_action.action_type is CoupActionType.Exchange:
            # Draw two cards from the pile
            if len(self.state.game_state["pile"]) < 2:
                raise ValueError("Not enough cards in pile for exchange")
            
            # Draw two cards and add them directly to the player's hand
            card1 = self.state.game_state["pile"].pop()
            card2 = self.state.game_state["pile"].pop()
            self.state.game_state["hidden_hand"][curr_action.source_player_id].append(card1)
            self.state.game_state["hidden_hand"][curr_action.source_player_id].append(card2)
            
            # Change phase to QueryWhichToKeep
            self.state.game_state["phase"] = GamePhase.QueryWhichToKeep
            
            # Send observation to player about their options
            all_cards = self.state.game_state["hidden_hand"][curr_action.source_player_id]
            cards_str = ", ".join(all_cards)
            
            # Determine how many cards they need to keep based on revealed cards (influences lost)
            cards_to_keep_count = 2 - len(self.state.game_state["revealed_hand"][curr_action.source_player_id])
            
            if cards_to_keep_count == 2:
                source_player_observation = f"You drew two cards from the pile for exchange. You now have: {cards_str}. You must choose which two cards to keep using [keep <card1>" + \
                    f"{' <card2>' if len(self.state.game_state['revealed_hand'][curr_action.source_player_id]) == 0 else ''}]"
            else:  # cards_to_keep_count == 1
                source_player_observation = f"You drew two cards from the pile for exchange. You now have: {cards_str}. Since you have lost an influence, you must choose which one card to keep using [keep <card>]"
                
            other_player_observations = f"Player #{curr_action.source_player_id} is exchanging cards with the Court deck."

        # Broadcast the observations to the players
        if source_player_observation:
            self.state.add_observation(from_id=ta.GAME_ID, to_id=curr_action.source_player_id, message=source_player_observation, for_logging=False)
        if target_player_observation is not None:
            self.state.add_observation(from_id=ta.GAME_ID, to_id=curr_action.target_player_id, message=target_player_observation, for_logging=False)
        if other_player_observations is not None:
            exclude_ids = [curr_action.source_player_id]
            if curr_action.target_player_id is not None:
                exclude_ids.append(curr_action.target_player_id)
            self._broadcast_observations(other_player_observations, exclude_player_ids=exclude_ids)


    def _execute_showdown_on_bullshit(self):
        # the "challenged" player is the player who initially played the challenged card
        challenger_player_id = self.state.game_state["action_metadata"].challenger_player_id
        challenged_card = self._action_to_card(self.state.game_state["action_metadata"].action_type)
        challenged_player_id = self.state.game_state["action_metadata"].source_player_id  # The person who made the original claim
        is_honest = self.state.game_state["hidden_hand"][challenged_player_id].count(challenged_card) > 0
        
        challenged_message = ""
        challenger_message = ""
        other_player_observations = ""
        
        if is_honest:
            # If player was honest, then he gets a new card from the pile, and we reshuffle. Then challenger loses a card
            self.state.game_state["hidden_hand"][challenged_player_id].remove(challenged_card)
            self.state.game_state["pile"].append(challenged_card)
            random.shuffle(self.state.game_state["pile"])

            new_pulled_card = self.state.game_state["pile"].pop()
            self.state.game_state["hidden_hand"][challenged_player_id].append(new_pulled_card)

            # Player who called bullshit loses a card
            card_lost_by_challenger = self._make_player_lose_a_card(challenger_player_id)
            
            
            ###### UPDATE OBSERVATIONS
            challenger_remaining_cards = self.state.game_state["hidden_hand"][challenger_player_id]

            # Check if the challenger was the target of assassination and is now eliminated
            if (self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate and 
                self.state.game_state["action_metadata"].target_player_id == challenger_player_id and
                len(challenger_remaining_cards) == 0):
                # Target is eliminated, so assassination should not proceed
                self.state.game_state["action_metadata"].action_type = CoupActionType.PASS
    
            # Tell the challenger that their bullshit call failed
            challenger_message = f"Your bullshit call on Player #{challenged_player_id} failed. They did indeed have a {challenged_card} card." + \
                (f"You lost a {card_lost_by_challenger} card." if (len(challenger_remaining_cards) == 0 or challenger_remaining_cards[0] != card_lost_by_challenger) else f"You lost one of your {card_lost_by_challenger} cards.") + \
                (f"You now have only one card remaining, the {challenger_remaining_cards[0]} card." if len(challenger_remaining_cards) > 0 else \
                f"You have no cards remaining, you're eliminated!")
            # Tell the challenged player that they just survived a bullshit challenge
            challenged_message = f"You were unsuccessfully challenged on your {challenged_card} claim by Player #{challenger_player_id}. " + \
                f"Because you had to reveal your {challenged_card} card to prove them wrong, you were given a new one from the pile. It is a {new_pulled_card} card. Player #{challenger_player_id} revealed and lost a {card_lost_by_challenger} card, " + \
                (f"they now have only one card remaining." if len(challenger_remaining_cards) > 0 else f"they have no cards remaining, Player #{challenger_player_id} is eliminated!")
            # Tell everyone else what happened
            other_player_observations = f"Player #{challenger_player_id} just unsuccessfully called bullshit on Player #{challenged_player_id}'s {challenged_card} claim! " + \
                f"Player #{challenged_player_id} did indeed have a {challenged_card} card, put it back in the pile and got a new one. Player #{challenger_player_id} lost an influence and revealed a {card_lost_by_challenger} card." + \
                (f"Player #{challenger_player_id} now has 1 card remaining." if len(challenger_remaining_cards) > 0 else f"Player #{challenger_player_id} has no cards remaining, they're eliminated!")
    
        else:
            # Player who got challenged loses a card, nothing else changes
            card_lost_by_challenged = self._make_player_lose_a_card(challenged_player_id)
            
            # If this was an assassination that got successfully challenged, refund the 3 coins
            if self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate:
                self.state.game_state["coins"][challenged_player_id] += 3
                self.state.game_state["treasury_coins"] -= 3
            
            challenged_message = f"You were challenged on your {challenged_card} claim by Player #{challenger_player_id}, Since you did not have a {challenged_card} card, you lost your {card_lost_by_challenged} card." + \
                (f" Your 3 coins for the assassination attempt have been refunded." if self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate else "") + \
                (f" You now have only one card remaining, the {self.state.game_state["hidden_hand"][challenged_player_id][0]} card." if len(self.state.game_state["hidden_hand"][challenged_player_id]) > 0 else \
                " You have no cards remaining, you're eliminated!")
            # Tell the challenger that they just successfully challenged the challenged player
            challenger_message = f"You just successfully challenged Player #{challenged_player_id} on their {challenged_card} claim! " + \
                (f"They are blocked from doing it and have {len(self.state.game_state["hidden_hand"][challenged_player_id])} card remaining." if len(self.state.game_state["hidden_hand"][challenged_player_id]) > 0 else \
                "They have no cards remaining, they're eliminated!") + \
                (f" They were refunded their 3 coins." if self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate else "")
            # Other players see the challenger successfully challenge the challenged player
            other_player_observations = f"Player #{challenger_player_id} just successfully challenged Player #{challenged_player_id} on their {challenged_card} claim! " + \
                (f"Player #{challenged_player_id} was blocked from doing it and has {len(self.state.game_state["hidden_hand"][challenged_player_id])} card remaining." if len(self.state.game_state["hidden_hand"][challenged_player_id]) > 0 else \
                f"Player #{challenged_player_id} has no cards remaining, they're eliminated!") + \
                (f" They were refunded their 3 coins." if self.state.game_state["action_metadata"].action_type is CoupActionType.Assassinate else "")
            
            # Mark no-op for _advance_turn()
            self.state.game_state["action_metadata"].action_type = CoupActionType.PASS

        # Also mark that we have no more players to query so that we can advance the turn
        self.state.game_state["action_metadata"].players_to_query = None
        self.state.add_observation(from_id=ta.GAME_ID, to_id=challenged_player_id, message=challenged_message, for_logging=False)
        self.state.add_observation(from_id=ta.GAME_ID, to_id=challenger_player_id, message=challenger_message, for_logging=False)
        self._broadcast_observations(other_player_observations, exclude_player_ids=[challenged_player_id, challenger_player_id])
    
    def _execute_showdown_on_blocker_bullshit(self):
        source_player_id = self.state.game_state["action_metadata"].source_player_id
        blocker_player_id = self.state.game_state["action_metadata"].blocker_player_id
        challenger_player_id = self.state.game_state["action_metadata"].blocker_challenger_player_id
        
        # Determine which card the blocker claimed to have based on the block type
        action_metadata = self.state.game_state["action_metadata"]
        block_type = getattr(action_metadata, 'block_type', None)
        
        # Map the block type to the card claimed
        if block_type is CoupActionType.BlockForeignAid:
            block_card = "Duke"
        elif block_type is CoupActionType.BlockStealCaptain:
            block_card = "Captain"
        elif block_type is CoupActionType.BlockStealAmbassador:
            block_card = "Ambassador"
        elif block_type is CoupActionType.BlockAssassinate:
            block_card = "Contessa"
        else:
            raise ValueError(f"Unexpected block type: {block_type}")
        
        # Check if blocker actually has the card they claimed
        is_honest = self.state.game_state["hidden_hand"][blocker_player_id].count(block_card) > 0
        
        if is_honest:
            # Blocker was honest - they shuffle their card back and draw new, challenger loses a card
            self.state.game_state["hidden_hand"][blocker_player_id].remove(block_card)
            self.state.game_state["pile"].append(block_card)
            random.shuffle(self.state.game_state["pile"])
            
            new_card = self.state.game_state["pile"].pop()
            self.state.game_state["hidden_hand"][blocker_player_id].append(new_card)
            
            # Challenger loses a card
            card_lost = self._make_player_lose_a_card(challenger_player_id)
            challenger_remaining = len(self.state.game_state["hidden_hand"][challenger_player_id])
            
            # Send observations
            blocker_msg = f"You were challenged on your {block_card} block by Player #{challenger_player_id}. Since you had the {block_card}, you shuffled it back and drew a {new_card}. Player #{challenger_player_id} lost a {card_lost} and has {challenger_remaining} card(s) remaining."
            challenger_msg = f"Your challenge on Player #{blocker_player_id}'s {block_card} block failed. They did have a {block_card}. You lost a {card_lost} and have {challenger_remaining} card(s) remaining."
            others_msg = f"Player #{challenger_player_id} challenged Player #{blocker_player_id}'s {block_card} block and failed. Player #{blocker_player_id} had the {block_card}, shuffled it back and drew a new card. Player #{challenger_player_id} lost a {card_lost} and has {challenger_remaining} card(s) remaining."
            
            # The block was successful, so the original action is cancelled
            self.state.game_state["action_metadata"].action_type = CoupActionType.PASS
            
        else:
            # Blocker was lying - they lose a card, original action proceeds
            card_lost = self._make_player_lose_a_card(blocker_player_id)
            blocker_remaining = len(self.state.game_state["hidden_hand"][blocker_player_id])
            
            # Send observations
            blocker_msg = f"You were challenged on your {block_card} block by Player #{challenger_player_id}. Since you didn't have a {block_card}, you lost a {card_lost} and have {blocker_remaining} card(s) remaining."
            challenger_msg = f"Your challenge on Player #{blocker_player_id}'s {block_card} block succeeded! They didn't have a {block_card}. They lost a {card_lost} and have {blocker_remaining} card(s) remaining."
            others_msg = f"Player #{challenger_player_id} successfully challenged Player #{blocker_player_id}'s {block_card} block. Player #{blocker_player_id} didn't have the {block_card}, lost a {card_lost} and has {blocker_remaining} card(s) remaining."
            
            # The block failed, so the original action will proceed
            # No need to change action_type
        
        # Send all observations
        self.state.add_observation(from_id=ta.GAME_ID, to_id=blocker_player_id, message=blocker_msg, for_logging=False)
        self.state.add_observation(from_id=ta.GAME_ID, to_id=challenger_player_id, message=challenger_msg, for_logging=False)
        self._broadcast_observations(others_msg, exclude_player_ids=[blocker_player_id, challenger_player_id])
        
        # Mark that we're done querying
        self.state.game_state["action_metadata"].players_to_query = None

    def _execute_exchange_action(self):
        """Execute the exchange action after player has chosen which cards to keep"""
        metadata = self.state.game_state["action_metadata"]
        player_id = metadata.source_player_id
        cards_to_keep = metadata.cards_to_keep
        
        # Get all cards currently in hand (includes the 2 drawn cards)
        all_cards = self.state.game_state["hidden_hand"][player_id][:]
        
        # Validate that the cards to keep are actually available
        cards_available = all_cards[:]
        for card in cards_to_keep:
            if card in cards_available:
                cards_available.remove(card)
            else:
                raise ValueError(f"Cannot keep {card} - it's not one of your available cards")
        
        # Update player's hand with only the kept cards
        self.state.game_state["hidden_hand"][player_id] = list(cards_to_keep)
        
        # Put the non-kept cards back in the pile and shuffle
        for card in cards_available:
            self.state.game_state["pile"].append(card)
        random.shuffle(self.state.game_state["pile"])
        
        # Send observations
        if len(cards_to_keep) == 1:
            source_observation = f"You have completed your exchange and kept: {cards_to_keep[0]}"
        else:
            source_observation = f"You have completed your exchange and kept: {', '.join(cards_to_keep)}"
        other_observation = f"Player #{player_id} has completed their exchange."
        
        self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=source_observation, for_logging=False)
        self._broadcast_observations(other_observation, exclude_player_ids=[player_id])

    def _broadcast_observations(self, other_player_observations: str, exclude_player_ids: Optional[List[int]] = None):
        """ Broadcast the observations to the players except for the players in `exclude_player_ids` """
        for pid in range(self.state.num_players):
            if pid in exclude_player_ids:
                continue
            self.state.add_observation(from_id=ta.GAME_ID, to_id=pid, message=other_player_observations, for_logging=False)

    # ---------------------------------------------------------------------
    # PROMPT GENERATION METHODS -- CONVERTS GAME STATE TO PROMPT
    # ---------------------------------------------------------------------
    def _gen_initial_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        prompt = base_coup_prompts.base_prompt.replace("<NUM_PLAYERS>", str(self.state.num_players))
        prompt = prompt.replace("<PLAYER_ID>", str(player_id))
        prompt = prompt.replace("<PLAYER_OBSERVATIONS>", self._make_player_observations_prompt(player_id))
        return prompt
    

    def _make_last_action_msg(self, player_id: int, action: CoupActionType) -> str:
        """
        Make a prompt for the last action that was taken.
        Remember: This function will never be called when player_id is the current player
        """
        # TODO: re-check this thing with the new phases
        game_state = self.state.game_state
        curr_pid = self.state.current_player_id
        
        # If the game is in challenge phase and current_player==source, it means the current_player just made a challengable claim and we are now going to be asked to block or call bullshit
        if game_state["phase"] == "challenge" and curr_pid == game_state["last_action_source_player_id"]:
            action = game_state["last_action"]
            action_target_player_id = game_state["last_action_target_player_id"]
            you_str = " (you)" if action_target_player_id == player_id else ""
            affected_player_str = f" on Player {action_target_player_id}{you_str}." if action_target_player_id is not None and action not in {CoupActionType.Exchange, CoupActionType.Tax, CoupActionType.ForeignAid, CoupActionType.Keep} else "."
            claim_str = f" They're claiming they have a {self._action_to_card(action)} card." if action != CoupActionType.ForeignAid else ""
            return f"Player #{curr_pid} just played {action.value}{affected_player_str}{claim_str}"
        elif game_state["phase"] == "challenge" and curr_pid != game_state["last_action_source_player_id"]:
            action_str = f"call [BULLSHIT] on" if game_state["last_action"] == CoupActionType.BULLSHIT else f"[PASS] for their turn regarding challenging"
            your_str = " (your)" if game_state['last_action_source_player_id'] == player_id else ""
            return f"Player #{curr_pid} has decided to {action_str} Player #{game_state['last_action_source_player_id']}'s {your_str} claim."
        
        elif action is CoupActionType.Keep:   # Special exception for the exchange action
            return f"Player #{curr_pid} just completed their exchange."
        else: # game_state["phase"] == "play", so we are in play mode not challenge mode, and we know the action is not Keep
            return f"Player #{curr_pid} just played {action.value}."

    def _make_player_observations_prompt(self, player_id: Optional[int] = None) -> str:
        """
        Make a prompt for the specified player. Tells them their latest hand and the state of the game (what cards are in the pile, what cards are in the revealed hand, etc).
        """
        if player_id is None:
            player_id = self.state.current_player_id
        game_state = self.state.game_state
        msg = f"There are {self.state.num_players} players in the game.\n"

        for pid in range(self.state.num_players):
            if pid == player_id: 
                continue
            if len(game_state['hidden_hand'][pid]) == 0:
                msg += f"Player #{pid} is out.\n"
            elif len(game_state['revealed_hand'][pid]) > 0:
                msg += f"Player #{pid} has {game_state['coins'][pid]} coins, has revealed and lost a {game_state['revealed_hand'][pid][0]} card, and has {len(game_state['hidden_hand'][pid])} hidden influence cards remaining.\n"
            else:
                msg += f"Player #{pid} has {game_state['coins'][pid]} coins, and has {len(game_state['hidden_hand'][pid])} hidden influence cards remaining.\n"


        msg += f"\n ------ You are Player #{player_id}. You have {game_state['coins'][player_id]} coins"

        if len(game_state['hidden_hand'][player_id]) == 2:
            msg += f" and {len(game_state['hidden_hand'][player_id])} hidden influence cards remaining: You have a {game_state['hidden_hand'][player_id][0]} and a {game_state['hidden_hand'][player_id][1]}."
        elif len(game_state['hidden_hand'][player_id]) == 1:
            msg += f", a hidden {game_state['hidden_hand'][player_id][0]} card, and you have a revealed {game_state['revealed_hand'][player_id][0]} card that is out of play."

        msg += " --------\n"
        return msg
    
    def _send_call_to_action_prompt(self) -> None:
        """
        Make a prompt for the player that asks them to make an action or challenge. 
        This is only called when the player IS the current_player, done AFTER we've advanced the turn.
        """
        msg = base_coup_prompts.base_reprompt
        msg = msg.replace("<PLAYER_OBSERVATIONS>", self._make_player_observations_prompt())
        
        # Determine the call to action based on the current phase
        if self.state.game_state["phase"] == GamePhase.QueryWhichToKeep:
            # Player needs to choose which cards to keep after exchange
            call_to_action_str = f"You need to choose which {'two cards' if len(self.state.game_state['revealed_hand'][self.state.current_player_id]) == 0 else 'card'} to keep. Use [keep <card1>" + \
                f"{' <card2>' if len(self.state.game_state['revealed_hand'][self.state.current_player_id]) == 0 else ''}]"
            
        elif self.state.game_state["phase"] == GamePhase.QueryForBlockOrChallenge:
            # Player is being asked if they want to block or challenge
            metadata = self.state.game_state["action_metadata"]
            action = metadata.action_type
            source_player_id = metadata.source_player_id
            target_player_id = metadata.target_player_id
            
            # Build the action description
            action_desc = f"Player #{source_player_id} is attempting to {action.value}"
            if action is CoupActionType.Assassinate:
                action_desc += " (they have paid 3 coins)"
            if target_player_id is not None and target_player_id != self.state.current_player_id:
                action_desc += f" on Player #{target_player_id}"
            elif target_player_id == self.state.current_player_id:
                action_desc += " on you"
            
            # Determine valid block options for current player
            block_options = []
            if action is CoupActionType.ForeignAid:
                block_options.append("[block foreign aid]")
            elif action is CoupActionType.Steal and target_player_id == self.state.current_player_id:
                block_options.extend(["[block steal captain]", "[block steal ambassador]"])
            elif action is CoupActionType.Assassinate and target_player_id == self.state.current_player_id:
                block_options.append("[block assassinate]")
            
            # Build the call to action
            if block_options:
                block_str = ", ".join(block_options) + ", "
            else:
                block_str = ""
            
            # Add claim info for challengeable actions
            claim_str = ""
            if action in {CoupActionType.Tax, CoupActionType.Assassinate, CoupActionType.Steal, CoupActionType.Exchange}:
                claim_str = f" (claiming {self._action_to_card(action)})"
            
            # Build the call to action with proper handling for foreign aid
            bullshit_str = "call [BULLSHIT], " if action is not CoupActionType.ForeignAid else ""
            call_to_action_str = f"{action_desc}{claim_str}. Do you want to {block_str}{bullshit_str}or [PASS]?"
            
        elif self.state.game_state["phase"] == GamePhase.QueryToChallengeTheBlocker:
            # Someone blocked, asking if anyone wants to challenge the block
            metadata = self.state.game_state["action_metadata"]
            blocker_id = metadata.blocker_player_id
            block_type = metadata.block_type
            
            # Determine which card the blocker is claiming based on block type
            if block_type is CoupActionType.BlockForeignAid:
                block_claim = "Duke"
            elif block_type is CoupActionType.BlockStealCaptain:
                block_claim = "Captain"
            elif block_type is CoupActionType.BlockStealAmbassador:
                block_claim = "Ambassador"
            elif block_type is CoupActionType.BlockAssassinate:
                block_claim = "Contessa"
            else:
                block_claim = "unknown card"
            
            call_to_action_str = f"Player #{blocker_id} is blocking with {block_claim}. Do you want to call [BULLSHIT] or [PASS]?"
            
        elif self.state.game_state["coins"][self.state.current_player_id] >= 10:
            # Forced coup
            call_to_action_str = "You have 10 or more coins and must coup. Use [coup x] where x is the player id number."
            
        else:
            # Normal play phase
            call_to_action_str = "What action do you want to take?"
        
        msg = msg.replace("<CALL_TO_ACTION_OR_CHALLENGE>", call_to_action_str)
        
        # Send the message to the current player
        self.state.add_observation(from_id=ta.GAME_ID, to_id=self.state.current_player_id, message=msg, for_logging=False)

    def _action_to_card(self, action: CoupActionType) -> str:
        """ Convert a CoupActionType to a card """
        
        if action is CoupActionType.Tax:
            return "Duke"
        elif action is CoupActionType.Assassinate:
            return "Assassin"
        elif action is CoupActionType.Steal:
            return "Captain"
        elif action is CoupActionType.Exchange:
            return "Ambassador"
        
        elif action is CoupActionType.BlockAssassinate:
            return "Contessa"
        elif action is CoupActionType.BlockStealCaptain:
            return "Captain"
        elif action is CoupActionType.BlockStealAmbassador:
            return "Ambassador"
        elif action is CoupActionType.BlockForeignAid:
            return "Duke"
        
        else:
            return "."

    # ---------------------------------------------------------------------
    # GAME STATE ADJUSTMENT METHODS -- SYNTACTIC SUGAR FOR THE GAME LOGIC
    # ---------------------------------------------------------------------

    def _make_player_lose_a_card(self, player_id: int):
        """
        In a perfect world, the player would pick which card they want to lose.
        But for now, we'll just pop the last card in their hand.
        """
        card = self.state.game_state["hidden_hand"][player_id].pop()
        self.state.game_state["revealed_hand"][player_id].append(card)
        return card

    def _advance_turn(self):
        """
        Advance the state to the next player based on current phase.
        """
        if self.state.game_state["phase"] == GamePhase.Play:
            # Normal play phase - go to next player in turn order
            current_pid = self.state.current_player_id
            next_pid = (current_pid + 1) % self.state.num_players
            # Skip eliminated players
            while len(self.state.game_state["hidden_hand"][next_pid]) == 0:
                next_pid = (next_pid + 1) % self.state.num_players
                if next_pid == current_pid:  # All other players eliminated
                    break

            # Income and Coup immediately advance the turn, so action_metadata is no longer needed
            if self.state.game_state["action_metadata"] is not None and self.state.game_state["action_metadata"].action_type in {CoupActionType.Income, CoupActionType.Coup}:
                self.state.game_state["action_metadata"] = None
                    
        elif self.state.game_state["phase"] == GamePhase.QueryWhichToKeep:
            # Check if the exchange has been completed (cards_to_keep is set)
            metadata = self.state.game_state["action_metadata"]
            if hasattr(metadata, 'cards_to_keep') and metadata.cards_to_keep is not None:
                # Exchange is complete, move to next player
                self.state.game_state["phase"] = GamePhase.Play
                source_pid = metadata.source_player_id
                next_pid = (source_pid + 1) % self.state.num_players
                # Skip eliminated players
                while len(self.state.game_state["hidden_hand"][next_pid]) == 0:
                    next_pid = (next_pid + 1) % self.state.num_players
                    if next_pid == source_pid:  # All other players eliminated
                        break
                self.state.game_state["action_metadata"] = None
            else:
                # Stay with the same player - they still need to choose cards
                next_pid = self.state.current_player_id
            
        elif self.state.game_state["phase"] in {GamePhase.QueryForBlockOrChallenge, GamePhase.QueryToChallengeTheBlocker}:
            metadata = self.state.game_state["action_metadata"]
            if metadata.players_to_query and len(metadata.players_to_query) > 0:
                # Query next player in the list
                next_pid = metadata.players_to_query.pop(0)
            else:
                # No more players to query
                if self.state.game_state["phase"] == GamePhase.QueryToChallengeTheBlocker:
                    # Only cancel the original action if no one challenged the block
                    # (If someone did challenge and the blocker was honest, the action was already set to PASS in _execute_showdown_on_blocker_bullshit)
                    if not hasattr(metadata, 'blocker_challenger_player_id') or metadata.blocker_challenger_player_id is None:
                        # Block was not challenged, so cancel the original action
                        self.state.game_state["action_metadata"].action_type = CoupActionType.PASS
                
                # Execute the action (may be PASS if blocked/challenged successfully)
                self._execute_current_action()
                
                # If we just executed an Exchange, we'll be in QueryWhichToKeep phase
                if self.state.game_state["phase"] == GamePhase.QueryWhichToKeep:
                    next_pid = self.state.game_state["action_metadata"].source_player_id
                    self.state.game_state["action_metadata"].players_to_query = [] # No more players to query
                else:
                    # Return to normal play - next player after action source
                    self.state.game_state["phase"] = GamePhase.Play
                    source_pid = metadata.source_player_id
                    next_pid = (source_pid + 1) % self.state.num_players
                    # Skip eliminated players
                    while len(self.state.game_state["hidden_hand"][next_pid]) == 0:
                        next_pid = (next_pid + 1) % self.state.num_players
                        if next_pid == source_pid:  # All other players eliminated
                            break
                    self.state.game_state["action_metadata"] = None
        else:
            raise Exception(f"Unexpected game phase: {self.state.game_state['phase']}")
        
        self.state.manually_update_current_player(new_player_id=next_pid)
        
        # Check for winner
        winner = self._get_winner()
        if winner is not None:
            self.state.set_winners(player_ids=[winner], reason=f"Player {winner} has won the game!")
            return True, {"winner": winner}
        else:
            return False, {}

    def _get_winner(self) -> Optional[int]:
        """
        Check if the game is over. Return winning player id if so, otherwise return None.
        """
        remaining_players = [pid for pid in range(self.state.num_players) if len(self.state.game_state["hidden_hand"][pid]) > 0]
        if len(remaining_players) == 1:
            return remaining_players[0]
        else:
            return None


    # -----------------------------------------------------------------------
    #  PARSE ACTIONS -- JUST BOILERPLATE CODE NOTHING INTERESTING BELOW HERE
    # -----------------------------------------------------------------------
    def _parse_action(self, response_str: str) -> Tuple[CoupActionType, Optional[Union[int, List[str]]]]:
        """
        Extract the **last** square-bracket command from `response_str` and convert it to (CoupActionType, arg).

        The purpose of this method is TO PARSE ONLY. It makes sure the response is translated into a valid action, but does not validate against the state of the game.
        """
        # 1) Grab all bracketed chunks, take the last one.
        match_list = re.findall(r"\[([^\[\]]+)\]", response_str.replace("[GAME]", " "))
        if not match_list:
            raise ValueError(f"No bracketed command found. What is your desired [action]?")
        cmd = match_list[-1].strip().lower()
        tokens = cmd.split()

        if not tokens:
            raise ValueError("Empty command.")

        # ---------- Simple one-word actions ----------
        simple = {"income": CoupActionType.Income, "tax": CoupActionType.Tax,"exchange": CoupActionType.Exchange, "pass": CoupActionType.PASS, "bullshit": CoupActionType.BULLSHIT}
        if tokens[0] in simple:
            if len(tokens) > 1:
                raise ValueError(f"Invalid action: {tokens[0]}, cannot have more than one word when doing a {tokens[0]}")
            return simple[tokens[0]], None
        
        if tokens[:2] == ["foreign", "aid"]:
            if len(tokens) > 2:
                raise ValueError(f"Invalid action: {response_str}, cannot have more than two words when doing a foreign aid")
            return CoupActionType.ForeignAid, None

        # ---------- Directed actions ----------
        directed_map = {"coup": CoupActionType.Coup, "assassinate": CoupActionType.Assassinate, "steal": CoupActionType.Steal }
        if tokens[0] in directed_map:
            if len(tokens) < 2 or not tokens[1].isdigit():
                raise ValueError(f"Missing / invalid target for '{tokens[0]}'.")
            return directed_map[tokens[0]], int(tokens[1])

        # ---------- Ambassador "keep" special ----------
        if tokens[0] == "keep":
            if len(tokens) < 2 or len(tokens) > 3:
                raise ValueError("'keep' must specify one or two cards to keep.")
            
            cards = []
            for i in range(1, len(tokens)):
                if tokens[i].lower() not in {"duke", "assassin", "ambassador", "captain", "contessa"}:
                    raise ValueError(f"Invalid card name: {tokens[i]}")
                cards.append(tokens[i].lower())
            
            return CoupActionType.Keep, cards

        # ---------- Blocks ----------
        if tokens[0] == "block":
            if tokens[1:3] == ["foreign", "aid"]:
                return CoupActionType.BlockForeignAid, None
            if tokens[1] == "steal" and len(tokens) >= 3:
                if tokens[2] == "ambassador":
                    return CoupActionType.BlockStealAmbassador, None
                if tokens[2] == "captain":
                    return CoupActionType.BlockStealCaptain, None
                raise ValueError("Block steal must specify 'ambassador' or 'captain'.")
            if tokens[1] == "assassinate":
                return CoupActionType.BlockAssassinate, None

        raise ValueError(f"Unrecognized command: [{cmd}]")
    

    #########################################################################
    #  RENDERING METHOD
    #########################################################################
    def _game_state_to_headline_str(self, game_state: Optional[Dict[str, Any]] = None):
        """
        Convert the game state to a headline string.
        """
        if hasattr(self.state, "game_state") and self.state.game_state is not None and self._get_winner() == self.state.current_player_id:
            return f"Player #{self._get_winner()} has won!"
        if game_state["phase"] == GamePhase.Play:
            return f"It's Player #{self.state.current_player_id}'s turn"
        elif game_state["phase"] == GamePhase.QueryForBlockOrChallenge:
            tgt_player_str = ""
            if game_state['action_metadata'].action_type in {CoupActionType.Assassinate, CoupActionType.Steal}:
                tgt_player_str = f" on Player #{game_state['action_metadata'].target_player_id}" if game_state['action_metadata'].action_type is CoupActionType.Assassinate else f" from Player #{game_state['action_metadata'].target_player_id}"
            return f"Player #{game_state['action_metadata'].source_player_id} is attempting a {game_state['action_metadata'].action_type.name}{tgt_player_str}, asking if Player #{self.state.current_player_id} wants to block/challenge."
        elif game_state["phase"] == GamePhase.QueryToChallengeTheBlocker:
            return f"Player #{game_state['action_metadata'].blocker_player_id} is doing a {game_state['action_metadata'].block_type.name} on Player #{game_state['action_metadata'].source_player_id}, asking if Player #{self.state.current_player_id} wants to challenge the block."
        elif game_state["phase"] == GamePhase.QueryWhichToKeep:
            return f"Player #{game_state['action_metadata'].source_player_id} is attempting an Exchange, asking which they wish to keep."
        else:
            raise Exception(f"Unexpected game phase: {game_state['phase']}")
        
    def _get_player_marker(self, player_id: int, game_state: Optional[Dict[str, Any]] = None):
        """
        Helper function to display a useful marker to show the player's status in the game.
        """
        if hasattr(self.state, "game_state") and self.state.game_state is not None and self._get_winner() == player_id:
            return "👑"  # Player is the winner
        if game_state["hidden_hand"][player_id] == []:
            return "💀"  # Player is eliminated
        if (game_state["phase"] == GamePhase.QueryForBlockOrChallenge or game_state["phase"] == GamePhase.QueryToChallengeTheBlocker) and \
            player_id == game_state["action_metadata"].blocker_player_id:
            return "B"  # Player is blocking the action
        
        if game_state["phase"] == GamePhase.QueryWhichToKeep and player_id == game_state["action_metadata"].source_player_id:
            return "🔀"  # Player being asked which cards they wish to keep
        
        if self.state.current_player_id == player_id:
            return "*"  # Player is the current player
        
        if game_state["action_metadata"] is not None and game_state["action_metadata"].source_player_id == player_id:
            return "."  # Player is awaiting potential challenges
        
        return " "  # Player is not involved in the action

    def _render_board(self, game_state: Optional[Dict[str, Any]] = None):
        """
        Pretty console renderer for a Coup game_state.

        The offset and adjustment are used to ensure that the board is always LINE_WIDTH characters wide, because ansii codes add to char count but not to spacing.
        """
        # --- helpers -----------------------------------------------------------
        game_state = self.state.game_state if game_state is None else game_state
        
        # Card colors - specific ANSI codes for each card type
        CARD_COLOURS = {
            "Contessa": 91,      # Red
            "Ambassador": 92,    # Green
            "Duke": 95,          # Purple/Magenta
            "Captain": 94,       # Blue
            "Assassin": 90       # Dark Grey
        }
        
        # Player header colors - using different colors from cards
        # Using: Yellow(93), Cyan(96), White(97), and variations
        PLAYER_COLOURS = [93, 96, 97, 33, 35, 36]

        def colour(text: str, code: int) -> str:
            return f"\033[{code}m{text}\033[0m"

        def bold_underline_colour(text: str, code: int) -> str:
            # Combines bold (1), underline (4) and color in one ANSI code
            return f"\033[1;4;{code}m{text}\033[0m"

        def strike(text: str) -> str:
            # ANSI strike-through (not supported in a few older terminals)
            return f"\033[9m{text}\033[0m"


        # -----------------------------------------------------------------------

        out_lines = ["",self._game_state_to_headline_str(game_state), ""]
        # Sort players numerically for reproducibility
        for pid in range(self.state.num_players):
            player_colour_code = PLAYER_COLOURS[pid % len(PLAYER_COLOURS)]

            # "*" means this is the current player who just did an action
            # "." means this is the player who initially triggered a QueryForX phase
            # " " means this is a player who is not involved in the action

            # ----- header: "Player #x" (unique colour) -----
            curr_player_marker = self._get_player_marker(pid, game_state)
            header = bold_underline_colour(f"[{curr_player_marker}] - Player #{pid}", player_colour_code)
            out_lines.append(f"{header}  ––  {game_state['coins'][pid]} coin{'s' if game_state['coins'][pid]!=1 else ''}")

            # ----- cards -----------------------------------
            hand_cards = game_state["hidden_hand"][pid]   # Hidden cards
            revealed   = game_state["revealed_hand"][pid] # Revealed/lost cards

            for card in hand_cards:
                card_colour_code = CARD_COLOURS.get(card, 97)  # Default to white if card not found
                out_lines.append(f"   - {colour(card, card_colour_code)}")

            # Sometimes revealed cards may no longer be in hand (fully lost)
            for card in revealed:
                card_colour_code = CARD_COLOURS.get(card, 97)  # Default to white if card not found
                out_lines.append(f"   - {colour(strike(card), card_colour_code)}")

            out_lines.append("")

        out_lines.append("")
        out_lines.append("")
        # from_ansi is used to ensure that the ANSI codes are properly padded while rendering
        return Text.from_ansi("\n".join(out_lines))

   