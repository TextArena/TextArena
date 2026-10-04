import re
from typing import Any, Dict, List, Optional, Tuple, Union

import textarena as ta


class GolfEnv(ta.GameEnv):
    min_players = 2
    max_players = 4

    def __init__(self, num_cards: int = 6, num_columns: int = 3):
        """ Initializes the Golf card game environment """
        if not isinstance(num_cards, int) or isinstance(num_cards, bool) or not 2 <= num_cards <= 12:
            raise ValueError("num_cards must be an integer between 2 and 12")
        if not isinstance(num_columns, int) or isinstance(num_columns, bool) or num_columns < 1:
            raise ValueError("num_columns must be a positive integer")
        if num_cards % num_columns != 0:
            raise ValueError("num_cards must be divisible by num_columns")
        self.num_cards = num_cards
        self.num_columns = num_columns
        self.num_rows = num_cards // num_columns
        self.deck = self._create_deck()

    def _create_deck(self) -> List[Dict[str, Any]]:
        """ Creates a standard 52-card deck """
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        deck = []

        if self.num_cards <= 6:
            num_decks = 1
        elif self.num_cards <= 9:
            num_decks = 2
        elif self.num_cards <= 12:
            num_decks = 3

        for _ in range(num_decks):
            for suit in suits:
                for rank in ranks:
                    deck.append({'rank': rank, 'suit': suit, 'value': self._get_card_value(rank)})
        return deck

    def _get_card_value(self, rank: str) -> int:
        """ Returns the point value of a card in Golf """
        if rank == 'A':
            return 1
        elif rank in ['J', 'Q']:
            return 10
        elif rank == 'K':
            return 0  # Kings are worth 0 in Golf
        else:
            return int(rank)

    def _card_to_string(self, card: Dict[str, Any]) -> str:
        return f"{card['rank']}{card['suit']}"

    def _find_action_token(self, message: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
        """ Parse action from player message using regex patterns """
        patterns = [
            ("draw", re.compile(r"^\s*\[?\s*draw\s*\]?\s*$", re.I)),
            ("take", re.compile(r"^\s*\[?\s*take\s*\]?\s*$", re.I)),
            ("swap", re.compile(r"^\s*\[?\s*swap\s+(\d+)\s+(\d+)\s*\]?\s*$", re.I)),
            ("discard", re.compile(r"^\s*\[?\s*discard\s*\]?\s*$", re.I)),
            ("knock", re.compile(r"^\s*\[?\s*knock\s*\]?\s*$", re.I)),
            ("peek", re.compile(r"^\s*\[?\s*peek\s+(\d+)\s+(\d+)\s*\]?\s*$", re.I))
        ]

        found = [(name, m) for name, rx in patterns if (m := rx.search(message))]
        if len(found) != 1:
            return None, None  # none or ambiguous

        action_name, match = found[0]
        params = {}

        if action_name in ("swap", "peek"):
            try:
                params['row'] = int(match.group(1))
                params['col'] = int(match.group(2))
            except ValueError:
                return None, None

        return action_name, params

    def setup(self) -> Dict[str, Any]:
        num_players = self.state.num_players
        deck_copy = self.deck.copy()
        self.rng.shuffle(deck_copy)

        # Reveal 1/3 of each player's cards at random positions
        cards_to_reveal = self.num_cards // 3

        players = {}
        for player_id in range(num_players):
            positions_to_reveal = self.rng.sample(range(self.num_cards), cards_to_reveal)
            player_cards = [
                {'card': deck_copy.pop(), 'revealed': i in positions_to_reveal, 'peeked': False}
                for i in range(self.num_cards)
            ]
            players[player_id] = {'cards': player_cards, 'score': 0}

        discard_pile = [deck_copy.pop()]

        return {
            'players': players,
            'deck': deck_copy,
            'discard_pile': discard_pile,
            'current_phase': 'playing',  # playing, final_round, finished
            'knocker': None,
            'triggering_player': None,
            'final_turns_remaining': None,
            'turn_phase': 'draw'  # draw, action_with_card
        }

    def prompt(self, player_id: int) -> str:
        return (
            f"You are playing Golf (Card Game) - Player {player_id}.\n"
            f"Goal: Get the lowest total score in this single round. If columns share the same value, they are summed as 0.\n"
            f"Card Values: A=1, 2-10=face value, J/Q=10, K=0\n\n"
            f"Actions (reply with exactly one):\n"
            f"- 'draw' - Draw from deck\n"
            f"- 'take' - Take from discard pile\n"
            f"- 'swap X Y' - Swap drawn card with position X (row) Y (column)\n"
            f"- 'discard' - Discard the drawn card\n"
            f"- 'knock' - End your turn and give each opponent one final turn\n"
            f"- 'peek X Y' - Privately inspect one face-down card during final turns\n"
        )

    def _render_player_hand(self, player_id: int, viewer_id: Optional[int] = None) -> str:
        """ Renders the player's hand in a grid format """
        if player_id not in self.game_state['players']: return "No cards"

        cards = self.game_state['players'][player_id]['cards']
        output = ["  Col: " + " ".join(f"{col:>4}" for col in range(1, self.num_columns + 1))]

        for row in range(self.num_rows):
            row_str = f"Row {row + 1}: "
            for col in range(self.num_columns):
                card_idx = row * self.num_columns + col
                if card_idx < len(cards):
                    card_info = cards[card_idx]
                    visible = card_info['revealed'] or (
                        viewer_id == player_id and card_info.get('peeked', False)
                    )
                    card_str = f"{self._card_to_string(card_info['card']):>4}" if visible else "  ? "
                    row_str += f"{card_str} "
                else:
                    row_str += "     "
            output.append(row_str)

        return "\n".join(output)

    def render(self, player_id: int) -> str:
        """ Announce hand / available actions to the player about to act """
        gs = self.game_state
        boards = [f"Your hand:\n{self._render_player_hand(player_id, viewer_id=player_id)}"]
        for opponent_id in sorted(pid for pid in gs['players'] if pid != player_id):
            boards.append(
                f"Player {opponent_id}'s public cards:\n"
                f"{self._render_player_hand(opponent_id, viewer_id=player_id)}"
            )
        hand_str = "\n\n".join(boards)
        discard_top = self._card_to_string(gs['discard_pile'][-1]) if gs['discard_pile'] else "None"

        if gs['current_phase'] == 'finished':
            options = "Game finished."
        elif gs['turn_phase'] == 'draw':
            if gs['current_phase'] == 'final_round':
                options = "Final turns! Your options: 'draw', 'take', 'peek X Y'"
            else:
                options = "Your options: 'draw', 'take', 'knock'"
        else:  # action_with_card phase
            if gs.get('took_from_discard', False):
                options = "You must: 'swap X Y' (cannot discard cards from discard pile)"
            else:
                options = "You must: 'swap X Y' or 'discard'"

        drawn = ""
        if gs['turn_phase'] == 'action_with_card' and 'drawn_card' in gs:
            drawn = f"\nYour drawn card: {self._card_to_string(gs['drawn_card'])}"
        return f"{hand_str}\nDiscard pile: {discard_top}{drawn}\n{options}"

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        action_name, params = self._find_action_token(action)

        if action_name is None:
            return self.invalid("Use exactly ONE action: 'draw', 'take', 'swap X Y', 'discard', 'knock', or 'peek X Y'")

        if self.game_state['turn_phase'] == 'draw':
            return self._handle_draw_phase(player_id, action_name, params)
        elif self.game_state['turn_phase'] == 'action_with_card':
            return self._handle_action_phase(player_id, action_name, params)

    def _handle_draw_phase(self, player_id: int, action_name: str, params: Dict) -> Union[ta.Outcome, ta.Invalid, None]:
        """ Handle actions when player needs to draw or take a card """
        gs = self.game_state
        if action_name == 'draw':
            if not gs['deck']:
                # Deck is empty - trigger immediate game end
                self.broadcast("Deck is empty! Game ends immediately.", ta.ObservationType.GAME_MESSAGE)
                return self._end_game()

            drawn_card = gs['deck'].pop()
            gs['drawn_card'] = drawn_card
            gs['turn_phase'] = 'action_with_card'
            self.message(player_id, f"You drew: {self._card_to_string(drawn_card)}\nNow you must 'swap X Y' or 'discard' it.", ta.ObservationType.GAME_MESSAGE)
            self.set_next_player(player_id)  # same player finishes the turn
            return None

        elif action_name == 'take':
            if not gs['discard_pile']:
                return self.invalid("The discard pile is empty!")

            drawn_card = gs['discard_pile'].pop()
            gs['drawn_card'] = drawn_card
            gs['turn_phase'] = 'action_with_card'
            gs['took_from_discard'] = True
            self.message(player_id, f"You took: {self._card_to_string(drawn_card)} from discard pile\nYou must 'swap X Y' with it (cannot discard).", ta.ObservationType.GAME_MESSAGE)
            self.set_next_player(player_id)  # same player finishes the turn
            return None

        elif action_name == 'knock':
            if gs['current_phase'] != 'playing':
                return self.invalid("The final round has already started.")
            gs['knocker'] = player_id
            return self._trigger_final_round(player_id, "knocked")

        elif action_name == 'peek':
            if gs['current_phase'] != 'final_round':
                return self.invalid("You may only peek during the final round.")
            row, col = params['row'], params['col']
            if row < 1 or row > self.num_rows or col < 1 or col > self.num_columns:
                return self.invalid(
                    f"Position out of bounds. Use row 1-{self.num_rows}, "
                    f"column 1-{self.num_columns}"
                )
            card_idx = (row - 1) * self.num_columns + (col - 1)
            card_info = gs['players'][player_id]['cards'][card_idx]
            if card_info['revealed']:
                return self.invalid("That card is already face up.")
            if card_info.get('peeked', False):
                return self.invalid("You already peeked at that card.")
            card_info['peeked'] = True
            self.message(
                player_id,
                f"You privately peeked at {self._card_to_string(card_info['card'])} "
                f"at position ({row},{col}).",
                ta.ObservationType.GAME_MESSAGE,
            )
            return self._next_turn()

        else:
            return self.invalid("You must first 'draw', 'take', 'knock', or 'peek X Y'")

    def _handle_action_phase(self, player_id: int, action_name: str, params: Dict) -> Union[ta.Outcome, ta.Invalid, None]:
        """ Handle actions when player has a drawn card """
        if action_name == 'swap':
            return self._handle_swap(player_id, params)
        elif action_name == 'discard':
            # Can only discard if card was drawn from deck (not discard pile)
            if self.game_state.get('took_from_discard', False):
                return self.invalid("You cannot discard a card taken from the discard pile. You must swap it.")
            return self._handle_discard_drawn(player_id)
        else:
            return self.invalid("You have a drawn card. You must 'swap X Y' or 'discard' it.")

    def _handle_swap(self, player_id: int, params: Dict) -> Union[ta.Outcome, ta.Invalid, None]:
        """ Handle swapping drawn card with a position """
        gs = self.game_state
        if 'drawn_card' not in gs:
            return self.invalid("You need a drawn card to swap.")

        row, col = params['row'], params['col']
        if row < 1 or row > self.num_rows or col < 1 or col > self.num_columns:
            return self.invalid(f"Position out of bounds. Use row 1-{self.num_rows}, column 1-{self.num_columns}")

        card_idx = (row - 1) * self.num_columns + (col - 1)
        player = gs['players'][player_id]

        old_card = player['cards'][card_idx]['card']
        player['cards'][card_idx]['card'] = gs['drawn_card']
        player['cards'][card_idx]['revealed'] = True

        gs['discard_pile'].append(old_card)
        self.broadcast(f"Player {player_id} swapped {self._card_to_string(gs['drawn_card'])} with {self._card_to_string(old_card)} at position ({row},{col})", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        del gs['drawn_card']
        gs['took_from_discard'] = False

        if self._player_has_all_cards_revealed(player_id):
            return self._trigger_final_round(player_id, "has all cards revealed")
        return self._next_turn()

    def _handle_discard_drawn(self, player_id: int) -> Union[ta.Outcome, ta.Invalid, None]:
        """ Handle discarding the drawn card """
        gs = self.game_state
        if 'drawn_card' not in gs:
            return self.invalid("You need a drawn card to discard.")

        discarded_card = gs['drawn_card']
        gs['discard_pile'].append(discarded_card)
        self.broadcast(f"Player {player_id} discarded {self._card_to_string(discarded_card)}", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        del gs['drawn_card']
        gs['took_from_discard'] = False

        if self._player_has_all_cards_revealed(player_id):
            return self._trigger_final_round(player_id, "has all cards revealed")
        return self._next_turn()

    def _player_has_all_cards_revealed(self, player_id: int) -> bool:
        if player_id not in self.game_state['players']: return False
        return all(card_info['revealed'] for card_info in self.game_state['players'][player_id]['cards'])

    def _trigger_final_round(self, triggering_player: int, reason: str) -> Optional[ta.Outcome]:
        """ Trigger the final round when a condition is met """
        gs = self.game_state
        if gs['current_phase'] == 'final_round':
            return self._next_turn()  # already in final round, just continue

        gs['current_phase'] = 'final_round'
        gs['triggering_player'] = triggering_player
        gs['final_turns_remaining'] = max(0, len(self.state.alive_players) - 1)
        self.broadcast(f"Player {triggering_player} {reason}! Each other player gets one more turn.", ta.ObservationType.GAME_MESSAGE)
        return self._next_turn(count_final_turn=False)

    def _next_turn(self, count_final_turn: bool = True) -> Optional[ta.Outcome]:
        """ Finish the current player's turn and check for end conditions """
        gs = self.game_state
        gs['turn_phase'] = 'draw'

        # The player who drew the final stock card may finish placing it, but
        # no extra dummy turn should be required to discover the empty deck.
        if not gs['deck']:
            self.broadcast("Deck is empty! Game ends immediately.", ta.ObservationType.GAME_MESSAGE)
            return self._end_game()

        # Check if final round is complete
        if gs['current_phase'] == 'final_round':
            if count_final_turn:
                gs['final_turns_remaining'] -= 1
            if gs['final_turns_remaining'] <= 0:
                return self._end_game()

        return None  # default rotation moves to the next player

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        """Forfeit an eliminated player's pending final turn exactly once."""
        self.eliminate(player_id)
        alive = self.state.alive_players
        if len(alive) <= 1:
            return self.winner(alive, reason=f"Player {player_id} made repeated invalid moves: {reason}")

        gs = self.game_state
        if gs['current_phase'] == 'final_round':
            gs['final_turns_remaining'] -= 1
            if gs['final_turns_remaining'] <= 0:
                return self._end_game()
        self.broadcast(
            f"Player {player_id} was eliminated for repeated invalid moves.",
            ta.ObservationType.GAME_ADMIN,
        )
        return None

    def _end_game(self) -> ta.Outcome:
        """ End the game and determine winner """
        gs = self.game_state
        gs['current_phase'] = 'finished'
        # Reveal all cards and calculate final scores with column matching
        for player_id, player in gs['players'].items():
            for card_info in player['cards']:
                card_info['revealed'] = True

            total_score = 0
            for col in range(self.num_columns):
                column_values = []
                for row in range(self.num_rows):
                    card_idx = row * self.num_columns + col
                    if card_idx < len(player['cards']):
                        column_values.append(player['cards'][card_idx]['card']['value'])

                if len(set(column_values)) == 1 and len(column_values) > 1:
                    column_score = 0  # all cards in the column match
                else:
                    column_score = sum(column_values)
                total_score += column_score

            player['score'] = total_score

        # Find winner(s) among players still in the game (lowest score).
        active_players = self.state.alive_players
        winner_score = min(gs['players'][pid]['score'] for pid in active_players)
        winners = [pid for pid in active_players if gs['players'][pid]['score'] == winner_score]
        winner_label = ", ".join(str(pid) for pid in winners)

        summary = f"Game Over! Player(s) {winner_label} finished with {winner_score} points!\n\nFinal Scores:\n"
        for player_id, player in sorted(gs['players'].items(), key=lambda x: x[1]['score']):
            summary += f"Player {player_id}: {player['score']} points\n"

        if len(winners) == len(active_players):
            if len(active_players) == self.state.num_players:
                return self.draw(reason=summary)
            rewards = {
                pid: (0 if pid in active_players else -1)
                for pid in range(self.state.num_players)
            }
            return self.outcome(rewards, reason=summary)
        return self.winner(winners, reason=summary)

    def get_board_str(self) -> str:
        """ Get a string representation of the current game state """
        if not self.state.game_state:
            return "Game not started"
        output = []
        output.append("=== GOLF GAME ===")
        if self.state.game_state['discard_pile']: output.append(f"Discard pile: {self._card_to_string(self.state.game_state['discard_pile'][-1])}")
        if self.state.game_state['knocker'] is not None: output.append(f"Player {self.state.game_state['knocker']} has knocked!")
        output.append("")
        for player_id, player in self.state.game_state['players'].items():
            output.append(f"Player {player_id} (Score: {player['score']}):")
            output.append(self._render_player_hand(player_id, viewer_id=None))
            output.append("")
        return "\n".join(output)
