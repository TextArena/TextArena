from typing import Dict, Optional, List, Tuple, Any
import random
import textarena as ta
import re

class SpiteAndMaliceEnv(ta.Env):
    """
    Environment for Spite and Malice.
    """
    def __init__(self):
        """ Initialize the Spite and Malice environment """
        # Initialize the deck and shuffle
        self.deck = [f"{rank}{suit}" for rank in "A23456789JQK" for suit in "♠♥♦♣"] * 2
        
    @property
    def terminal_render_keys(self):
        return ["rendered_board","player_turn"]

    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        """ Reset the environment to start a new game """
        # Initialize the game state
        self.state = ta.TwoPlayerState(num_players=2, seed=seed, max_turns=None)
        
        ## Initialize the players' payoff piles, hand, discard piles, and center piles
        random.shuffle(self.deck)
        self.players = self._initialize_players()
        self.center_piles = [[] for _ in range(4)]
        
        ## Draw cards for each player
        self._draw_cards(0)
        self._draw_cards(1)

        ## Return the initial observations
        game_state={
            "players": self.players, "center_piles": self.center_piles,
            "player_turn": self.state.current_player_id, "rendered_board": self._render_board()
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._observe_current_state(player_id=self.state.current_player_id)
    
    def _initialize_players(self):
        """ Initialize the players' payoff piles, hand, and discard piles. """
        players = {0: {"payoff": [], "hand": [], "discard": [[] for _ in range(4)]},
                   1: {"payoff": [], "hand": [], "discard": [[] for _ in range(4)]}}
        
        ## Deal the payoff piles (20 cards each for a shorter game)
        for player in players:
            players[player]["payoff"] = [self.deck.pop() for _ in range(20)]
        
        return players
    
    def _draw_cards(self, player_id: int):
        """ Draw cards to maintain 5 cards in hand. """
        while len(self.players[player_id]["hand"]) < 5 and self.deck:
            self.players[player_id]["hand"].append(self.deck.pop())
        
        if not self.deck and len(self.players[player_id]["hand"]) < 5:
            self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=self.m("message", "no_more_cards"), observation_type=ta.ObservationType.GAME_MESSAGE)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        """
        Generate the player prompt.

        Args:
            player_id (int): ID of the player.

        Returns:
            str: Player prompt.
        """
        return self.m("player_prompt", "intro", player_id=player_id)

    def _observe_current_state(self, player_id: int):
        """ Observe the current state of the game for a specific player """
        available_moves = ["[draw]"]

        # Add valid play actions
        for i, pile in enumerate(self.center_piles):
            # From payoff pile
            if self.players[player_id]["payoff"]:
                top_payoff_card = self.players[player_id]["payoff"][-1]
                if self._can_play_on_center(top_payoff_card, pile):
                    available_moves.append(f"[play {top_payoff_card} {i}]")
            # From hand
            for card in self.players[player_id]["hand"]:
                if self._can_play_on_center(card, pile):
                    available_moves.append(f"[play {card} {i}]")
            # From discard
            for discard_pile in self.players[player_id]["discard"]:
                if discard_pile:
                    top_discard_card = discard_pile[-1]
                    if self._can_play_on_center(top_discard_card, pile):
                        available_moves.append(f"[play {top_discard_card} {i}]")

        # Add discard actions (you can discard any card from hand to any discard pile)
        for i, discard_pile in enumerate(self.players[player_id]["discard"]):
            for card in self.players[player_id]["hand"]:
                available_moves.append(f"[discard {card} {i}]")

        # Add to observation
        self.state.add_observation(to_id=player_id, message=self.m("board", "current", board=self._render_board(player_id=player_id), moves=", ".join(available_moves)), observation_type=ta.ObservationType.GAME_BOARD)

    
    def _play_card(self, player_id: int, card: str, center_index: int):
        """ Play a card from hand, payoff pile, or discard pile to a center pile """
        # Check if the card can be played on the specified center pile
        if self._can_play_on_center(card, self.center_piles[center_index]):
            # Check if the card is the top card of the payoff pile first
            if self.players[player_id]["payoff"] and card == self.players[player_id]["payoff"][-1]:
                self.players[player_id]["payoff"].pop()
            # Check if the card is in the player's hand
            elif card in self.players[player_id]["hand"]:
                self.players[player_id]["hand"].remove(card)
            # Check if the card is the top card of any discard pile
            else:
                found_in_discard = False
                for discard_pile in self.players[player_id]["discard"]:
                    if discard_pile and discard_pile[-1] == card:
                        discard_pile.pop()
                        found_in_discard = True
                        break
                if not found_in_discard:
                    return False  # Exit if the card was not in any valid pile

            # Add the card to the center pile
            self.center_piles[center_index].append(card)
            # Check if the center pile has reached Queen and clear it if so
            if len(self.center_piles[center_index]) == 11:
                self.center_piles[center_index] = []
            return True
        # If the card could not be played, return False
        return False

    def _can_play_on_center(self, card: str, pile: List[str]):
        """
        Determine if a card can be played on a center pile.
        Note that king cards are wild and can be played on any card, e.g. [play K♠ 0].
        """
        # Allow King to be played as a wild card in any position
        if card[0] == "K":
            return True
        # If the pile is empty, allow an Ace or King to start it
        if not pile:
            return card[0] == "A" or card[0] == "K"
        # If the top card of the pile is a King, treat it as the next rank in sequence
        if pile[-1][0] == "K":
            # Get the rank the King is substituting by assuming it's the next rank in sequence
            top_card_rank = len(pile) -1 if len(pile) >= 1 else 0  # Treat as '1' if K is the only card
        else:
            # Otherwise, use the actual rank of the top card
            top_card_rank = self._card_rank(pile[-1][0])
        # Check if the played card is one rank higher than the top card or King-replaced rank
        return self._card_rank(card[0]) == top_card_rank + 1
    
    def _card_rank(self, card: str):
        """ Define the rank order (A=1, 2=2, ..., Q=12, K as wild) """
        ranks = "A23456789JQK"
        return ranks.index(card[0])
    
    def _discard_card(self, player_id: int, card: str, discard_index: int):
        """ Discard a card to one of the player's discard piles """
        self.players[player_id]["hand"].remove(card)
        self.players[player_id]["discard"][discard_index].append(card)

    def _check_win(self, player_id: int):
        """ 
        Check if the player's payoff pile is empty (normal win condition)
        or if there's a deadlock situation where no player can make valid moves
        """
        # Normal win condition: payoff pile is empty
        if len(self.players[player_id]["payoff"]) == 0:
            return True
        
        # Check for deadlock situation
        if self._is_deadlock():
            # Determine winner based on fewest cards in payoff pile
            player_0_payoff = len(self.players[0]["payoff"])
            player_1_payoff = len(self.players[1]["payoff"])
            
            if player_0_payoff < player_1_payoff:
                return player_id == 0
            elif player_1_payoff < player_0_payoff:
                return player_id == 1
            else:
                # Tie - could return False to continue game or handle as desired
                # For now, we'll declare the current player as winner in case of tie
                return True
        
        return False

    def _is_deadlock(self):
        """
        Check if the game is in a deadlock state where no player can make valid moves.
        This happens when:
        1. No more cards can be drawn from the deck
        2. Neither player can play any card from their hand, payoff pile, or discard piles
        3. Both players have empty hands (they've been forced to discard everything)
        """
        # If there are still cards in the deck, not a deadlock
        if self.deck:
            return False
        
        # Check if both players have no cards in hand and no valid moves
        for player_id in [0, 1]:
            player = self.players[player_id]
            
            # If player has cards in hand, they can still discard, so not deadlock
            if player["hand"]:
                return False
            
            # Check if player can make any valid plays from payoff or discard piles
            if self._player_has_valid_moves(player_id):
                return False
        
        return True

    def _player_has_valid_moves(self, player_id: int):
        """
        Check if a player has any valid moves (can play cards to center piles)
        """
        player = self.players[player_id]
        
        # Check if top card of payoff pile can be played
        if player["payoff"]:
            top_payoff_card = player["payoff"][-1]
            for pile in self.center_piles:
                if self._can_play_on_center(top_payoff_card, pile):
                    return True
        
        # Check if any top cards from discard piles can be played
        for discard_pile in player["discard"]:
            if discard_pile:
                top_discard_card = discard_pile[-1]
                for pile in self.center_piles:
                    if self._can_play_on_center(top_discard_card, pile):
                        return True
        
        return False

    def _handle_game_end_check(self):
        """
        Check for game end conditions and set winner if appropriate.
        Call this in your step method after processing actions.
        """
        current_player = self.state.current_player_id
        
        # Check if current player won
        if self._check_win(current_player):
            if len(self.players[current_player]["payoff"]) == 0:
                reason = self.m("outcome", "payoff_win", player_id=current_player)
                self.state.set_winner(player_id=current_player, reason=reason)
            else:
                # Deadlock situation
                player_0_payoff = len(self.players[0]["payoff"])
                player_1_payoff = len(self.players[1]["payoff"])

                if player_0_payoff < player_1_payoff:
                    winner = 0
                    reason = self.m("outcome", "deadlock_p0", p0=player_0_payoff, p1=player_1_payoff)
                elif player_1_payoff < player_0_payoff:
                    winner = 1
                    reason = self.m("outcome", "deadlock_p1", p0=player_0_payoff, p1=player_1_payoff)
                else:
                    winner = current_player
                    reason = self.m("outcome", "deadlock_tie", p0=player_0_payoff, player_id=current_player)

                self.state.set_winner(player_id=winner, reason=reason)
            return True
        
        return False
        
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """
        Process the player's action.
        
        Args:
            action (str): The action taken by the player.
            
        Returns:
            bool: done.
            Info: Additional information about the game state
        """

        player_id = self.state.current_player_id

        ## update the observation
        self.state.add_observation(from_id=player_id, to_id=player_id, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        ## action search pattern
        action_search_pattern = re.compile(r"\[(play|discard|draw)(?: ([A23456789JQK][♠♥♦♣]) ([0-3]))?\]") # e.g. [play A♠ 0], [discard A♠ 1], [draw]
        matches = action_search_pattern.findall(action)
        ## Let's allow for the player to parse multiple actions 

        rotate_player  = False

        if not matches:
            self.state.set_invalid_move(reason=self.m("invalid_move", "wrong_format", player_id=player_id))
            rotate_player  = True
        else:
            ## at least one action is matched. Let's process them.
            for match in matches:
                action_type, card, index = match
                if action_type == "draw":
                    self._draw_cards(player_id)
                    self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=self.m("message", "drew_self"), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    self.state.add_observation(from_id=ta.GAME_ID, to_id=1-player_id, message=self.m("message", "drew_other", player_id=player_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

                elif action_type == "play":
                    ## check if the player has the card in hand or payoff pile or discard pile
                    if self._play_card(player_id, card, int(index)):
                        self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=self.m("message", "played_self", card=card, index=index), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                        self.state.add_observation(from_id=ta.GAME_ID, to_id=1-player_id, message=self.m("message", "played_other", player_id=player_id, card=card, index=index), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                    else:
                        self.state.set_invalid_move(reason=self.m("invalid_move", "bad_play", player_id=player_id, card=card, index=index))
                        break
                elif action_type == "discard":
                    ## player is discarding a card, which also ends the players turn
                    if card == self.players[player_id]["payoff"][-1] and card not in self.players[player_id]["hand"]:
                        self.state.set_invalid_move(reason=self.m("invalid_move", "discard_from_payoff", player_id=player_id))
                        break
                    elif card not in self.players[player_id]["hand"]:
                        self.state.set_invalid_move(reason=self.m("invalid_move", "discard_not_in_hand", player_id=player_id))
                        break
                    else:
                        self._discard_card(player_id, card, int(index))
                        self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=self.m("message", "discarded_self", card=card, index=index, other=1 - player_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)
                        self.state.add_observation(from_id=ta.GAME_ID, to_id=-1, message=self.m("message", "discarded_other", player_id=player_id, card=card, index=index, other=1 - player_id), observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION) # TODO - can probably improve this message.
                        rotate_player  = True
                        self.state.game_state["player_turn"] = 1 - player_id
                        break
                else:
                    self.state.set_invalid_move(reason=self.m("invalid_move", "bad_move_type", player_id=player_id))
                    break
        
        ## udpate the rendered board game state
        self.state.game_state["rendered_board"] = self._render_board()

        ## check if the game is over (updated to handle deadlock)
        if self._handle_game_end_check():
            pass  # Winner already set in _handle_game_end_check

        self._observe_current_state(player_id=1 - player_id if rotate_player else player_id)  # Observe the next player's state if we rotated players
        return self.state.step(rotate_player)        
    
    def _player_view(self, player: int):
        """ Build a localized message for a single player's board view """
        top = self.players[player]['payoff'][-1] if self.players[player]['payoff'] else self.m("board", "empty")
        return self.m("board", "player_view", player_id=player, top=top,
                      length=len(self.players[player]['payoff']),
                      hand=self.players[player]['hand'], discard=self.players[player]['discard'])

    def _render_board(self, player_id: Optional[int] = None):
        """ Render the game board """
        center = self.m("board", "center", p0=self.center_piles[0], p1=self.center_piles[1],
                        p2=self.center_piles[2], p3=self.center_piles[3])
        if player_id is not None:
            return self.m("board", "wrapper", center=center, view0=self._player_view(player_id), view1="")
        else:
            return self.m("board", "wrapper", center=center, view0=self._player_view(0), view1=self._player_view(1))