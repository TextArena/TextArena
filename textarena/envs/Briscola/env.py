import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class BriscolaEnv(ta.GameEnv):
    min_players = 2
    max_players = 4

    def __init__(self):
        """ Initializes the Briscola card game environment """
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
        pattern = re.compile(r"^\s*\[?\s*play\s+(\d+)\s*\]?\s*$", re.I)
        match = pattern.match(message)

        if match:
            try:
                return int(match.group(1)) - 1  # Convert to 0-based index
            except ValueError:
                return None
        return None

    def setup(self) -> Dict[str, Any]:
        """ Initialize and return the complete game state """
        gs = {
            'players': {},
            'deck': [],
            'trump_suit': None,
            'trump_card': None,
            'current_trick': [],
            'tricks_won': {},
            'points_won': {},
            'removed_cards': [],
            'phase': 'playing',  # playing, finished
            'trick_leader': 0,
            'cards_in_hand': 3
        }

        # Shuffle deck
        deck_copy = self.deck.copy()
        if self.state.num_players == 3:
            # A three-player deal needs 39 cards so every trick is complete.
            gs['removed_cards'] = [
                card for card in deck_copy
                if card['rank'] == '2' and card['suit'] == '♣'
            ]
            deck_copy = [
                card for card in deck_copy
                if not (card['rank'] == '2' and card['suit'] == '♣')
            ]
        self.rng.shuffle(deck_copy)

        # Deal round-robin, as cards are dealt at a real table.
        cards_per_hand = gs['cards_in_hand']
        for player_id in range(self.state.num_players):
            gs['players'][player_id] = {
                'hand': [],
                'points': 0
            }
            gs['tricks_won'][player_id] = []
            gs['points_won'][player_id] = 0
        for _ in range(cards_per_hand):
            for player_id in range(self.state.num_players):
                gs['players'][player_id]['hand'].append(deck_copy.pop())

        # Set trump card (last card dealt becomes trump indicator)
        if deck_copy:
            gs['trump_card'] = deck_copy.pop()
            gs['trump_suit'] = gs['trump_card']['suit']
            deck_copy.insert(0, gs['trump_card'])  # Put trump card at bottom of deck

        gs['deck'] = deck_copy
        return gs

    def on_start(self):
        """ Announce the start of the game with trump suit """
        gs = self.game_state
        trump_str = self._card_to_string(gs['trump_card']) if gs['trump_card'] else "None"

        self.broadcast(
            f"Briscola game started! Trump suit: {gs['trump_suit']} (Trump card: {trump_str})",
            ta.ObservationType.GAME_MESSAGE
        )

    def prompt(self, player_id: int) -> str:
        game_state = self.game_state
        return (
            f"You are playing Briscola - Player {player_id}.\n"
            f"Goal: Win tricks and collect the most points (120 total points in the deck).\n"
            f"Card Points: A=11, 3=10, K=4, Q=3, J=2, others=0\n"
            f"Card Power: A > 3 > K > Q > J > 7 > 6 > 5 > 4 > 2\n"
            f"Trump cards beat non-trump cards regardless of power.\n\n"
            f"Action: reply with 'play X' where X is the position (1-{len(game_state['players'][player_id]['hand']) if player_id in game_state['players'] else 3}) of the card in your hand\n"
        )

    def _render_player_hand(self, player_id: int) -> str:
        """ Renders the player's hand """
        gs = self.game_state
        if player_id not in gs['players']:
            return "No cards"

        player = gs['players'][player_id]
        hand = player['hand']

        if not hand:
            return "No cards in hand"

        output = []
        output.append("Your hand:")
        for i, card in enumerate(hand):
            trump_indicator = " (TRUMP)" if card['suit'] == gs['trump_suit'] else ""
            output.append(f"  {i+1}. {self._card_to_string(card)} [{card['points']} pts]{trump_indicator}")

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

    def render(self, player_id: int) -> str:
        """ The board shown to the player about to act """
        gs = self.game_state

        hand_str = self._render_player_hand(player_id)
        trick_str = self._render_current_trick()

        # Show current scores
        scores = []
        for pid in range(self.state.num_players):
            scores.append(f"Player {pid}: {gs['points_won'][pid]} pts")
        scores_str = " | ".join(scores)

        trump_info = f"Trump suit: {gs['trump_suit']}"
        if gs['deck']:
            trump_info += f" | Cards left in deck: {len(gs['deck'])}"

        return f"{hand_str}\n\n{trick_str}\n\nScores: {scores_str}\n{trump_info}\n\nPlay a card by replying 'play X'"

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

        # Play the card
        played_card = player['hand'].pop(card_index)
        gs['current_trick'].append((player_id, played_card))

        self.broadcast(
            f"Player {player_id} played {self._card_to_string(played_card)}",
            ta.ObservationType.GAME_ACTION_DESCRIPTION
        )

        # Check if trick is complete
        if len(gs['current_trick']) == len(self.state.alive_players):
            return self._resolve_trick()
        # Otherwise the default rotation moves to the next player.
        return None

    def _resolve_trick(self) -> Optional[ta.Outcome]:
        """ Resolve the completed trick """
        gs = self.game_state

        # Determine trick winner
        winner_id, winning_card = self._determine_trick_winner(gs['current_trick'], gs['trump_suit'])

        # Calculate points in this trick
        trick_points = sum(card['points'] for _, card in gs['current_trick'])

        # Award points and trick to winner
        gs['points_won'][winner_id] += trick_points
        gs['tricks_won'][winner_id].append(gs['current_trick'].copy())

        self.broadcast(
            f"Player {winner_id} wins the trick with {self._card_to_string(winning_card)} and gains {trick_points} points!",
            ta.ObservationType.GAME_MESSAGE
        )

        # Clear current trick
        gs['current_trick'] = []

        # The trick winner leads and draws first.
        gs['trick_leader'] = winner_id
        self._deal_new_cards()

        # Check for game end
        if self._is_game_over():
            return self._end_game()

        # Winner leads next trick
        self.set_next_player(winner_id)
        return None

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
        gs = self.game_state

        if not gs['deck']:
            return

        # Deal one card to each player, starting with trick winner
        players_to_deal = []
        start_player = gs['trick_leader']

        active_players = self.state.alive_players
        for i in range(self.state.num_players):
            player_id = (start_player + i) % self.state.num_players
            if player_id in active_players:
                players_to_deal.append(player_id)

        recipients = [
            player_id for player_id in players_to_deal
            if len(gs['players'][player_id]['hand']) < gs['cards_in_hand']
        ]
        if len(gs['deck']) < len(recipients):
            # Never create a partial final draw that leaves active players with
            # unequal hand sizes and an impossible trick.
            gs['removed_cards'].extend(gs['deck'])
            gs['deck'].clear()
            return
        for player_id in recipients:
            new_card = gs['deck'].pop()
            gs['players'][player_id]['hand'].append(new_card)

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """Remove a forfeiting hand without corrupting future trick sizes."""
        gs = self.game_state
        self.eliminate(player_id)
        gs['removed_cards'].extend(gs['players'][player_id]['hand'])
        gs['players'][player_id]['hand'] = []
        alive = self.state.alive_players
        if len(alive) <= 1:
            return self.winner(alive, reason=f"Player {player_id} made repeated invalid moves: {reason}")

        # Keep the number of still-playable cards divisible into complete
        # tricks for the remaining players. Excess stock is out of play.
        playable = (
            len(gs['deck'])
            + len(gs['current_trick'])
            + sum(len(gs['players'][pid]['hand']) for pid in alive)
        )
        excess = playable % len(alive)
        while excess and gs['deck']:
            gs['removed_cards'].append(gs['deck'].pop())
            excess -= 1

        self.broadcast(
            f"Player {player_id} was eliminated for repeated invalid moves.",
            ta.ObservationType.GAME_ADMIN,
        )
        if len(gs['current_trick']) == len(alive):
            return self._resolve_trick()
        return None

    def _is_game_over(self) -> bool:
        """ Check if the game is over """
        gs = self.game_state

        # Game is over when all players have no cards left
        for player_id in self.state.alive_players:
            if gs['players'][player_id]['hand']:
                return False

        return True

    def _end_game(self) -> ta.Outcome:
        """ End the game and determine winner """
        gs = self.game_state
        gs['phase'] = 'finished'

        active_players = self.state.alive_players
        winner_points = max(gs['points_won'][pid] for pid in active_players)
        winners = [pid for pid in active_players if gs['points_won'][pid] == winner_points]
        winner_label = ", ".join(str(pid) for pid in winners)

        # Create final summary
        summary = f"Game Over! Player(s) {winner_label} finished with {winner_points} points!\n\nFinal Scores:\n"
        sorted_players = sorted(gs['points_won'].items(), key=lambda x: x[1], reverse=True)

        for player_id, points in sorted_players:
            tricks_count = len(gs['tricks_won'][player_id])
            summary += f"Player {player_id}: {points} points ({tricks_count} tricks)\n"

        if len(winners) == len(active_players):
            if len(active_players) == self.state.num_players:
                return self.draw(summary)
            rewards = {
                pid: (0 if pid in active_players else -1)
                for pid in range(self.state.num_players)
            }
            return self.outcome(rewards, summary)
        return self.winner(winners, summary)

    def get_board_str(self) -> str:
        """ Get a string representation of the current game state """
        gs = self.game_state
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
