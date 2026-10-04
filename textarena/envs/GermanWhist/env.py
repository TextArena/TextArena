import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class GermanWhistEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    mdp_includes_actions = False

    def __init__(self):
        """ Initializes the German Whist card game environment """
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
        pattern = re.compile(r"^play\s+(\d+)$", re.I)
        match = pattern.match(message)

        if match:
            try:
                return int(match.group(1)) - 1  # Convert to 0-based index
            except ValueError:
                return None
        return None

    def setup(self) -> Dict[str, Any]:
        """ Initialize and return the complete game state """
        # Shuffle deck
        deck_copy = self.deck.copy()
        self.rng.shuffle(deck_copy)

        # Deal 13 cards to each player, round-robin.
        players = {player_id: {'hand': []} for player_id in range(2)}
        for _ in range(13):
            for player_id in range(2):
                players[player_id]['hand'].append(deck_copy.pop())

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
            'completed_tricks': [],
            'tricks_won': {0: 0, 1: 0},  # both phases, for display only
            'playing_tricks_won': {0: 0, 1: 0},  # only these decide the game
            'phase': 'learning',  # learning, playing, finished
            'trick_leader': 0,
            'next_card': next_card,  # The card that winner of trick will receive
            'tricks_in_learning': 0,
            'tricks_in_playing': 0
        }

    def on_start(self):
        """ Announce the start of the game with trump suit """
        gs = self.game_state
        trump_str = self._card_to_string(gs['trump_card']) if gs['trump_card'] else "None"

        self.broadcast(
            f"German Whist game started!\nTrump suit: {gs['trump_suit']} (Trump card: {trump_str})\n\nLEARNING PHASE: The trick winner takes the face-up card from the deck and the loser takes the next card face down (only the loser sees it); then the next card is turned face up. Tricks won in this phase do not count towards victory.",
            ta.ObservationType.GAME_MESSAGE
        )

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        phase_info = ""
        if game_state['phase'] == 'learning':
            phase_info = "LEARNING PHASE: Win tricks to get the visible next card. You can see what you're competing for! These tricks do not count towards victory."
        else:
            phase_info = "PLAYING PHASE: No more cards to draw. Every trick from now on counts towards victory!"

        return (
            f"You are playing German Whist - Player {player_id}.\n"
            f"{phase_info}\n"
            f"Goal: Win the majority (7+) of the 13 playing-phase tricks. The first 13 tricks (learning phase) only decide who gets which cards.\n"
            f"Card Power: A > K > Q > J > 10 > 9 > 8 > 7 > 6 > 5 > 4 > 3 > 2\n"
            f"Trump cards beat non-trump cards. You must follow suit if possible.\n\n"
            f"Action: reply with 'play X' where X is the position (1-{len(game_state['players'][player_id]['hand']) if player_id in game_state['players'] else 13}) of the card in your hand\n"
        )

    def _render_player_hand(self, player_id: int) -> str:
        """ Renders the player's hand organized by suit """
        gs = self.game_state
        if player_id not in gs['players']:
            return "No cards"

        player = gs['players'][player_id]
        hand = player['hand']

        if not hand:
            return "No cards in hand"

        # Group cards by suit for better readability
        suits_order = [gs['trump_suit']] + [suit for suit in ['♠', '♥', '♦', '♣'] if suit != gs['trump_suit']]

        output = []
        output.append("Your hand:")

        for suit in suits_order:
            suit_cards = [(i, card) for i, card in enumerate(hand) if card['suit'] == suit]
            if suit_cards:
                # Sort by power within suit
                suit_cards.sort(key=lambda x: x[1]['power'], reverse=True)

                trump_indicator = " (TRUMP)" if suit == gs['trump_suit'] else ""
                output.append(f"  {suit}{trump_indicator}:")

                for original_index, card in suit_cards:
                    # Find the actual position in the hand for the play command
                    actual_position = hand.index(card) + 1
                    output.append(f"    {actual_position}. {self._card_to_string(card)}")

        return "\n".join(output)

    def _render_current_trick(self) -> str:
        """ Renders the current trick being played """
        gs = self.game_state
        if not gs['current_trick']:
            return "No cards played yet this trick."

        output = []
        output.append("Current trick:")
        for player_id, card in gs['current_trick']:
            trump_indicator = " (TRUMP)" if card['suit'] == gs['trump_suit'] else ""
            output.append(f"  Player {player_id}: {self._card_to_string(card)}{trump_indicator}")

        return "\n".join(output)

    def _render_next_card_info(self) -> str:
        """ Renders information about the next card to be won """
        gs = self.game_state

        if gs['phase'] != 'learning':
            return "PLAYING PHASE: No more cards to draw from deck."

        if not gs['next_card']:
            return "No more cards in deck."

        trump_indicator = " (TRUMP)" if gs['next_card']['suit'] == gs['trump_suit'] else ""
        return f"Next card for trick winner: {self._card_to_string(gs['next_card'])}{trump_indicator}"

    def render(self, player_id: int) -> str:
        """ The board shown to the player about to act """
        gs = self.game_state

        hand_str = self._render_player_hand(player_id)
        trick_str = self._render_current_trick()
        next_card_str = self._render_next_card_info()

        # Show current score
        if gs['phase'] == 'learning':
            scores_str = f"Learning-phase tricks (do not count) - Player 0: {gs['tricks_won'][0]} | Player 1: {gs['tricks_won'][1]}"
        else:
            scores_str = f"Scoring tricks - Player 0: {gs['playing_tricks_won'][0]} | Player 1: {gs['playing_tricks_won'][1]}"

        # Phase information
        phase_str = f"Phase: {gs['phase'].upper()}"
        if gs['phase'] == 'learning':
            remaining_cards = len(gs['deck'])
            phase_str += f" ({remaining_cards} cards left in deck)"

        message_parts = [hand_str, "", trick_str, "", next_card_str, "", scores_str, phase_str, "", "Play a card by replying 'play X'"]
        return "\n".join(message_parts)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state

        # Parse action
        card_index = self._find_action_token(action)

        if card_index is None:
            return self.invalid("Reply with 'play X' where X is the card position (1, 2, 3, etc.)")

        # Validate card index
        player = gs['players'][player_id]
        if card_index < 0 or card_index >= len(player['hand']):
            return self.invalid(f"Invalid card position. You have {len(player['hand'])} cards (1-{len(player['hand'])})")

        played_card = player['hand'][card_index]

        # Validate suit following rules
        if not self._is_valid_play(player_id, played_card):
            lead_suit = gs['current_trick'][0][1]['suit']
            return self.invalid(f"You must follow suit ({lead_suit}) if you have cards of that suit!")

        # Play the card
        player['hand'].pop(card_index)
        gs['current_trick'].append((player_id, played_card))

        self.broadcast(
            f"Player {player_id} played {self._card_to_string(played_card)}",
            ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

        # Check if trick is complete
        if len(gs['current_trick']) == 2:
            return self._resolve_trick()
        # Otherwise the default rotation moves to the other player.
        return None

    def _is_valid_play(self, player_id: int, played_card: Dict[str, Any]) -> bool:
        """ Check if the played card follows suit rules """
        gs = self.game_state

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

    def _resolve_trick(self) -> Optional[ta.Outcome]:
        """ Resolve the completed trick """
        gs = self.game_state

        # Determine trick winner
        winner_id, winning_card = self._determine_trick_winner(gs['current_trick'], gs['trump_suit'])
        loser_id = 1 - winner_id

        # Award trick to winner
        gs['tricks_won'][winner_id] += 1

        if gs['phase'] == 'learning':
            gs['tricks_in_learning'] += 1
        else:
            gs['tricks_in_playing'] += 1
            gs['playing_tricks_won'][winner_id] += 1

        self.broadcast(
            f"Player {winner_id} wins the trick with {self._card_to_string(winning_card)}!",
            ta.ObservationType.GAME_MESSAGE
        )

        # Preserve played cards so all 52 physical cards remain accounted for.
        gs['completed_tricks'].append(gs['current_trick'].copy())
        gs['current_trick'] = []

        # Handle card distribution in learning phase
        if gs['phase'] == 'learning' and gs['deck']:
            self._handle_learning_phase_cards(winner_id, loser_id)

        # Check for phase transition
        if gs['phase'] == 'learning' and not gs['deck']:
            gs['phase'] = 'playing'
            self.broadcast(
                f"LEARNING PHASE COMPLETE! No more cards to draw.\nPLAYING PHASE: Every remaining trick counts towards victory. Win as many as possible with your current hand!",
                ta.ObservationType.GAME_MESSAGE
            )

        # Check for game end
        if self._is_game_over():
            return self._end_game()

        # Winner leads next trick
        gs['trick_leader'] = winner_id
        self.set_next_player(winner_id)
        return None

    def _handle_learning_phase_cards(self, winner_id: int, loser_id: int):
        """ Handle card distribution during learning phase """
        gs = self.game_state

        if not gs['deck']:
            return

        # Winner gets the face-up card (next_card), which both players have seen
        if gs['next_card']:
            gs['players'][winner_id]['hand'].append(gs['next_card'])
            self.broadcast(
                f"Player {winner_id} takes the face-up {self._card_to_string(gs['next_card'])}; "
                f"Player {loser_id} draws the next card face down.",
                ta.ObservationType.GAME_MESSAGE
            )

        # Remove the card from deck
        if gs['deck']:
            gs['deck'].pop()

        # Loser gets the next card (now face-down)
        if gs['deck']:
            loser_card = gs['deck'].pop()
            gs['players'][loser_id]['hand'].append(loser_card)

            self.message(
                loser_id,
                f"You received a face-down card: {self._card_to_string(loser_card)}",
                ta.ObservationType.GAME_MESSAGE
            )

            # The next stock card is turned face up for both players
            if gs['deck']:
                gs['next_card'] = gs['deck'][-1]
                self.broadcast(
                    f"The next face-up card is {self._card_to_string(gs['next_card'])}.",
                    ta.ObservationType.GAME_MESSAGE
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
        gs = self.game_state

        # Game is over when all players have no cards left
        for player in gs['players'].values():
            if player['hand']:
                return False

        return True

    def _end_game(self) -> ta.Outcome:
        """ End the game and determine winner """
        gs = self.game_state
        gs['phase'] = 'finished'

        # Only the 13 playing-phase tricks count, so a complete game cannot tie.
        player_0_tricks = gs['playing_tricks_won'][0]
        player_1_tricks = gs['playing_tricks_won'][1]

        if player_0_tricks > player_1_tricks:
            winner_id = 0
        elif player_1_tricks > player_0_tricks:
            winner_id = 1
        else:
            winner_id = None

        # Create final summary
        summary = "Game Over! Only the playing-phase tricks count towards victory.\n\n"
        summary += "Final Score (playing phase):\n"
        summary += f"Player 0: {player_0_tricks} tricks ({gs['tricks_won'][0]} including the learning phase)\n"
        summary += f"Player 1: {player_1_tricks} tricks ({gs['tricks_won'][1]} including the learning phase)\n\n"

        if winner_id is not None:
            summary += f"Player {winner_id} wins with {gs['playing_tricks_won'][winner_id]} scoring tricks!"
            return self.winner(winner_id, summary)
        else:
            summary += "It's a tie!"
            return self.draw(reason=summary)

    def get_board_str(self) -> str:
        """ Get a string representation of the current game state """
        gs = self.game_state
        if not gs:
            return "Game not started"

        output = []
        output.append("=== GERMAN WHIST GAME ===")
        output.append(f"Phase: {gs['phase'].upper()}")
        output.append(f"Trump suit: {gs['trump_suit']}")

        if gs['trump_card']:
            output.append(f"Trump card: {self._card_to_string(gs['trump_card'])}")

        if gs['phase'] == 'learning':
            output.append(f"Cards left in deck: {len(gs['deck'])}")
            if gs['next_card']:
                output.append(f"Next card for winner: {self._card_to_string(gs['next_card'])}")

        output.append("")

        # Current trick
        if gs['current_trick']:
            output.append("Current trick:")
            for player_id, card in gs['current_trick']:
                trump_indicator = " (TRUMP)" if card['suit'] == gs['trump_suit'] else ""
                output.append(f"  Player {player_id}: {self._card_to_string(card)}{trump_indicator}")
            output.append("")

        # Player information
        for player_id in range(2):
            if player_id in gs['players']:
                player = gs['players'][player_id]
                hand_size = len(player['hand'])
                tricks = gs['tricks_won'][player_id]
                scoring = gs['playing_tricks_won'][player_id]

                output.append(f"Player {player_id}: {scoring} scoring tricks ({tricks} total), {hand_size} cards in hand")

        return "\n".join(output)
