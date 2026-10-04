import re
from enum import Enum
from typing import Any, Dict, Optional, List, Union

import textarena as ta
from textarena.envs.Hanabi.renderer import create_board_str

class Suit(Enum):
    """
    Enum for representing suits.
    """
    WHITE = "white"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    RED = "red"


class Card:
    """
    A simple class for representing a Hanabi card.
    """
    def __init__(self, suit: Suit, rank: int):
        assert 1 <= rank <= 5, f"The rank should be between 1 and 5, received {rank}."
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return f"a {self.suit.value} card with rank {self.rank}"

    def __eq__(self, other):
        if not isinstance(other, Card):
            return NotImplemented
        return self.rank == other.rank and self.suit == other.suit


class HanabiEnv(ta.GameEnv):
    min_players = 2
    max_players = 5
    broadcast_actions = False  # raw actions are echoed only to their author
    error_allowance = 1
    _play_pattern = re.compile(r"^\s*\[?\s*play\s+([0-9]{1,6})\s*\]?\s*$", re.IGNORECASE)
    _discard_pattern = re.compile(r"^\s*\[?\s*discard\s+([0-9]{1,6})\s*\]?\s*$", re.IGNORECASE)
    _reveal_pattern = re.compile(
        r"^\s*\[?\s*reveal\s+player\s+([0-9]{1,6})\s+card\s+"
        r"([0-9]{1,6})\s+(color|rank)\s+([a-z0-9]+)\s*\]?\s*$",
        re.IGNORECASE,
    )

    def __init__(self, info_tokens: int = 8, fuse_tokens: int = 4,):
        if not isinstance(info_tokens, int) or isinstance(info_tokens, bool) or info_tokens < 0:
            raise ValueError("info_tokens must be a non-negative integer")
        if not isinstance(fuse_tokens, int) or isinstance(fuse_tokens, bool) or fuse_tokens < 1:
            raise ValueError("fuse_tokens must be a positive integer")
        self.deck_size = 50
        self.info_tokens = info_tokens
        self.fuse_tokens = fuse_tokens

    def setup(self) -> Dict[str, Any]:
        self.num_players = self.state.num_players
        self.hand_size = 5 if self.num_players <= 3 else 4  # The hand size is 5 for 2-3 players, and 4 for 4-5 players
        self.deck = self._generate_deck()
        return {
            "info_tokens": self.info_tokens,
            "fuse_tokens": self.fuse_tokens,
            "fireworks": {
                Suit.WHITE: 0,
                Suit.YELLOW: 0,
                Suit.GREEN: 0,
                Suit.BLUE: 0,
                Suit.RED: 0,
            },
            "deck_size": self.deck_size,
            "deck": self.deck,
            "player_hands": {
                player: self.generate_hand(self.deck) for player in range(self.num_players)
            },
            "discard_pile": [],
            "last_round": -1,
        }

    def get_board_str(self) -> str:
        """Get the string representing the Hanabi board."""
        return create_board_str(game_state=self.state.game_state)

    def prompt(self, player_id: int) -> str:
        return (
        f"You are Player {player_id} in an {self.state.num_players}-player Hanabi game. "
        f"Hanabi is a cooperative card game where players work together to create a series of fireworks by playing "
        f"cards in ascending numerical order starting from 1. Each player holds their cards facing outward so that all "
        f"players can see everyone else's cards but not their own.\n\n"

        f"Objective:\n"
        f"The objective is to play cards in sequence (1 through 5) for each color without making mistakes. "
        f"There are 5 different colors and each color has cards numbered 1 to 5.\n\n"

        f"Key Rules:\n"
        "On your turn, you have three types of possible actions:\n"

        "1. Give a Hint (Reveal): Provide a hint to another player about their cards, specifying either a color or a"
            " number present in their hand. Hints must be accurate and can only reveal positions of cards matching the "
            "hint.\n"
        "2. Discard a Card: Discard one of your own cards to potentially gain an Info token.\n"
        "3. Play a Card: Attempt to play a card from your hand. If played correctly in sequence, it adds to the "
            "fireworks; if not, it reduces one fuse token.\n\n"

        "Tokens:\n"
        "Fuse Tokens: Deducted when a wrong card is played.\n"
        "Info Tokens: Used to give clues.\n\n"

        "Illegal Moves:\n"
        "Playing a card that cannot be placed properly costs a fuse token. If fuse tokens reach zero, the game ends in "
        "failure.\n\n"

        "Game End:\n"
        "The game ends when all fireworks are completed (perfect score of 25), or when the deck is exhausted "
        "and each player has taken one final turn, or when the players run out of fuse tokens.\n\n"

        "State Representation:\n"
        "The game state is represented with the following details:\n"

        "Fuse tokens: Number of remaining fuse tokens.\n"
        "Info tokens: Number of available information tokens.\n"
        "Fireworks: Current progress on each firework color.\n"
        "Discards: Cards that have been discarded.\n\n"

        "Your Role:\n"
        "You are one of the players, cooperating with others to maximize the total score of the fireworks "
        "(the number of cards correctly played in sequence).\n"
        "Although you cannot see your own cards, you can see the cards in the hands of your teammates.\n"
        "Use hints, discards, and plays strategically to guide the team towards successful sequences.\n"

        "When it's your turn, your output should be in one of the following formats between quotes:\n\n"

        "'Reveal player N card X color C', to give a hint about color C of card X to the player at index N.\n"
        "'Reveal player N card X rank R', to give hint about rank R of card X to the player at index N.\n"
        "'Play X', to play the card in position X from your hand.\n"
        "'Discard X', to discard the card in position X from your hand.\n\n"

        "Remember, communication is limited to hints about colors or numbers only, and sharing illegal or extraneous "
        "information is not allowed. Work together, follow the rules, and aim for the highest cooperative score possible!\n\n"
        )

    def render(self, player_id: int) -> str:
        """
        Generate a string describing the current game state, as seen by `player_id`.
        """
        gs = self.game_state
        discard_pile = "".join(str(card) + "\n" for card in gs['discard_pile'])
        visible_cards = ""

        for other_id in range(self.num_players):
            if other_id == player_id:
                continue
            else:
                visible_cards += f"- Player {other_id} has cards:\n"
                for i, card in enumerate(gs['player_hands'][other_id]):
                    if card is not None:
                        visible_cards += f"\tcard {i}: {card}\n"

        return (
            f"You are player {player_id}. \n\n"
            f"Current game state:\n"
            f"Fuse tokens: there are {gs['fuse_tokens']} fuse tokens remaining.\n"
            f"Info tokens: there are {gs['info_tokens']} info tokens remaining.\n\n"
            f"Fireworks: The current progress on each firework color is:\n"
            f"\t{Suit.WHITE.value}: {gs['fireworks'][Suit.WHITE]}.\n"
            f"\t{Suit.YELLOW.value}: {gs['fireworks'][Suit.YELLOW]}.\n"
            f"\t{Suit.GREEN.value}: {gs['fireworks'][Suit.GREEN]}.\n"
            f"\t{Suit.BLUE.value}: {gs['fireworks'][Suit.BLUE]}.\n"
            f"\t{Suit.RED.value}: {gs['fireworks'][Suit.RED]}.\n\n"
            f"Your teammates have the following cards in their hand:\n"
            f"{visible_cards}\n"
            f"Discards: The following cards have been discarded:\n"
            f"{discard_pile}\n"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        reveal_match = self._reveal_pattern.fullmatch(action)
        play_match = self._play_pattern.fullmatch(action)
        discard_match = self._discard_pattern.fullmatch(action)
        if reveal_match:
            result = self._handle_reveal(player_id, reveal_match)
        elif play_match:
            result = self._handle_play(player_id, play_match)
        elif discard_match:
            result = self._handle_discard(player_id, discard_match)
        else:
            return self.invalid("The player provided an invalid action. Players can only 'reveal', 'play' or 'discard'.")

        if isinstance(result, ta.Invalid):
            return result
        return self._check_game_end()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # A player who exhausts the error allowance skips a turn (cooperative game: nobody is eliminated).
        outcome = self._check_game_end()
        if outcome is not None:
            return outcome
        message = (f"Player {player_id} made {self.state.error_allowance + 1} "
                   f"invalid moves in a row, skipping a turn. ")
        self.broadcast(message, ta.ObservationType.GAME_MESSAGE, from_id=player_id)
        self.state.game_info[player_id]["invalid_move"] = False  # a skipped turn is not a terminal invalid move
        self.set_next_player((player_id + 1) % self.num_players)
        return None

    def _handle_discard(self, player_id: int, match: re.Match) -> Optional[ta.Invalid]:
        """
        Handle a player's attempt to discard a card.
        """
        gs = self.game_state
        if gs["info_tokens"] >= self.info_tokens:
            return self.invalid(
                "You cannot discard while all information tokens are available."
            )
        card_idx = int(match.group(1))
        hand = gs['player_hands'][player_id]
        if card_idx >= len(hand):
            return self.invalid(
                f"Card {card_idx} does not exist; choose an index between 0 and {len(hand) - 1}."
            )

        card = hand.pop(card_idx)
        message = f"Player {player_id} discards {card}."
        gs['discard_pile'].append(card)

        if gs['info_tokens'] < self.info_tokens:
            gs['info_tokens'] += 1
            message += " This replenishes an info token."
        else:
            message += " This does not replenish an info token as the token cap is reached."

        self.broadcast(message, ta.ObservationType.GAME_MESSAGE, from_id=player_id)
        replacement = self._draw_card(gs['deck'])
        if replacement is not None:
            hand.append(replacement)
        return None

    def _handle_play(self, player_id: int, match: re.Match) -> Optional[ta.Invalid]:
        """
        Handle a player's attempt to play a card.
        """
        gs = self.game_state
        card_idx = int(match.group(1))
        hand = gs['player_hands'][player_id]
        if card_idx >= len(hand):
            return self.invalid(
                f"Card {card_idx} does not exist; choose an index between 0 and {len(hand) - 1}."
            )

        card = hand.pop(card_idx)
        action_description = f"Player {player_id} attempts to play {card}."
        if self._play(card):
            if card.rank == 5 and gs['info_tokens'] < self.info_tokens:
                gs['info_tokens'] += 1
                action_description += " Completing a firework replenishes one info token."
            self.broadcast(
                action_description + " The card was played successfully.",
                ta.ObservationType.GAME_MESSAGE,
                from_id=player_id,
            )
        else:
            gs['fuse_tokens'] -= 1
            message = (
                action_description
                + " The card did not match the current state of the fireworks. This costs one fuse token."
                + f" There are {gs['fuse_tokens']} fuse tokens remaining."
            )
            self.broadcast(message, ta.ObservationType.GAME_MESSAGE, from_id=player_id)
            gs['discard_pile'].append(card)

        replacement = self._draw_card(gs['deck'])
        if replacement is not None:
            hand.append(replacement)
        return None

    def _handle_reveal(self, player_id: int, match: re.Match) -> Optional[ta.Invalid]:
        """
        Handle a player's attempt to reveal a card.
        """
        gs = self.game_state
        if gs['info_tokens'] == 0:  # Invalid action, no info tokens left
            return self.invalid("Player attempted to give a hint without having any info tokens.")

        target_player = int(match.group(1))
        card_index = int(match.group(2))
        hint_type = match.group(3).lower()
        hint_value = match.group(4).lower()
        invalid = self.check_valid_move(player_id, target_player, card_index, hint_type, hint_value)
        if invalid is not None:
            return invalid

        target_hand = gs["player_hands"][target_player]
        if hint_type == "color":
            matching_indices = [
                idx for idx, card in enumerate(target_hand)
                if card.suit.value == hint_value
            ]
            hint = (
                f"All {hint_value} cards in Player {target_player}'s hand are at "
                f"indices {matching_indices}."
            )
        else:  # The player gave a hint about the rank
            rank = int(hint_value)
            matching_indices = [
                idx for idx, card in enumerate(target_hand) if card.rank == rank
            ]
            hint = (
                f"All rank {rank} cards in Player {target_player}'s hand are at "
                f"indices {matching_indices}."
            )

        gs['info_tokens'] = gs['info_tokens'] - 1
        self.broadcast(hint, ta.ObservationType.GAME_MESSAGE, from_id=player_id)
        return None

    def check_valid_move(
        self,
        player_id: int,
        target_player: int,
        card_index: int,
        hint_type: str,
        hint_value: str,
    ) -> Optional[ta.Invalid]:
        """
        Check the validity of the reveal move. Returns ``None`` if the move is valid, else an ``Invalid``.
        """
        if target_player == player_id:
            return self.invalid("The player attempts to reveal information about their own cards.")
        if target_player >= self.num_players:
            return self.invalid("The player attempts to reveal information about a non-existing teammate.")

        target_hand = self.game_state['player_hands'][target_player]
        if card_index >= len(target_hand):
            return self.invalid("The player attempts to reveal information about a non-existing card.")

        card = target_hand[card_index]
        if hint_type == "color":
            try:
                color = Suit(hint_value)
            except ValueError:
                return self.invalid("The player provided a color that is not in the game.")
            if card.suit != color:
                return self.invalid("The color hint does not match the selected card.")
        else:
            try:
                rank = int(hint_value)
            except ValueError:
                return self.invalid("The player provided an invalid rank format.")
            if rank < 1 or rank > 5:
                return self.invalid("The player provided a rank outside the range 1 to 5.")
            if card.rank != rank:
                return self.invalid("The rank hint does not match the selected card.")
        return None

    def _play(self, card: Card) -> bool:
        """
        Verifies whether the played ``card`` matches the current state of the fireworks, and updates the current state.
        Returns ``False`` if the ``card`` cannot be played, ``True`` otherwise.
        """
        rocket = self.game_state['fireworks'][card.suit]

        if rocket == card.rank - 1:  # Valid play, update the fireworks
            self.game_state['fireworks'][card.suit] += 1
            return True

        return False  # Invalid play

    def _check_game_end(self) -> Optional[ta.Outcome]:
        """
        Check whether the game has ended. Later conditions take precedence, matching the legacy check order.
        """
        gs = self.game_state
        outcome = None

        # Losing conditions
        if len(gs['deck']) == 0:  # The deck has run out
            if gs['last_round'] == -1:  # Start the last round
                self.broadcast("There are no cards left in the deck. This is the final round.", ta.ObservationType.GAME_MESSAGE)
                gs['last_round'] = self.state.current_player_id
            elif gs['last_round'] == self.state.current_player_id:  # End the last round
                score = self._calculate_scores()
                outcome = self.outcome(
                    {pid: score / 25 for pid in range(self.num_players)},
                    reason=f"The deck has run out. Final team score: {score}/25.",
                )

        if gs['fuse_tokens'] <= 0:  # There are no fuse tokens left
            outcome = self.outcome(
                {pid: 0.0 for pid in range(self.num_players)},
                reason="The team ran out of fuse tokens. Final team score: 0/25.",
            )

        # Winning condition
        if self._completed_fireworks():
            outcome = self.winner(list(range(self.num_players)), reason="All 5s have been played successfully.")

        return outcome

    def _completed_fireworks(self) -> bool:
        """
        Check whether all rockets are complete.
        """
        for rocket in self.game_state['fireworks'].keys():
            if self.game_state['fireworks'][rocket] < 5:
                return False
        return True

    def _calculate_scores(self) -> int:
        """
        Calculate the scores based on the status of the fireworks.
        """
        return sum([x for x in self.game_state['fireworks'].values()])

    @staticmethod
    def _generate_deck() -> List[Card]:
        """
        Generate a deck of 50 cards. The deck contains 5 suits, white, yellow, blue, green and red; and 5 ranks. Of each
        suit, there are three 1s, two of each 2s, 3s and 4s, and one 5.
        """
        ranks = {1: 3, 2: 2, 3: 2, 4: 2, 5: 1}
        deck = []

        for suit in Suit:
            for rank in ranks.keys():
                for q in range(ranks[rank]):
                    deck.append(Card(suit=suit, rank=rank))

        return deck

    def generate_hand(self, deck: List[Card]) -> List[Card]:
        """
        Draw ``self.hand_size`` random cards from ``deck``, removing them from the deck.
        """
        return [self._draw_card(deck) for _ in range(self.hand_size)]

    def _draw_card(self, deck: List[Card]) -> Optional[Card]:
        """
        Draw a random card from the ``deck``. Returns ``None`` if there are no cards left.
        """
        if len(deck) > 0:
            return deck.pop(self.rng.randrange(len(deck)))
        else:
            return None
