import random
import re
from typing import Optional, Tuple, List, Dict, Any

import textarena as ta

class GermanWhistEnv(ta.Env):
    def __init__(self):
        """ Initializes the German Whist card game environment """
        super().__init__()
        self.deck = self._create_deck()

    def _create_deck(self) -> List[Dict[str, Any]]:
        """ Creates a standard 52-card deck for German Whist """
        suits = ['♠', '♥', '♦', '♣']  # Spades, Hearts, Diamonds, Clubs
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = []

        for suit in suits:
            for rank in ranks:
                card = {
                    'rank': rank,
                    'suit': suit,
                    'power': self._get_card_power(rank)
                }
                deck.append(card)
        return deck

    def _get_card_power(self, rank: str) -> int:
        """ Returns the power/strength of a card (higher = stronger) """
        power_values = {
            '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
            '9': 9, '10': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
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
        if num_players != 2:
            raise ValueError("German Whist is a two-player game only")

        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed)

        # Initialize game state BEFORE calling state.reset()
        game_state = self._init_game_state()

        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)

        # Announce game start and first turn
        self._announce_game_start()
        self._announce_turn(self.state.current_player_id)

    def _init_game_state(self) -> Dict[str, Any]:
        """ Initialize and return the complete game state """
        # Shuffle deck
        deck_copy = self.deck.copy()
        random.shuffle(deck_copy)

        # Deal 13 cards to each player
        players = {}
        for player_id in range(2):
            player_hand = []
            for _ in range(13):
                if deck_copy:
                    player_hand.append(deck_copy.pop())

            players[player_id] = {
                'hand': player_hand
            }

        # Set trump card (next card after dealing)
        trump_card = None
        trump_suit = None
        next_card = None

        if deck_copy:
            trump_card = deck_copy.pop()
            trump_suit = trump_card['suit']
            # Put trump card back on top of remaining deck
            deck_copy.append(trump_card)

        # Set the next card (top of deck) that winner will get
        if deck_copy:
            next_card = deck_copy[-1]

        # Return complete game state
        return {
            'players': players,
            'deck': deck_copy,
            'trump_suit': trump_suit,
            'trump_card': trump_card,
            'current_trick': [],
            # Total tricks won across both phases (for display only)
            'tricks_won': {0: 0, 1: 0},
            # Tricks won during the playing phase (these decide the game)
            'playing_tricks_won': {0: 0, 1: 0},
            'phase': 'learning',  # learning, playing, finished
            'trick_leader': 0,
            'next_card': next_card,  # The card that winner of trick will receive
            'tricks_in_learning': 0,
            'tricks_in_playing': 0
        }

    def _announce_game_start(self):
        """ Announce the start of the game with trump suit """
        gs = self.state.game_state
        trump_str = self._card_to_string(gs['trump_card']) if gs['trump_card'] else self.m("game_start", "no_trump_card")

        self.state.add_observation(
            message=self.m("game_start", "intro", trump_suit=gs['trump_suit'], trump_str=trump_str),
            observation_type=ta.ObservationType.GAME_MESSAGE
        )

    def _generate_player_prompt(self, player_id: int, game_state: Dict[str, Any]) -> str:
        if game_state['phase'] == 'learning':
            phase_info = self.m("player_prompt", "phase_learning")
        else:
            phase_info = self.m("player_prompt", "phase_playing")

        hand_size = len(game_state['players'][player_id]['hand']) if player_id in game_state['players'] else 13
        return self.m("player_prompt", "intro", player_id=player_id, phase_info=phase_info, hand_size=hand_size)

    def _render_player_hand(self, player_id: int):
        """ Renders the player's hand organized by suit """
        gs = self.state.game_state
        if player_id not in gs['players']:
            return self.m("hand", "no_cards")

        player = gs['players'][player_id]
        hand = player['hand']

        if not hand:
            return self.m("hand", "no_cards_in_hand")

        # Group cards by suit for better readability
        suits_order = [gs['trump_suit']] + [suit for suit in ['♠', '♥', '♦', '♣'] if suit != gs['trump_suit']]

        output = self.m("hand", "header")

        for suit in suits_order:
            suit_cards = [(i, card) for i, card in enumerate(hand) if card['suit'] == suit]
            if suit_cards:
                # Sort by power within suit
                suit_cards.sort(key=lambda x: x[1]['power'], reverse=True)

                trump_indicator = self.m("hand", "trump_indicator") if suit == gs['trump_suit'] else ""
                output = self.m("hand", "suit_line", observation=output, suit=suit, trump_indicator=trump_indicator)

                for original_index, card in suit_cards:
                    output = self.m("hand", "card_line", observation=output, index=original_index + 1, card=self._card_to_string(card))

        return output

    def _render_current_trick(self):
        """ Renders the current trick being played """
        gs = self.state.game_state
        if not gs['current_trick']:
            return self.m("trick_view", "empty")

        output = self.m("trick_view", "header")
        for player_id, card in gs['current_trick']:
            trump_indicator = self.m("trick_view", "trump_indicator") if card['suit'] == gs['trump_suit'] else ""
            output = self.m("trick_view", "card_line", observation=output, player_id=player_id, card=self._card_to_string(card), trump_indicator=trump_indicator)

        return output

    def _render_next_card_info(self):
        """ Renders information about the next card to be won """
        gs = self.state.game_state

        if gs['phase'] != 'learning':
            return self.m("next_card", "playing_phase")

        if not gs['next_card']:
            return self.m("next_card", "deck_empty")

        if gs['next_card']['suit'] == gs['trump_suit']:
            return self.m("next_card", "available_trump", card=self._card_to_string(gs['next_card']))
        return self.m("next_card", "available", card=self._card_to_string(gs['next_card']))

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
            self.state.set_invalid_move(self.m("invalid_move", "bad_position", hand_size=len(player['hand'])))
            return self.state.step()

        played_card = player['hand'][card_index]

        # Validate suit following rules
        if not self._is_valid_play(player_id, played_card):
            lead_suit = gs['current_trick'][0][1]['suit'] if gs['current_trick'] else None
            if lead_suit:
                self.state.set_invalid_move(self.m("invalid_move", "must_follow_suit", lead_suit=lead_suit))
            else:
                self.state.set_invalid_move(self.m("invalid_move", "invalid_play"))
            return self.state.step()

        # Play the card
        player['hand'].pop(card_index)
        gs['current_trick'].append((player_id, played_card))

        self.state.add_observation(
            message=self.m("game_action", "played", player_id=player_id, card=self._card_to_string(played_card)),
            observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

        # Check if trick is complete
        if len(gs['current_trick']) == 2:
            return self._resolve_trick()
        else:
            # Move to next player
            return self._next_player_in_trick()

    def _is_valid_play(self, player_id: int, played_card: Dict[str, Any]) -> bool:
        """ Check if the played card follows suit rules """
        gs = self.state.game_state

        # If leading the trick, any card is valid
        if not gs['current_trick']:
            return True

        # Get the lead suit
        lead_suit = gs['current_trick'][0][1]['suit']

        # If playing same suit as lead, always valid
        if played_card['suit'] == lead_suit:
            return True

        # If playing different suit, must not have any cards of lead suit
        player = gs['players'][player_id]
        has_lead_suit = any(card['suit'] == lead_suit for card in player['hand'])

        return not has_lead_suit

    def _next_player_in_trick(self) -> Tuple[bool, ta.Info]:
        """ Move to the next player in the current trick """
        next_player = 1 - self.state.current_player_id  # Switch between 0 and 1
        self.state.manually_set_current_player_id(next_player)

        self._announce_turn(next_player)
        return self.state.step(rotate_player=False)

    def _resolve_trick(self) -> Tuple[bool, ta.Info]:
        """ Resolve the completed trick """
        gs = self.state.game_state

        # Determine trick winner
        winner_id, winning_card = self._determine_trick_winner(gs['current_trick'], gs['trump_suit'])
        loser_id = 1 - winner_id

        # Award trick to winner
        gs['tricks_won'][winner_id] += 1

        if gs['phase'] == 'learning':
            gs['tricks_in_learning'] += 1
            message = self.m("trick", "won_learning", winner_id=winner_id, card=self._card_to_string(winning_card))
        else:
            gs['tricks_in_playing'] += 1
            gs['playing_tricks_won'][winner_id] += 1
            message = self.m("trick", "won", winner_id=winner_id, card=self._card_to_string(winning_card))

        self.state.add_observation(
            message=message,
            observation_type=ta.ObservationType.GAME_MESSAGE
        )

        # Clear current trick
        gs['current_trick'] = []

        # Handle card distribution in learning phase
        if gs['phase'] == 'learning' and gs['deck']:
            self._handle_learning_phase_cards(winner_id, loser_id)

        # Check for phase transition
        if gs['phase'] == 'learning' and not gs['deck']:
            gs['phase'] = 'playing'
            self.state.add_observation(
                message=self.m("phase", "learning_complete"),
                observation_type=ta.ObservationType.GAME_MESSAGE
            )

        # Check for game end
        if self._is_game_over():
            return self._end_game()

        # Winner leads next trick
        gs['trick_leader'] = winner_id
        self.state.manually_set_current_player_id(winner_id)

        self._announce_turn(winner_id)
        return self.state.step(rotate_player=False)

    def _handle_learning_phase_cards(self, winner_id: int, loser_id: int):
        """ Handle card distribution during learning phase """
        gs = self.state.game_state

        if not gs['deck']:
            return

        # Winner gets the face-up card (next_card)
        if gs['next_card']:
            gs['players'][winner_id]['hand'].append(gs['next_card'])
            self.state.add_observation(
                to_id=winner_id,
                message=self.m("draw", "winner_received", card=self._card_to_string(gs['next_card'])),
                observation_type=ta.ObservationType.GAME_MESSAGE
            )

        # Remove the card from deck
        if gs['deck']:
            gs['deck'].pop()

        # Loser gets the next card (now face-down)
        if gs['deck']:
            loser_card = gs['deck'].pop()
            gs['players'][loser_id]['hand'].append(loser_card)

            self.state.add_observation(
                to_id=loser_id,
                message=self.m("draw", "loser_received", card=self._card_to_string(loser_card)),
                observation_type=ta.ObservationType.GAME_MESSAGE
            )

            # Winner gets to see what the next card will be
            if gs['deck']:
                gs['next_card'] = gs['deck'][-1]
                self.state.add_observation(
                    to_id=winner_id,
                    message=self.m("draw", "winner_preview", card=self._card_to_string(gs['next_card'])),
                    observation_type=ta.ObservationType.GAME_MESSAGE
                )
            else:
                gs['next_card'] = None
        else:
            gs['next_card'] = None

    def _determine_trick_winner(self, trick: List[Tuple[int, Dict]], trump_suit: str) -> Tuple[int, Dict]:
        """ Determine who wins the trick """
        if not trick:
            return 0, {}

        # Get the lead suit (first card played)
        lead_suit = trick[0][1]['suit']

        # Separate trump cards from non-trump cards
        trump_cards = [(pid, card) for pid, card in trick if card['suit'] == trump_suit]
        non_trump_cards = [(pid, card) for pid, card in trick if card['suit'] != trump_suit]

        # If there are trump cards, highest trump wins
        if trump_cards:
            winner_id, winning_card = max(trump_cards, key=lambda x: x[1]['power'])
            return winner_id, winning_card

        # No trump cards: highest card of lead suit wins
        lead_suit_cards = [(pid, card) for pid, card in non_trump_cards if card['suit'] == lead_suit]

        if lead_suit_cards:
            winner_id, winning_card = max(lead_suit_cards, key=lambda x: x[1]['power'])
            return winner_id, winning_card

        # Fallback (shouldn't happen in normal play)
        return trick[0][0], trick[0][1]

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

        # Only playing-phase tricks count. 13 tricks, so no tie is possible.
        p0_playing = gs['playing_tricks_won'][0]
        p1_playing = gs['playing_tricks_won'][1]

        winner_id = 0 if p0_playing > p1_playing else 1

        summary = self.m(
            "outcome", "summary",
            l0=gs['tricks_won'][0] - p0_playing, l1=gs['tricks_won'][1] - p1_playing,
            p0=p0_playing, p1=p1_playing,
            winner_id=winner_id, winner_tricks=gs['playing_tricks_won'][winner_id]
        )

        self.state.set_winner(winner_id, summary)

        return self.state.step(rotate_player=False)

    def _announce_turn(self, player_id: int):
        """ Announce the current player's turn """
        gs = self.state.game_state

        hand_str = self._render_player_hand(player_id)
        trick_str = self._render_current_trick()
        next_card_str = self._render_next_card_info()

        # Show current score
        if gs['phase'] == 'learning':
            scores_str = self.m("turn", "scores_learning", tricks0=gs['tricks_won'][0], tricks1=gs['tricks_won'][1])
        else:
            scores_str = self.m("turn", "scores_playing", tricks0=gs['playing_tricks_won'][0], tricks1=gs['playing_tricks_won'][1])

        # Phase information
        if gs['phase'] == 'learning':
            phase_str = self.m("turn", "phase_learning", phase=gs['phase'].upper(), remaining_cards=len(gs['deck']))
        else:
            phase_str = self.m("turn", "phase", phase=gs['phase'].upper())

        message = self.m("turn", "board", hand=hand_str, trick=trick_str, next_card=next_card_str, scores=scores_str, phase=phase_str)

        self.state.add_observation(
            to_id=player_id,
            message=message,
            observation_type=ta.ObservationType.GAME_BOARD
        )

    def get_board_str(self):
        """ Get a string representation of the current game state """
        gs = self.state.game_state
        if not gs:
            return self.m("board_str", "not_started")

        output = self.m("board_str", "header")
        output = self.m("board_str", "phase", observation=output, phase=gs['phase'].upper())
        output = self.m("board_str", "trump_suit", observation=output, trump_suit=gs['trump_suit'])

        if gs['trump_card']:
            output = self.m("board_str", "trump_card", observation=output, card=self._card_to_string(gs['trump_card']))

        if gs['phase'] == 'learning':
            output = self.m("board_str", "cards_left", observation=output, count=len(gs['deck']))
            if gs['next_card']:
                output = self.m("board_str", "next_card", observation=output, card=self._card_to_string(gs['next_card']))

        output = self.m("board_str", "blank", observation=output)

        # Current trick
        if gs['current_trick']:
            output = self.m("board_str", "current_trick", observation=output)
            for player_id, card in gs['current_trick']:
                trump_indicator = self.m("board_str", "trump_indicator") if card['suit'] == gs['trump_suit'] else ""
                output = self.m("board_str", "trick_line", observation=output, player_id=player_id, card=self._card_to_string(card), trump_indicator=trump_indicator)
            output = self.m("board_str", "blank", observation=output)

        # Player information
        for player_id in range(2):
            if player_id in gs['players']:
                player = gs['players'][player_id]
                hand_size = len(player['hand'])
                tricks = gs['tricks_won'][player_id]
                scoring = gs['playing_tricks_won'][player_id]

                output = self.m("board_str", "player_line", observation=output, player_id=player_id, scoring=scoring, tricks=tricks, hand_size=hand_size)

        return output