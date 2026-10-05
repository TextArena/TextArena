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
    mdp_includes_actions = False
    broadcast_actions = False  # raw actions are echoed only to their author
    error_allowance = 1
    _play_pattern = re.compile(r"^play\s+([0-9]{1,6})$", re.IGNORECASE)
    _discard_pattern = re.compile(r"^discard\s+([0-9]{1,6})$", re.IGNORECASE)
    _reveal_pattern = re.compile(
        r"^reveal\s+player\s+([0-9]{1,6})\s+card\s+"
        r"([0-9]{1,6})\s+(color|rank)\s+([a-z0-9]+)$",
        re.IGNORECASE,
    )

    info_tokens = ta.Param(8, "The starting and maximum number of information tokens.", min=1)
    fuse_tokens = ta.Param(3, "The number of fuse tokens; the game is lost when the last one is used.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.deck_size = 50

    def setup(self) -> Dict[str, Any]:
        self.num_players = self.state.num_players
        self.hand_size = 5 if self.num_players <= 3 else 4  # The hand size is 5 for 2-3 players, and 4 for 4-5 players
        self.deck = self._generate_deck()
        hands = {player: self.generate_hand(self.deck) for player in range(self.num_players)}
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
            "player_hands": hands,
            # What each player has been told about each card in their hand, aligned with player_hands.
            "hints": {player: [self._no_hints() for _ in hand] for player, hand in hands.items()},
            "discard_pile": [],
            "last_round": -1,
            "skips_in_a_row": 0,  # turns skipped for repeated invalid moves since the last valid action
        }

    @staticmethod
    def _no_hints() -> Dict[str, Any]:
        return {"color": None, "rank": None, "not_colors": [], "not_ranks": []}

    @staticmethod
    def _hint_text(knowledge: Dict[str, Any]) -> str:
        known = " ".join(str(value) for value in (knowledge["color"], knowledge["rank"]) if value is not None)
        excluded = [] if knowledge["color"] else list(knowledge["not_colors"])
        excluded += [] if knowledge["rank"] else [str(rank) for rank in knowledge["not_ranks"]]
        parts = ([f"known: {known}"] if known else []) + ([f"not {', '.join(excluded)}"] if excluded else [])
        return "; ".join(parts) if parts else "no hints"

    def get_board_str(self) -> str:
        """Get the string representing the Hanabi board."""
        return create_board_str(game_state=self.state.game_state)

    def prompt(self, player_id: int) -> str:
        return (
        f"You are Player {player_id} in a {self.state.num_players}-player Hanabi game. "
        f"Hanabi is a cooperative card game where players work together to create a series of fireworks by playing "
        f"cards in ascending numerical order starting from 1. Each player holds their cards facing outward so that all "
        f"players can see everyone else's cards but not their own.\n\n"

        f"Objective:\n"
        f"The objective is to play cards in sequence (1 through 5) for each color without making mistakes. "
        f"There are 5 different colors (white, yellow, green, blue, red); each color has three 1s, two each of 2s, "
        f"3s and 4s, and one 5.\n\n"

        f"Key Rules:\n"
        "On your turn, you have three types of possible actions:\n"

        "1. Give a Hint (Reveal): Provide a hint to another player about their cards, specifying either a color or a"
            " number present in their hand. Hints must be accurate and reveal the positions of all of their cards "
            "matching the hint. A hint costs one info token.\n"
        f"2. Discard a Card: Discard one of your own cards to regain one info token. Discarding is not allowed "
            f"while all {self.info_tokens} info tokens are available.\n"
        "3. Play a Card: Attempt to play a card from your hand. If played correctly in sequence, it adds to the "
            "fireworks; if not, it is discarded and the team loses one fuse token. Completing a firework with its 5 "
            "returns one info token.\n"
        "After playing or discarding you draw a new card while the deck lasts.\n\n"

        "Tokens:\n"
        f"Fuse Tokens: The team starts with {self.fuse_tokens}; one is lost for every wrong card played.\n"
        f"Info Tokens: The team starts with {self.info_tokens} (the maximum); they are used to give clues.\n\n"

        "Card positions:\n"
        "Cards in a hand are numbered from 0. A newly drawn card goes to the end of the hand, and the cards after "
        "a played or discarded card move down one position.\n\n"

        "Misplays:\n"
        "Playing a card that cannot be placed on its firework is a legal move, but the card is discarded and it costs "
        "a fuse token. If fuse tokens reach zero, the game ends in failure with a score of 0.\n\n"

        "Invalid Replies:\n"
        f"A reply that is not a valid action is rejected. {self.error_allowance + 1} invalid replies in a row skip "
        "your turn; if every player skips a turn in a row, the game ends with the current score.\n\n"

        "Game End:\n"
        "The game ends when all fireworks are completed (perfect score of 25), or when the deck is exhausted "
        "and each player has taken one final turn, or when the players run out of fuse tokens. "
        "The team score is the number of cards played on the fireworks.\n\n"

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
                        visible_cards += f"\tcard {i}: {card} (their hints: {self._hint_text(gs['hints'][other_id][i])})\n"

        own_hints = gs['hints'][player_id]
        own_cards = "".join(f"\tcard {i}: {self._hint_text(knowledge)}\n" for i, knowledge in enumerate(own_hints))
        final_round = (
            f"The deck is empty: this is the final round, which ends after Player {gs['last_round']}'s turn.\n"
            if gs['last_round'] != -1 else ""
        )
        return (
            f"You are player {player_id}. \n\n"
            f"Current game state:\n"
            f"Fuse tokens: there are {gs['fuse_tokens']} fuse tokens remaining.\n"
            f"Info tokens: there are {gs['info_tokens']} info tokens remaining.\n"
            f"Deck: there are {len(gs['deck'])} cards left to draw.\n{final_round}\n"
            f"Your hand: you hold {len(own_hints)} cards (positions 0 to {len(own_hints) - 1}) that you cannot see. "
            f"What the hints so far have told you:\n{own_cards}\n"
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
        self.game_state["skips_in_a_row"] = 0
        return self._check_game_end()

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        # A player who exhausts the error allowance skips a turn (cooperative game: nobody is eliminated).
        outcome = self._check_game_end()
        if outcome is not None:
            return outcome
        gs = self.game_state
        gs["skips_in_a_row"] += 1
        if gs["skips_in_a_row"] >= self.num_players:
            # Skipped turns change nothing, so a full round of them would repeat forever.
            score = self._calculate_scores()
            return self.outcome(
                {pid: score / 25 for pid in range(self.num_players)},
                reason=f"Every player skipped a turn in a row for repeated invalid moves, so the game ends. "
                       f"Final team score: {score}/25.",
            )
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

        card = self._remove_card(player_id, card_idx)
        message = f"Player {player_id} discards {card}."
        gs['discard_pile'].append(card)

        if gs['info_tokens'] < self.info_tokens:
            gs['info_tokens'] += 1
            message += " This replenishes an info token."
        else:
            message += " This does not replenish an info token as the token cap is reached."

        self.broadcast(message, ta.ObservationType.GAME_MESSAGE, from_id=player_id)
        self._draw_replacement(player_id)
        return None

    def _remove_card(self, player_id: int, card_idx: int) -> Card:
        self.game_state['hints'][player_id].pop(card_idx)
        return self.game_state['player_hands'][player_id].pop(card_idx)

    def _draw_replacement(self, player_id: int):
        replacement = self._draw_card(self.game_state['deck'])
        if replacement is not None:
            self.game_state['player_hands'][player_id].append(replacement)
            self.game_state['hints'][player_id].append(self._no_hints())

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

        card = self._remove_card(player_id, card_idx)
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

        self._draw_replacement(player_id)
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
            known_key, excluded_key, value = "color", "not_colors", hint_value
            order = [suit.value for suit in Suit]
        else:  # The player gave a hint about the rank
            rank = int(hint_value)
            matching_indices = [
                idx for idx, card in enumerate(target_hand) if card.rank == rank
            ]
            hint = (
                f"All rank {rank} cards in Player {target_player}'s hand are at "
                f"indices {matching_indices}."
            )
            known_key, excluded_key, value = "rank", "not_ranks", rank
            order = [1, 2, 3, 4, 5]

        for idx, knowledge in enumerate(gs["hints"][target_player]):
            if idx in matching_indices:
                knowledge[known_key] = value
            elif value not in knowledge[excluded_key]:
                knowledge[excluded_key] = sorted(knowledge[excluded_key] + [value], key=order.index)

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
        Check whether the game has ended. Later conditions take precedence.
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
