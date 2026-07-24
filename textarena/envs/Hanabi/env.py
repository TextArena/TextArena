import re, random
from enum import Enum
from typing import Optional, Tuple, List

import textarena as ta
from textarena.core import GAME_ID
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
        return self.rank == other.rank and self.suit == other.suit


class HanabiEnv(ta.Env):
    def __init__(self, info_tokens: int = 8, fuse_tokens: int = 4,):

        self.deck_size = 50
        self.info_tokens = info_tokens
        self.fuse_tokens = fuse_tokens

    def reset(self, num_players: int, seed: Optional[int] = None):
        """
        Reset the state.

        Args:
            num_players (int): the number of players. Should be between 2 and 5.
            seed (Optional[int]): a random seed, used for drawing cards if provided.

        Returns:

        """
        assert num_players <= 5, f"Hanabi is played with 2 to 5 players, received {num_players} players."
        self.state = ta.TeamMultiPlayerState(num_players=num_players, seed=seed, error_allowance=1)
        self.num_players = num_players
        self.hand_size = 5 if num_players <= 3 else 4  # The hand size is 5 for 2-3 players, and 4 for 4-5 players
        self.deck = self._generate_deck()

        game_state = {
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
        self.state.reset(game_state=game_state, player_prompt_function=self._initial_prompt)

        # Inform player 0
        self.state.add_observation(to_id=self.state.current_player_id, message=self._state_description(),
                                   observation_type=ta.ObservationType.GAME_MESSAGE)

    def get_board_str(self) -> str:
        """Get the string representing the Hanabi board."""
        return create_board_str(game_state=self.state.game_state)

    def _initial_prompt(self, player_id: int, game_state: dict) -> str:
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

        "'[Reveal] player N card X color C', to give a hint about color C of card X to the player at index N.\n"
        "'[Reveal] player N card X rank R', to give hint about rank R of card X to the player at index N.\n"
        "'[Play] X', to play the card in position X from your hand.\n"
        "'[Discard] X', to discard the card in position X from your hand.\n\n"

        "Remember, communication is limited to hints about colors or numbers only, and sharing illegal or extraneous "
        "information is not allowed. Work together, follow the rules, and aim for the highest cooperative score possible!\n\n"
        )

    def _state_description(self):
        """
        Generate a string describing the current game state.

        Returns:
            str: a description of the current game state.
        """
        discard_pile = "".join(str(card) + "\n" for card in self.state.game_state['discard_pile'])
        visible_cards = ""

        for player_id in range(self.num_players):
            if player_id == self.state.current_player_id:
                continue
            else:
                visible_cards += f"- Player {player_id} has cards:\n"
                for i, card in enumerate(self.state.game_state['player_hands'][player_id]):
                    if card is not None:
                        visible_cards += f"\tcard {i}: {card}\n"

        return (
            f"You are player {self.state.current_player_id}. \n\n"
            f"Current game state:\n"
            f"Fuse tokens: there are {self.state.game_state['fuse_tokens']} fuse tokens remaining.\n"
            f"Info tokens: there are {self.state.game_state['info_tokens']} info tokens remaining.\n\n"
            f"Fireworks: The current progress on each firework color is:\n"
            f"\t{Suit.WHITE.value}: {self.state.game_state['fireworks'][Suit.WHITE]}.\n"
            f"\t{Suit.YELLOW.value}: {self.state.game_state['fireworks'][Suit.YELLOW]}.\n"
            f"\t{Suit.GREEN.value}: {self.state.game_state['fireworks'][Suit.GREEN]}.\n"
            f"\t{Suit.BLUE.value}: {self.state.game_state['fireworks'][Suit.BLUE]}.\n"
            f"\t{Suit.RED.value}: {self.state.game_state['fireworks'][Suit.RED]}.\n\n"
            f"Your teammates have the following cards in their hand:\n"
            f"{visible_cards}\n"
            f"Discards: The following cards have been discarded:\n"
            f"{discard_pile}\n"
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """
        Handle a game step.
        Args:
            action (str): the player's action.

        Returns:
            Tuple[bool, ta.Info]: information regarding the current game step.
        """
        self.state.add_observation(from_id=self.state.current_player_id, to_id=self.state.current_player_id,
                                   message=action, observation_type=ta.ObservationType.PLAYER_ACTION)
        # Parse the action:
        if re.compile(r"\[reveal\]", re.IGNORECASE).search(action):  # The action is [reveal]
            self._handle_reveal(action)

        elif re.compile(r"\[play\]", re.IGNORECASE).search(action):  # The action is [Play]
            self._handle_play(action)

        elif re.compile(r"\[discard\]", re.IGNORECASE).search(action):  # The action is [Discard]
            self._handle_discard(action)

        else: # Invalid action
            reason = r"The player provided an invalid action. Players can only '[reveal]', '[play]' or '[discard]'."
            self.state.set_invalid_move(reason=reason)

        # Check whether the game has ended
        self._check_game_end()

        # The player needs to skip a round because of making invalid moves
        if self.state.game_info[self.state.current_player_id]["invalid_move"]:
            message = (f"Player {self.state.current_player_id} made {self.state.error_allowance + 1} "
                       f"invalid moves in a row, skipping a turn. ")
            self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=message,
                                       observation_type=ta.ObservationType.GAME_MESSAGE)
            # Include the player for the next round
            self.state.game_info[self.state.current_player_id]["invalid_move"] = False
            self.state.made_invalid_move = False
            self.state.error_count = 0

        # Manually rotate the players (this functionality has not been added to the TeamMultiplayerState)
        self._rotate_players()

        return self.state.step(rotate_player=False)

    def _handle_discard(self, action: str) -> None:
        """
        Handle a player's attempt to discard a card.

        Args:
            action (str): the player's action.

        Returns:
            None
        """
        card_idx = re.findall(r"(\d)", action)
        if card_idx:
            try:
                card = self.state.game_state['player_hands'][self.state.current_player_id].pop(int(card_idx[0]))
                action = f"Player {self.state.current_player_id} discards {str(card)}."
            except IndexError:
                reason = "The player attempts to discard a non-existing card."
                self.state.set_invalid_move(reason=reason)
                self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                           message=f"You attempted to discard a non-existing card. "
                                                   f"Please consider cards between 0 and {self.hand_size - 1} "
                                                   f"(Including). You provided {card_idx[0]}.",
                                           observation_type=ta.ObservationType.GAME_MESSAGE)
                return


            # Add the card to the discard pile
            self.state.game_state['discard_pile'].append(card)

            # Replenish an info token
            if self.state.game_state['info_tokens'] < 8:
                self.state.game_state['info_tokens'] += 1
                action += " This replenishes an info token."

            else:
                action += " This does not replenish an info token as the token cap is reached."

            # Inform players
            self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=action,
                                       observation_type=ta.ObservationType.GAME_MESSAGE)

            # Draw a new card
            card = self._draw_card(self.state.game_state['deck'])

            # Give the card to the current player
            self.state.game_state['player_hands'][self.state.current_player_id].append(card)

        else:  # could not parse the action
            reason = "The player provided an invalid action."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                       message="You provided an invalid action. If you want to discard a card, type:\n "
                                               "'[Discard] X', to discard the card in position X from your hand. "
                                               "For example: '[Discard] 0' discards the card at position 0.",
                                       observation_type=ta.ObservationType.GAME_MESSAGE)

    def _handle_play(self, action: str) -> None:
        """
        Handle a player's attempt to play a card.

        Args:
            action (str): the player's action.

        Returns:
            None
        """
        card_idx = re.findall(r"(\d)", action)
        if card_idx:
            try:
                card = self.state.game_state['player_hands'][self.state.current_player_id].pop(int(card_idx[0]))
                action = f"Player {self.state.current_player_id} attempts to play {str(card)}."
            except IndexError:
                reason = "The player attempts to play a non-existing card."
                self.state.set_invalid_move(reason=reason)
                self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                           message=f"You attempted to play a non-existing card. "
                                                   f"Please consider cards between 0 and {self.hand_size - 1} "
                                                   f"(Including). You provided {card_idx[0]}.",
                                           observation_type=ta.ObservationType.GAME_MESSAGE)
                return


            # Check validity
            if self._play(card):
                message = action + " " + "The card was played successfully."
                self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=message,
                                           observation_type=ta.ObservationType.GAME_MESSAGE)

            else:  # Invalid!
                message = action + " " + ("The card did not match the current state of the fireworks."
                                          " This costs one fuse token.")
                self.state.game_state['fuse_tokens'] -= 1
                message += f" There are {self.state.game_state['fuse_tokens']} fuse tokens remaining."
                self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=message,
                                           observation_type=ta.ObservationType.GAME_MESSAGE)

                # Add the card to the discard pile
                self.state.game_state['discard_pile'].append(card)

            # Draw a new card
            card = self._draw_card(self.state.game_state['deck'])

            # Give the card to the current player
            self.state.game_state['player_hands'][self.state.current_player_id].append(card)

        else:  # Could not parse the action
            reason = "The player provided an invalid action."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                       message="You provided an invalid action. If you want to play a card, type:\n "
                                               "'[Play] X', to play the card in position X from your hand. "
                                               "For example: '[Play] 0' plays the card at position 0.",
                                       observation_type=ta.ObservationType.GAME_MESSAGE)

    def _handle_reveal(self, action: str) -> None:
        """
        Handle a player's attempt to reveal a card.

        Args:
            action (str): the player's action.

        Returns:
            None
        """
        # Token handling
        if self.state.game_state['info_tokens'] == 0:  # Invalid action, no info tokens left
            reason = "Player attempted to give a hint without having any info tokens."
            self.state.set_invalid_move(reason=reason)

        else:  # Parse the message and send it to the selected player
            card_index, color, player, rank = self._parse_hint(action)

            if not self.check_valid_move(card_index, color, player, rank):
                return

            # Parse the hint into a nice format for broadcasting,
            # removing all additional information provided to prevent cheating
            if color:  # The player gave a hint about the suit
                hint = f"Card {card_index[0]} from player {player[0]} is {color[0]}."

            else:  # The player gave a hint about the rank
                hint = f"Card {card_index[0]} from player {player[0]} has rank {rank[0]}."

            self.state.game_state['info_tokens'] = self.state.game_state['info_tokens'] - 1
            self.state.add_observation(from_id=self.state.current_player_id, to_id=-1, message=hint,
                                       observation_type=ta.ObservationType.GAME_MESSAGE)

    def check_valid_move(self, card_index: list, color: list, player: list, rank: list) -> bool:
        """
        Check the validity of the reveal move. Returns ``True`` if the move is valid, else ``False``.

        Args:
            card_index (List[int]): the index of the card.
            color (List[str]): the suit of the card.
            player (List[int]): the index of the player.
            rank (List[int]): the rank of the card.

        Returns:
            bool: ``True`` if the move is valid.

        """
        if player == [] or card_index == [] or (color == [] and rank == []):  # Incomplete answer
            reason = "The player provided an incomplete hint."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                    message="You provided an invalid action. If you want to reveal a card,"
                                            " type:\n "
                                            "'[Reveal] player N card X color C', to give a hint about color C of"
                                            " card X to the player at index N.\n"
                                            "or\n"
                                            "'[Reveal] player N card X rank R', to give hint about rank R of card"
                                            " X to the player at index N.\n\n"
                                            "For example: '[Reveal] player 0 card 0 color green' "
                                            "Reveals that card 0 from player 0 is green.",
                                    observation_type=ta.ObservationType.GAME_MESSAGE)
            return False

        if int(player[0]) == self.state.current_player_id:
            reason = "The player attempts to reveal information about their own cards."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                    message=f"You attempted to reveal information about your own cards. "
                                            f"This is not allowed.",
                                    observation_type=ta.ObservationType.GAME_MESSAGE)
            return False

        elif int(player[0]) < 0 or int(player[0]) >= self.num_players:
            reason = "The player attempts to reveal information about a non-existing teammate."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                    message=f"You attempted to reveal information about a non-existing teammate. "
                                            f"Please consider teammates between 0 and {self.num_players - 1} "
                                            f"(Including). Note that you cannot reveal information about "
                                            f"yourself, you are player {self.state.current_player_id}.",
                                    observation_type=ta.ObservationType.GAME_MESSAGE)
            return False

        if int(card_index[0]) < 0 or int(card_index[0]) >= self.hand_size:
            reason = "The player attempts to reveal information about a non-existing card."
            self.state.set_invalid_move(reason=reason)
            self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                    message=f"You attempted to reveal information about a non-existing card. "
                                            f"The card index should be between 0 and {self.hand_size - 1} "
                                            f"(including). You provided {card_index[0]}. ",
                                    observation_type=ta.ObservationType.GAME_MESSAGE)
            return False

        # Check color validity only if color hint is provided
        if color and color[0]:  # Only validate color if it's provided
            try:
                Suit(color[0])
            except ValueError:
                reason = "The player provided a color that is not in the game."
                self.state.set_invalid_move(reason=reason)
                self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                        message=f"You provided an invalid color. Valid colors are 'white', 'yellow', "
                                                f"'green', 'red' and 'blue'. You tried: '{color[0]}'.",
                                        observation_type=ta.ObservationType.GAME_MESSAGE)
                return False

        # Check rank validity only if rank hint is provided
        if rank and rank[0]:  # Only validate rank if it's provided
            try:
                rank_value = int(rank[0])
                if rank_value < 1 or rank_value > 5:
                    reason = "The player provided an invalid rank."
                    self.state.set_invalid_move(reason=reason)
                    self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                            message=f"You provided an invalid rank. Valid ranks are between 1 and 5"
                                                    f" (including). You provided: '{rank[0]}'.",
                                            observation_type=ta.ObservationType.GAME_MESSAGE)
                    return False
            except ValueError:
                reason = "The player provided an invalid rank format."
                self.state.set_invalid_move(reason=reason)
                self.state.add_observation(from_id=GAME_ID, to_id=self.state.current_player_id,
                                        message=f"You provided an invalid rank format. Valid ranks are between 1 and 5"
                                                f" (including). You provided: '{rank[0]}'.",
                                        observation_type=ta.ObservationType.GAME_MESSAGE)
                return False

        return True

    @staticmethod
    def _parse_hint(action: str):
        """
        Parse the hint provided by the player.
        """
        player = re.findall(r"player (\d+)", action)
        card_index = re.findall(r"card (\d)", action)
        color = re.findall(r"color ([A-Z]|[a-z]*)", action)
        rank = re.findall(r"rank (\d)", action)
        return card_index, color, player, rank

    def _play(self, card: Card) -> bool:
        """
        Verifies whether the played ``card`` matches the current state of the fireworks, and updates the current state.
        Returns ``False`` if the ``card`` cannot be played, ``True`` otherwise.

        Args:
            card (Card): a playing card.

        Returns:
            Bool: ``False`` if the ``card`` cannot be played, ``True`` otherwise.
        """
        rocket = self.state.game_state['fireworks'][card.suit]

        if rocket == card.rank - 1:  # Valid play, update the fireworks
            self.state.game_state['fireworks'][card.suit] += 1
            return True

        return False  # Invalid play

    def _rotate_players(self):
        """
        Select the next player and manually update the state.
        """
        next_player_id = (self.state.current_player_id + 1) % self.num_players
        self.state.manually_set_current_player_id(new_player_id=next_player_id)
        if not self.state.made_invalid_move:
            self.state.add_observation(to_id=next_player_id,
                                       message=self._state_description(),
                                       observation_type=ta.ObservationType.GAME_MESSAGE)

    def _check_game_end(self):
        """
        Check whether the game has ended, and update the rewards accordingly.

        Returns:
            None

        """
        # Losing conditions
        if len(self.state.game_state['deck']) == 0:  # The deck has run out
            if self.state.game_state['last_round'] == -1:  # Start the last round
                self.state.add_observation(from_id=-1, to_id=-1, message="There are no cards left in the deck. "
                                                                         "This is the final round.",
                                           observation_type=ta.ObservationType.GAME_MESSAGE)
                self.state.game_state['last_round'] = self.state.current_player_id

            elif self.state.game_state['last_round'] == self.state.current_player_id:  # End the last round
                self.state.set_draw(reason="The deck has run out.")
                rewards = self._calculate_scores()
                self.rewards = {pid: rewards for pid in range(self.num_players)}

        if self.state.game_state['fuse_tokens'] < 0:  # There are no fuse tokens left
            self.state.set_draw(reason="The team ran out of fuse tokens.")
            rewards = self._calculate_scores()
            self.rewards = {pid: rewards for pid in range(self.num_players)}

        # Winning conditions
        if self._completed_fireworks():
            self.state.set_winners(list(range(self.num_players)), reason="All 5s have been played successfully.")
            rewards = self._calculate_scores()
            self.rewards = {pid: rewards for pid in range(self.num_players)}

    def _completed_fireworks(self) -> bool:
        """
        Check whether all rockets are complete.

        Returns:
            Bool: ``True`` if all rockets are complete.
        """
        for rocket in self.state.game_state['fireworks'].keys():
            if self.state.game_state['fireworks'][rocket] < 5:
                return False
        return True

    def _calculate_scores(self) -> int:
        """
        Calculate the scores based on the status of the fireworks.

        Returns:
            int: the game scores.
        """
        return sum([x for x in self.state.game_state['fireworks'].values()])

    @staticmethod
    def _generate_deck() -> List[Card]:
        """
        Generate a deck of 40 cards. The deck contains 5 suits, white, yellow, blue, green and red; and 5 ranks. Of each
        suit, there are three 1s, two of each 2s, 3s and 4s, and one 5.

        Returns:
            List[Card]: a deck of Hanabi cards. The  total deck contains 50 cards.
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
        Draw ``self.hand_size`` random cards from ``deck``.

        Args:
            deck (List[Card]): a list of `Card`s representing the deck.

        Returns:
            List[Card]: ``self.hand_size`` randomly drawn cards from the ``deck``.

        Notes:
            This function actively removes the cards that are drawn from the deck.
        """
        return [self._draw_card(deck) for _ in range(self.hand_size)]

    @staticmethod
    def _draw_card(deck: List[Card]) -> Optional[Card]:
        """
        Draw a card from the ``deck``.
        Args:
            deck (List[Card]): a list of cards.

        Returns:
            Card: a randomly drawn card. Returns ``None`` if there are no cards left.
        """
        if len(deck) > 0:
            return deck.pop(random.randrange(len(deck)))
        else:
            return None


