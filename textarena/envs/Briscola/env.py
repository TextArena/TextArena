import random
import re
from typing import Optional, Tuple, List, Dict, Any

import textarena as ta

class BriscolaEnv(ta.Env):
    def __init__(self):
        """ Initializes the Briscola card game environment """
        super().__init__()
        self.deck = self._create_deck()
        
    def _create_deck(self) -> List[Dict[str, Any]]:
        """ Creates a 40-card Italian deck for Briscola """
        suits = ['♠', '♥', '♦', '♣']  # Spades, Hearts, Diamonds, Clubs
        ranks = ['A', '2', '3', '4', '5', '6', '7', 'J', 'Q', 'K']  # No 8, 9, 10 in Italian deck
        deck = []
        
        for suit in suits:
            for rank in ranks:
                card = {
                    'rank': rank,
                    'suit': suit,
                    'points': self._get_card_points(rank),
                    'power': self._get_card_power(rank)
                }
                deck.append(card)
        return deck
    
    def _get_card_points(self, rank: str) -> int:
        """ Returns the point value of a card in Briscola """
        point_values = {
            'A': 11,    # Ace
            '3': 10,    # Three
            'K': 4,     # King
            'Q': 3,     # Queen (Cavallo/Horse)
            'J': 2,     # Jack (Fante)
            '7': 0, '6': 0, '5': 0, '4': 0, '2': 0  # No points
        }
        return point_values[rank]
    
    def _get_card_power(self, rank: str) -> int:
        """ Returns the power/strength of a card for trick-taking (higher = stronger) """
        power_values = {
            'A': 8,     # Ace (strongest)
            '3': 7,     # Three
            'K': 6,     # King
            'Q': 5,     # Queen
            'J': 4,     # Jack
            '7': 3, '6': 2, '5': 1, '4': 0, '2': -1  # Weakest
        }
        return power_values[rank]
    
    def _card_to_string(self, card: Dict[str, Any]) -> str:
        """ Converts a card to a readable string """
        return f"{card['rank']}{card['suit']}"
    
    def _find_action_token(self, message: str) -> Optional[int]:
        """ Parse card play action from player message """
        pattern = re.compile(r"\[play (\d+)\]", re.I)
        match = pattern.search(message)
        
        if match:
            return int(match.group(1)) - 1  # Convert to 0-based index
        return None
    
    def reset(self, num_players: int = 2, seed: Optional[int] = None):
        """ Reset the game state """
        if num_players not in [2, 3, 4]:
            raise ValueError("Briscola supports 2, 3, or 4 players")
            
        if num_players == 2:
            self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)
        else:
            self.state = ta.FFAMultiPlayerState(num_players=num_players, seed=seed)
        
        # Initialize game state
        game_state = {
            'players': {},
            'deck': [],
            'trump_suit': None,
            'trump_card': None,
            'current_trick': [],
            'tricks_won': {},
            'points_won': {},
            'phase': 'playing',  # playing, finished
            'trick_leader': 0,
            'cards_in_hand': 3 if num_players <= 3 else 2
        }
        
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)
        self._init_game()
    
    def _init_game(self):
        """ Initialize the game """
        gs = self.state.game_state
        
        # Shuffle deck
        deck_copy = self.deck.copy()
        random.shuffle(deck_copy)
        
        # Deal cards to players
        cards_per_hand = gs['cards_in_hand']
        for player_id in range(self.state.num_players):
            player_hand = []
            for _ in range(cards_per_hand):
                if deck_copy:
                    player_hand.append(deck_copy.pop())
            
            gs['players'][player_id] = {
                'hand': player_hand,
                'points': 0
            }
            gs['tricks_won'][player_id] = []
            gs['points_won'][player_id] = 0
        
        # Set trump card (last card dealt becomes trump indicator)
        if deck_copy:
            gs['trump_card'] = deck_copy.pop()
            gs['trump_suit'] = gs['trump_card']['suit']
            deck_copy.insert(0, gs['trump_card'])  # Put trump card at bottom of deck
        
        gs['deck'] = deck_copy
        gs['current_trick'] = []
        gs['trick_leader'] = 0
        gs['phase'] = 'playing'
        
        # Announce game start
        self._announce_game_start()
        self._announce_turn(self.state.current_player_id)
    
    def _announce_game_start(self):
        """ Announce the start of the game with trump suit """
        gs = self.state.game_state
        trump_str = self._card_to_string(gs['trump_card']) if gs['trump_card'] else "None"

        self.state.add_observation(
            message=self.m("game", "start", trump_suit=gs['trump_suit'], trump_card=trump_str),
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
    
    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        max_pos = len(game_state['players'][player_id]['hand']) if player_id in game_state['players'] else 3
        return self.m("prompt", "intro", player_id=player_id, max_pos=max_pos)
    
    def _render_player_hand(self, player_id: int) -> str:
        """ Renders the player's hand """
        gs = self.state.game_state
        if player_id not in gs['players']:
            return self.m("hand", "none").render(_pid=player_id)

        player = gs['players'][player_id]
        hand = player['hand']

        if not hand:
            return self.m("hand", "empty").render(_pid=player_id)

        trump_mark = self.m("hand", "trump_mark").render(_pid=player_id)
        output = []
        output.append(self.m("hand", "header").render(_pid=player_id))
        for i, card in enumerate(hand):
            trump_indicator = trump_mark if card['suit'] == gs['trump_suit'] else ""
            output.append(self.m("hand", "card_line", pos=i + 1, card=self._card_to_string(card), points=card['points'], trump_mark=trump_indicator).render(_pid=player_id))

        return "\n".join(output)
    
    def _render_current_trick(self, recipient_id: int) -> str:
        """ Renders the current trick being played """
        gs = self.state.game_state
        if not gs['current_trick']:
            return self.m("trick", "empty").render(_pid=recipient_id)

        trump_mark = self.m("hand", "trump_mark").render(_pid=recipient_id)
        output = []
        output.append(self.m("trick", "header").render(_pid=recipient_id))
        for player_id, card in gs['current_trick']:
            trump_indicator = trump_mark if card['suit'] == gs['trump_suit'] else ""
            output.append(self.m("trick", "line", player_id=player_id, card=self._card_to_string(card), trump_mark=trump_indicator).render(_pid=recipient_id))

        return "\n".join(output)
    
    def step(self, action: str) -> Tuple[bool, ta.Info]:
        player_id = self.state.current_player_id
        gs = self.state.game_state
        
        self.state.add_observation(
            from_id=player_id, 
            message=action, 
            observation_type=ta.ObservationType.PLAYER_ACTION
        )
        
        # Parse action
        card_index = self._find_action_token(action)
        
        if card_index is None:
            self.state.set_invalid_move(self.m("invalid_move", "wrong_format"))
            return self.state.step()

        # Validate card index
        player = gs['players'][player_id]
        if card_index < 0 or card_index >= len(player['hand']):
            self.state.set_invalid_move(self.m("invalid_move", "out_of_range", count=len(player['hand'])))
            return self.state.step()

        # Play the card
        played_card = player['hand'].pop(card_index)
        gs['current_trick'].append((player_id, played_card))

        self.state.add_observation(
            message=self.m("action", "played", player_id=player_id, card=self._card_to_string(played_card)),
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )
        
        # Check if trick is complete
        if len(gs['current_trick']) == self.state.num_players:
            return self._resolve_trick()
        else:
            # Move to next player
            return self._next_player_in_trick()
    
    def _next_player_in_trick(self) -> Tuple[bool, ta.Info]:
        """ Move to the next player in the current trick """
        next_player = (self.state.current_player_id + 1) % self.state.num_players
        self.state.manually_set_current_player_id(next_player)
        
        self._announce_turn(next_player)
        return self.state.step(rotate_player=False)
    
    def _resolve_trick(self) -> Tuple[bool, ta.Info]:
        """ Resolve the completed trick """
        gs = self.state.game_state
        
        # Determine trick winner
        winner_id, winning_card = self._determine_trick_winner(gs['current_trick'], gs['trump_suit'])
        
        # Calculate points in this trick
        trick_points = sum(card['points'] for _, card in gs['current_trick'])
        
        # Award points and trick to winner
        gs['points_won'][winner_id] += trick_points
        gs['tricks_won'][winner_id].append(gs['current_trick'].copy())
        
        self.state.add_observation(
            message=self.m("action", "trick_win", winner=winner_id, card=self._card_to_string(winning_card), points=trick_points),
            observation_type=ta.ObservationType.GAME_MESSAGE
        )
        
        # Clear current trick
        gs['current_trick'] = []
        
        # Deal new cards if deck has cards
        self._deal_new_cards()
        
        # Check for game end
        if self._is_game_over():
            return self._end_game()
        
        # Winner leads next trick
        gs['trick_leader'] = winner_id
        self.state.manually_set_current_player_id(winner_id)
        
        self._announce_turn(winner_id)
        return self.state.step(rotate_player=False)
    
    def _determine_trick_winner(self, trick: List[Tuple[int, Dict]], trump_suit: str) -> Tuple[int, Dict]:
        """ Determine who wins the trick """
        if not trick:
            return 0, {}
        
        # Get the lead card (first card played) and lead suit
        lead_player_id, lead_card = trick[0]
        lead_suit = lead_card['suit']
        
        # Separate trump cards from non-trump cards
        trump_cards = [(pid, card) for pid, card in trick if card['suit'] == trump_suit]
        
        # Rule 1: If there are trump cards, highest trump wins
        if trump_cards:
            winner_id, winning_card = max(trump_cards, key=lambda x: x[1]['power'])
            return winner_id, winning_card
        
        # Rule 2: No trump cards played
        # Find all cards that follow the lead suit
        lead_suit_cards = [(pid, card) for pid, card in trick if card['suit'] == lead_suit]
        
        if lead_suit_cards:
            # If there are cards following suit, highest power of lead suit wins
            winner_id, winning_card = max(lead_suit_cards, key=lambda x: x[1]['power'])
            return winner_id, winning_card
        else:
            # This shouldn't happen in normal Briscola play since the lead card 
            # should always be in lead_suit_cards, but as a safety fallback:
            return lead_player_id, lead_card
    
    def _deal_new_cards(self):
        """ Deal new cards to players after a trick """
        gs = self.state.game_state
        
        if not gs['deck']:
            return
        
        # Deal one card to each player, starting with trick winner
        players_to_deal = []
        start_player = gs['trick_leader']
        
        for i in range(self.state.num_players):
            player_id = (start_player + i) % self.state.num_players
            players_to_deal.append(player_id)
        
        for player_id in players_to_deal:
            if gs['deck'] and len(gs['players'][player_id]['hand']) < gs['cards_in_hand']:
                new_card = gs['deck'].pop()
                gs['players'][player_id]['hand'].append(new_card)
    
    def _is_game_over(self) -> bool:
        """ Check if the game is over """
        gs = self.state.game_state
        
        # Game is over when all players have no cards left
        for player in gs['players'].values():
            if player['hand']:
                return False
        
        return True
    
    def _end_game(self) -> Tuple[bool, ta.Info]:
        """ End the game and determine winner """
        gs = self.state.game_state
        gs['phase'] = 'finished'
        
        # Find winner (most points)
        winner_id = max(gs['points_won'].keys(), key=lambda pid: gs['points_won'][pid])
        winner_points = gs['points_won'][winner_id]
        
        # Create final summary
        sorted_players = sorted(gs['points_won'].items(), key=lambda x: x[1], reverse=True)

        scores = "".join(
            self.m("outcome", "player_line", player_id=player_id, points=points, tricks=len(gs['tricks_won'][player_id])).render()
            for player_id, points in sorted_players
        )
        summary = self.m("outcome", "head", winner=winner_id, points=winner_points, scores=scores)
        
        if self.state.num_players == 2:
            # Set winner for two-player game
            self.state.set_winner(winner_id, summary)
        else:
            # For multiplayer, set outcome
            self.state.set_outcome(
                reward=1 if self.state.current_player_id == winner_id else 0,
                reason=summary
            )
        
        return self.state.step(rotate_player=False)
    
    def _announce_turn(self, player_id: int):
        """ Announce the current player's turn """
        gs = self.state.game_state
        
        hand_str = self._render_player_hand(player_id)
        trick_str = self._render_current_trick(player_id)

        # Show current scores
        scores = []
        for pid in range(self.state.num_players):
            scores.append(self.m("turn", "score_entry", player_id=pid, points=gs['points_won'][pid]).render(_pid=player_id))
        scores_str = " | ".join(scores)

        if gs['deck']:
            trump_info = self.m("turn", "trump_info_deck", trump_suit=gs['trump_suit'], deck_count=len(gs['deck'])).render(_pid=player_id)
        else:
            trump_info = self.m("turn", "trump_info", trump_suit=gs['trump_suit']).render(_pid=player_id)

        self.state.add_observation(
            to_id=player_id,
            message=self.m("turn", "board", hand=hand_str, trick=trick_str, scores=scores_str, trump_info=trump_info),
            observation_type=ta.ObservationType.GAME_BOARD
        )
    
    def get_board_str(self) -> str:
        """ Get a string representation of the current game state """
        gs = self.state.game_state
        if not gs:
            return "Game not started"
            
        output = []
        output.append("=== BRISCOLA GAME ===")
        output.append(f"Trump suit: {gs['trump_suit']}")
        
        if gs['trump_card']:
            output.append(f"Trump card: {self._card_to_string(gs['trump_card'])}")
        
        output.append(f"Cards left in deck: {len(gs['deck'])}")
        output.append("")
        
        # Current trick
        if gs['current_trick']:
            output.append("Current trick:")
            for player_id, card in gs['current_trick']:
                trump_indicator = " (TRUMP)" if card['suit'] == gs['trump_suit'] else ""
                output.append(f"  Player {player_id}: {self._card_to_string(card)}{trump_indicator}")
            output.append("")
        
        # Player information
        for player_id in range(self.state.num_players):
            if player_id in gs['players']:
                player = gs['players'][player_id]
                hand_size = len(player['hand'])
                points = gs['points_won'][player_id]
                tricks = len(gs['tricks_won'][player_id])
                
                output.append(f"Player {player_id}: {points} points, {tricks} tricks, {hand_size} cards in hand")
        
        return "\n".join(output)