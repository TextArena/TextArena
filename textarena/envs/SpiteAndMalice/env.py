import copy
import re
from typing import Any, Dict, List, Optional, Union

import textarena as ta

class SpiteAndMaliceEnv(ta.GameEnv):
    """
    Environment for Spite and Malice.
    """
    min_players = 2
    max_players = 2
    broadcast_actions = False  # raw actions are echoed only to their author

    def __init__(self):
        """ Initialize the Spite and Malice environment """
        pass

    @property
    def terminal_render_keys(self):
        return ["rendered_board", "player_turn"]

    @property
    def deck(self):
        return self.game_state["deck"]

    @property
    def players(self):
        return self.game_state["players"]

    @property
    def center_piles(self):
        return self.game_state["center_piles"]

    def setup(self) -> Dict[str, Any]:
        # Initialize the deck and shuffle
        deck = [f"{rank}{suit}" for rank in "A23456789JQK" for suit in "♠♥♦♣"] * 2
        self.rng.shuffle(deck)

        game_state = {
            "deck": deck,
            "players": {0: {"payoff": [], "hand": [], "discard": [[] for _ in range(4)]},
                        1: {"payoff": [], "hand": [], "discard": [[] for _ in range(4)]}},
            "center_piles": [[] for _ in range(4)],
            "completed_cards": [],
            "turn_has_drawn": {0: False, 1: False},
        }
        self.state.game_state = game_state  # so the helpers below can read it

        ## Deal the payoff piles (20 cards each for a shorter game)
        for player in game_state["players"]:
            game_state["players"][player]["payoff"] = [deck.pop() for _ in range(20)]

        ## Draw cards for each player
        self._draw_cards(0)
        self._draw_cards(1)

        game_state["player_turn"] = 0
        game_state["rendered_board"] = self._render_board()
        return game_state

    def _draw_cards(self, player_id: int, notify: bool = True):
        """ Draw cards to maintain 5 cards in hand. """
        while len(self.players[player_id]["hand"]) < 5 and self.deck:
            self.players[player_id]["hand"].append(self.deck.pop())

        if notify and not self.deck and len(self.players[player_id]["hand"]) < 5:
            message = (
                "There are no more cards to draw from. Remember that you can play cards from these sources:\n"
                "  1. Your **hand**.\n"
                "  2. The **top card of your payoff pile**.\n"
                "  3. The **top card of any of your discard piles**.\n\n"
            )
            self.message(player_id, message, ta.ObservationType.GAME_MESSAGE)

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id} in a two-player game of Spite and Malice. Your goal is to be the first to empty your payoff pile.\n\n"

            "### Game Overview:\n"
            "- The objective is to clear your payoff pile by playing cards to the center piles.\n"
            "- You can play cards from three sources:\n"
            "  1. Your **hand** (you start each turn with up to 5 cards in hand).\n"
            "  2. The **top card of your payoff pile**.\n"
            "  3. The **top card of any of your discard piles**.\n\n"

            "### Playing Rules:\n"
            "- You may play a card to a center pile if it is **one rank higher** than the top card on that pile (center piles start with Ace and go up to Queen; Kings are wild - they can be played on any card but do not change the rank sequence. This means if a King is used after 4, then that King is ranked 5 and the next card must be a 6).\n"
            "- If you can't play any more cards, you must **discard a card** to one of your discard piles to end your turn.\n"
            "- If a center pile reaches Queen, it will be cleared automatically.\n"
            "- The rank order is: A=1, 2=2, ..., 9=9, J=10, Q=11, K as wild. The deck has no 10s.\n\n"

            "### Actions:\n"
            "1. **Draw**: At the start of your turn, draw cards to fill your hand up to 5 cards. Enter **draw** to begin.\n"
            "2. **Play a Card**: To play a card, specify the card and the center pile like this: **play A♠ 0** (where 'A♠' is the card and '0' is the center pile index).\n"
            "3. **Discard**: If you can't play any more cards, discard a card from your hand to a discard pile to end your turn. Enter **discard A♠ 1** (where 'A♠' is the card and '1' is the discard pile index). Note that you cannot discard any card from the payoff pile. You may only discard the cards from your hand.\n\n"
            "You can chain several commands in one reply, e.g. 'draw play A♠ 0 discard 5♦ 1'; they are executed in order.\n\n"
        )

    def render(self, player_id: int) -> str:
        has_drawn = self.game_state["turn_has_drawn"][player_id]
        available_moves = [] if has_drawn else ["'draw'"]

        # Add valid play actions
        for i, pile in enumerate(self.center_piles) if has_drawn else []:
            # From payoff pile
            if self.players[player_id]["payoff"]:
                top_payoff_card = self.players[player_id]["payoff"][-1]
                if self._can_play_on_center(top_payoff_card, pile):
                    available_moves.append(f"'play {top_payoff_card} {i}'")
            # From hand
            for card in self.players[player_id]["hand"]:
                if self._can_play_on_center(card, pile):
                    available_moves.append(f"'play {card} {i}'")
            # From discard
            for discard_pile in self.players[player_id]["discard"]:
                if discard_pile:
                    top_discard_card = discard_pile[-1]
                    if self._can_play_on_center(top_discard_card, pile):
                        available_moves.append(f"'play {top_discard_card} {i}'")

        # Add discard actions (you can discard any card from hand to any discard pile)
        for i, discard_pile in enumerate(self.players[player_id]["discard"]) if has_drawn else []:
            for card in self.players[player_id]["hand"]:
                available_moves.append(f"'discard {card} {i}'")

        return f"Current Board:\n\n{self._render_board(player_id=player_id)}\nAvailable Moves: " + ", ".join(available_moves)

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        commands = self._parse_commands(action)
        if commands is None:
            return self.invalid(
                f"Invalid move format. Player {player_id} must submit only 'draw', "
                "'play <card> <pile>', or 'discard <card> <pile>' commands."
            )

        if any(command[0] == "discard" for command in commands[:-1]):
            return self.invalid("Discard ends the turn and must be the final command.")

        original_state = copy.deepcopy(self.game_state)
        events = []
        rotate_player = False
        invalid_reason: Optional[str] = None

        for command_index, (action_type, card, index) in enumerate(commands):
            if action_type == "draw":
                if command_index != 0 or self.game_state["turn_has_drawn"][player_id]:
                    invalid_reason = "Draw is allowed exactly once, at the start of your turn."
                    break
                self._draw_cards(player_id, notify=False)
                self.game_state["turn_has_drawn"][player_id] = True
                events.append(("draw", None, None))
                continue

            if not self.game_state["turn_has_drawn"][player_id]:
                invalid_reason = "You must draw before playing or discarding."
                break

            if action_type == "play":
                if self._play_card(player_id, card, index):
                    events.append(("play", card, index))
                    if not self.players[player_id]["payoff"]:
                        break
                    if not self.players[player_id]["hand"] and self.deck:
                        self._draw_cards(player_id, notify=False)
                        events.append(("refill", None, None))
                else:
                    invalid_reason = (
                        f"Invalid play. Player {player_id} tried to play {card} "
                        f"on center pile {index}."
                    )
                    break
            else:
                if card not in self.players[player_id]["hand"]:
                    invalid_reason = (
                        f"Invalid discard. Player {player_id} tried to discard "
                        "a card that is not in hand."
                    )
                    break
                self._discard_card(player_id, card, index)
                self.game_state["turn_has_drawn"][player_id] = False
                self.game_state["player_turn"] = 1 - player_id
                events.append(("discard", card, index))
                rotate_player = True

        if invalid_reason is not None:
            self.state.game_state = original_state
            return self.invalid(invalid_reason)

        for action_type, card, index in events:
            if action_type == "draw":
                self.message(player_id, "You drew cards.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self.message(1 - player_id, f"Player {player_id} drew cards.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            elif action_type == "refill":
                self.message(
                    player_id,
                    "You played every card in your hand, drew a new hand, and may continue your turn.",
                    ta.ObservationType.GAME_ACTION_DESCRIPTION,
                )
                self.message(
                    1 - player_id,
                    f"Player {player_id} played every card in hand and drew a new hand.",
                    ta.ObservationType.GAME_ACTION_DESCRIPTION,
                )
            elif action_type == "play":
                self.message(player_id, f"You played {card} on center pile {index}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self.message(1 - player_id, f"Player {player_id} played {card} on center pile {index}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            else:
                self.message(player_id, f"You discarded {card} to discard pile {index} and ended your turn.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
                self.broadcast(f"Player {player_id} discarded {card} to discard pile {index}. Player {1 - player_id} goes next.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        self.game_state["rendered_board"] = self._render_board()
        outcome = self._check_game_end(player_id)
        if outcome is not None:
            return outcome
        if (
            not rotate_player
            and not self.players[player_id]["hand"]
            and not self._player_has_valid_moves(player_id)
        ):
            self.game_state["turn_has_drawn"][player_id] = False
            self.game_state["player_turn"] = 1 - player_id
            self.broadcast(
                f"Player {player_id} has no card to discard and no legal play; "
                f"their turn ends automatically.",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            rotate_player = True
        if not rotate_player:
            self.set_next_player(player_id)
        return None

    def _parse_commands(self, action: str):
        """Parse a complete command chain without ignoring unmatched text."""
        action = action.replace("\ufe0f", "").replace("\ufe0e", "")  # emoji-style suits such as '♥️'
        if action.count("[") != action.count("]"):
            return None
        command_pattern = re.compile(
            r"(?:\[\s*)?\b(draw|play|discard)\b"
            r"(?:\s+([A23456789JQK][♠♥♦♣])\s+([0-3]))?"
            r"(?:\s*\])?",
            re.IGNORECASE,
        )
        commands = []
        position = 0
        for match in command_pattern.finditer(action):
            if action[position:match.start()].strip():
                return None
            verb, card, index = match.groups()
            if verb.lower() in {"play", "discard"} and (card is None or index is None):
                return None
            if verb.lower() == "draw" and (card is not None or index is not None):
                return None
            normalized_card = card[0].upper() + card[1:] if card else None
            commands.append((verb.lower(), normalized_card, int(index) if index is not None else None))
            position = match.end()
        if not commands or action[position:].strip():
            return None
        return commands

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
                self.game_state["completed_cards"].extend(self.center_piles[center_index])
                self.center_piles[center_index].clear()
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
            top_card_rank = len(pile) - 1 if len(pile) >= 1 else 0  # Treat as '1' if K is the only card
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

    def _check_game_end(self, current_player: int) -> Optional[ta.Outcome]:
        """ Check for game end conditions and return the outcome if the game is over. """
        if len(self.players[current_player]["payoff"]) == 0:
            return self.winner(current_player, reason=f"Player {current_player} has finished their payoff pile! Player {current_player} wins!")

        if not self._is_deadlock():
            return None

        player_0_payoff = len(self.players[0]["payoff"])
        player_1_payoff = len(self.players[1]["payoff"])

        if player_0_payoff < player_1_payoff:
            return self.winner(0, reason=f"Deadlock reached! Player 0 wins with {player_0_payoff} cards remaining vs Player 1's {player_1_payoff} cards.")
        elif player_1_payoff < player_0_payoff:
            return self.winner(1, reason=f"Deadlock reached! Player 1 wins with {player_1_payoff} cards remaining vs Player 0's {player_0_payoff} cards.")
        else:
            return self.draw(reason=f"Deadlock reached with both players having {player_0_payoff} payoff cards remaining.")

    def _render_board(self, player_id: Optional[int] = None) -> str:
        """ Render the game board """
        board = f"Draw pile: {len(self.deck)} card(s)\n\n--- Center Piles ---\n"
        for i, pile in enumerate(self.center_piles):
            board += f"Pile {i}: {pile}\n"

        for player in self.players:
            label = "Your View" if player_id == player else "Public View"
            board += f"\n--- Player {player} ({label}) ---\n"
            board += f"Payoff Pile (Top Card): {self.players[player]['payoff'][-1] if self.players[player]['payoff'] else 'Empty'}, Payoff Pile Length: {len(self.players[player]['payoff'])}\n"
            if player_id == player:
                board += f"Hand: {self.players[player]['hand']}\n"
            else:
                board += f"Hand: {len(self.players[player]['hand'])} hidden card(s)\n"
            board += f"Discard Piles: {self.players[player]['discard']}\n"
        return board
