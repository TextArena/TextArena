import re
from collections import Counter
from typing import Any, Dict, Optional, Union

import textarena as ta

from nltk.corpus import words

try:
    en_uk_dict = {word.lower() for word in words.words()}
except LookupError:
    # Keep imports/reset offline and deterministic even when the optional NLTK
    # corpus is absent. These one-letter English words preserve a playable
    # minimal fallback; deployments can install the corpus for the full lexicon.
    en_uk_dict = {"a", "i"}

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# Every letter takes at least two turns (bid + pass, or pass + pass), then both players submit.
MIN_COMPLETE_GAME_TURNS = 2 * len(ALPHABET) + 2


class LetterAuctionEnv(ta.GameEnv):
    """ The environment for Letter Auction Game """
    min_players = 2
    max_players = 2
    broadcast_actions = False

    def __init__(self, starting_coins: int = 100, max_turns: Optional[int] = None):
        """
        Initialize the environment for Letter Auction Game.

        Args:
            starting_coins (int): Coins each player starts with.
            max_turns (Optional[int]): Optional cap on the total number of turns; reaching it ends the game
                as a draw. Must be at least MIN_COMPLETE_GAME_TURNS, the length of the shortest complete game.
        """
        if not isinstance(starting_coins, int) or isinstance(starting_coins, bool) or starting_coins <= 0:
            raise ValueError("starting_coins must be a positive integer")
        if max_turns is not None and (
            not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < MIN_COMPLETE_GAME_TURNS
        ):
            raise ValueError(
                f"max_turns must be None or an integer of at least {MIN_COMPLETE_GAME_TURNS} "
                "(the length of the shortest complete game)"
            )
        self.letter_values = [1 for _ in range(26)]
        self.starting_coins = starting_coins
        self.max_turns = max_turns

    @property
    def terminal_render_keys(self):
        return ["rendered_text", "turn"]

    # Read-only accessors kept for renderers/tests that inspect the env directly.
    @property
    def player_states(self): return self.game_state["player_states"]
    @property
    def letters(self): return self.game_state["letters"]
    @property
    def round_number(self): return self.game_state["round_number"]
    @property
    def round_letter(self): return self.game_state["round_letter"]
    @property
    def bid_amount(self): return self.game_state["bid_amount"]
    @property
    def current_player(self): return self.game_state["current_player"]

    def setup(self) -> Dict[str, Any]:
        letters = list(ALPHABET)
        self.rng.shuffle(letters)
        player_states = {
            pid: {
                "coins": self.starting_coins,
                "letters": [],
                "letter_values": [],
                "letter_bid_history": {i: None for i in range(len(letters))},
                "word": None,
                "word_value": 0,
            }
            for pid in (0, 1)
        }
        game_state = {
            "player_states": player_states,
            "letters": letters,
            "round_number": 0,
            "round_letter": letters[0],
            "bid_amount": self.letter_values[0],
            "current_player": 0,
            "turn": 0,
        }
        game_state["rendered_text"] = self._render_text(game_state)
        return game_state

    def prompt(self, player_id: int) -> str:
        gs = self.game_state
        return (
            f"You are Player {player_id}. You are currently in the Letter Auction game.\n"
            "The goal of the game is to strategically bid on letters to form the highest value word. This is how the game works.\n"
            "You must listen to the gamemaster for guidance to play the game.\n"
            "The game consists of a series of rounds. In each round, a letter will be put up for auction.\n"
            "You can bid on the letter using your coins. The player with the highest bid wins the letter.\n"
            "The letter will be added to your collection, and the coins you bid will be deducted from your total.\n"
            "This bidding of letters will repeat till all the letters have been auctioned off. You are not rewarded for saving your coins.\n"
            "After all the letters have been auctioned, you will use the letters to form the highest value english word from the letters won.\n"
            "The player with the highest value word wins the game.\n"
            "To bid, reply with 'bid 2', 'bid 10', or another amount.\n"
            "If you do not want to bid, reply with 'pass'.\n"
            "At the end of the auction, submit your highest-value word directly, e.g. 'dog'.\n"
            "If you cannot form a valid word, reply 'pass' to submit no word (worth 0).\n"
            "Here is your starting information:\n"
            f"Your current coins: {gs['player_states'][player_id]['coins']}\n"
            f"Your current letters: {gs['player_states'][player_id]['letters']}\n"
            "\n"
            f"Game: Player 0 will go first. The first letter for bid: {gs['round_letter']}.\n"
            f"Starting bid is {gs['bid_amount']} coin. You can bid any amount of coins, or choose not to bid.\n"
        )

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state

        if gs["round_number"] < len(gs["letters"]):
            # Auction phase
            match = re.fullmatch(
                r"\s*(?P<legacy>\[)?\s*(?P<command>bid\s+\d+|pass)\s*(?(legacy)\])\s*",
                action,
                re.IGNORECASE,
            )
            if not match:
                return self.invalid(f"Invalid action: {action}. Please enter 'bid <amount>' or 'pass'.")
            action_text = match.group("command").lower()
            is_pass = action_text == "pass"

            if not is_pass:
                try:
                    bid_amount = int(action_text.split()[1])
                except ValueError:
                    return self.invalid("Invalid bid: the amount is too large to parse.")
                opponent_status = gs["player_states"][1 - player_id]["letter_bid_history"][gs["round_number"]]
                if bid_amount <= 0:
                    return self.invalid("Invalid bid: the amount must be a positive integer.")
                if gs["player_states"][player_id]["coins"] < bid_amount:
                    return self.invalid(f"Invalid bid: {bid_amount}. You do not have enough coins.")
                if opponent_status == "bid" and bid_amount <= gs["bid_amount"]:
                    return self.invalid(f"Invalid bid: {bid_amount}. You must bid more than the current bid of {gs['bid_amount']}.")
                if opponent_status is None and bid_amount < gs["bid_amount"]:
                    return self.invalid(f"Invalid bid: {bid_amount}. The opening bid is {gs['bid_amount']}.")

            # Record bid history if it's the player's first move this round
            if gs["player_states"][player_id]["letter_bid_history"][gs["round_number"]] is None:
                gs["player_states"][player_id]["letter_bid_history"][gs["round_number"]] = "pass" if is_pass else "bid"

            if is_pass: self._pass_bid(player_id)
            else: self._place_bid(player_id, bid_amount)
        else:
            # Word-submission phase
            match = re.fullmatch(
                r"\s*(?P<legacy>\[)?\s*(?P<word>[a-zA-Z]+)\s*(?(legacy)\])\s*",
                action,
            )
            if not match:
                return self.invalid(f"Invalid action: {action}. Please enter one English word, or 'pass' to submit no word.")
            word = match.group("word").lower()
            # "pass" can never be spelled: it needs two S tiles and every letter is auctioned once.
            if word == "pass":
                self._submit_no_word(player_id)
            else:
                result = self._calculate_word_value(player_id, word)
                if result is not None:
                    return result

        gs["turn"] = self.state.turn + 1
        gs["rendered_text"] = self._render_text(gs)

        # Check for game completion
        if all(gs["player_states"][pid]["word"] is not None for pid in gs["player_states"]):
            p0_score = gs["player_states"][0]["word_value"]
            p1_score = gs["player_states"][1]["word_value"]
            if p0_score > p1_score:
                return self.winner(0, reason=f"Player 0 wins with a score of {p0_score}")
            elif p1_score > p0_score:
                return self.winner(1, reason=f"Player 1 wins with a score of {p1_score}")
            else:
                return self.draw(reason="It's a draw!")

        self.set_next_player(gs["current_player"])
        return None

    def _pass_bid(self, player_id: int) -> None:
        """Pass on the current letter, allowing opponent to bid if they haven't yet."""
        gs = self.game_state
        opponent_id = 1 - player_id
        letter = gs["round_letter"]
        bid_status = gs["player_states"][opponent_id]["letter_bid_history"][gs["round_number"]]

        prompt = f"Player {player_id} passes on the letter '{letter}'."

        if bid_status is None:
            # Opponent hasn't bid yet — it's now their turn
            prompt += self._turn_manager(next_round=False, next_player=True)
        elif bid_status == "bid":
            # Opponent already bid — they win the letter
            self._assign_letter(opponent_id, letter, gs["bid_amount"])
            prompt += f" Player {opponent_id} will have '{letter}' for {gs['bid_amount']}."
            prompt += self._turn_manager(next_round=True, next_player=False)
        else:
            # Opponent also passed — no one gets the letter
            prompt += f" Player {opponent_id} also passes on the letter '{letter}'. So, no one will gain the letter."
            prompt += self._turn_manager(next_round=True, next_player=False)

        self.broadcast(prompt, ta.ObservationType.GAME_MESSAGE)

    def _place_bid(self, player_id: int, bid_amount: int) -> None:
        """Place a bid on the current letter (already validated)."""
        gs = self.game_state
        opponent_id = 1 - player_id
        letter = gs["round_letter"]
        opponent_status = gs["player_states"][opponent_id]["letter_bid_history"][gs["round_number"]]

        prompt = f"Player {player_id} bids {bid_amount} on the letter '{letter}'."

        if opponent_status is None or opponent_status == "bid":
            # This player becomes the top bidder; opponent will be asked (again)
            gs["bid_amount"] = bid_amount
            prompt += self._turn_manager(next_round=False, next_player=True)
        else:
            # Opponent passed — this player automatically wins the letter
            prompt += f" Since Player {opponent_id} passes on the letter '{letter}', Player {player_id} will have it for {bid_amount}."
            self._assign_letter(player_id, letter, bid_amount)
            prompt += self._turn_manager(next_round=True, next_player=True)

        self.broadcast(prompt, ta.ObservationType.GAME_MESSAGE)

    def _assign_letter(self, player_id: int, letter: str, bid_amount: int) -> None:
        """ Assign the letter to the player """
        player_state = self.game_state["player_states"][player_id]
        player_state["letters"].append(letter)
        player_state["letter_values"].append(bid_amount)
        player_state["coins"] -= bid_amount

    def _turn_manager(self, next_round: bool = False, next_player: Optional[bool] = False) -> str:
        """
        Manage the turns and rounds in the game, and return the prompt for the next player or announces end of auction.

        Args:
            next_round (bool, optional): Move to the next round. Defaults to False.
            next_player (bool, optional): Move to the next player. Defaults to False.

        Returns:
            str: The prompt for the next player or the end of auction.
        """
        gs = self.game_state
        if next_player:
            gs["current_player"] = 1 - gs["current_player"]

        if next_round:
            gs["round_number"] += 1
            if gs["round_number"] < len(gs["letters"]):
                gs["round_letter"] = gs["letters"][gs["round_number"]]
                gs["bid_amount"] = self.letter_values[gs["round_number"]]
                next_prompt = f" Player {gs['current_player']}, do you want to start bid on the letter '{gs['round_letter']}' for {gs['bid_amount']}?"
            else:
                # the auction is over
                next_prompt = "The auction is over. Now, players will use the letters they've won to form the highest value english word from the letters won. The player with the highest value word wins the game. Submit the word directly, for example: dog. If you cannot form a valid word, reply 'pass' to submit no word (worth 0)."
        else:
            next_prompt = f" Player {gs['current_player']}, do you want to bid on the letter '{gs['round_letter']}' for more than {gs['bid_amount']}?"

        return next_prompt

    def _calculate_word_value(self, player_id: int, word: str) -> Optional[ta.Invalid]:
        """ Calculate the value of the player's chosen word based on the bids """
        gs = self.game_state
        word = word.upper()
        player_state = gs["player_states"][player_id]

        if word.lower() not in en_uk_dict:
            return self.invalid(f"Invalid word: {word}. Please enter a valid English word.")
        available = Counter(player_state["letters"])
        needed = Counter(word)
        for letter, count in needed.items():
            if available[letter] < count:
                return self.invalid(
                    f"Invalid word: {word}. You need {count} '{letter}' tile(s), but only have {available[letter]}."
                )

        # calculate the word value
        values_by_letter: Dict[str, list[int]] = {}
        for letter, value in zip(player_state["letters"], player_state["letter_values"]):
            values_by_letter.setdefault(letter, []).append(value)
        word_value = sum(
            sum(values_by_letter[letter][:count])
            for letter, count in needed.items()
        )
        player_state["word"] = word
        player_state["word_value"] = word_value

        self.broadcast(f"Player {player_id} chooses the word '{word}' with a value of {player_state['word_value']}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # move on to the other player
        self._turn_manager(next_round=False, next_player=True)
        return None

    def _submit_no_word(self, player_id: int) -> None:
        """ Record that the player submits no word, which is worth 0 """
        player_state = self.game_state["player_states"][player_id]
        player_state["word"] = ""
        player_state["word_value"] = 0
        self.broadcast(f"Player {player_id} passes and submits no word, with a value of 0.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._turn_manager(next_round=False, next_player=True)

    def _render_text(self, game_state: Dict[str, Any]) -> str:
        """Render the game state."""
        rendered_text = f"Round {game_state['round_number'] + 1}/{len(game_state['letters']) + 1}\n" # +1 for the word phase
        rendered_text += f"Auctioned letters: {game_state['letters'][:game_state['round_number']]}\n"
        rendered_text += f"Letters remaining: {max(0, len(game_state['letters']) - game_state['round_number'])}\n"
        current_letter = game_state["round_letter"] if game_state["round_number"] < len(game_state["letters"]) else "Auction complete"
        rendered_text += f"Current letter: {current_letter}\n"
        rendered_text += f"Player 0: {game_state['player_states'][0]['coins']} coins, {game_state['player_states'][0]['letters']}\n"
        rendered_text += f"Player 1: {game_state['player_states'][1]['coins']} coins, {game_state['player_states'][1]['letters']}\n"
        rendered_text += f"Current player: {game_state['current_player']}\n"
        return rendered_text

    def render_text(self) -> str:
        return self._render_text(self.game_state)
