import re, random
from typing import Optional, Tuple, Dict, Any, List, Callable

import textarena as ta

import nltk
nltk.download("words")
from nltk.corpus import words

from textarena.envs.utils.word_lists import WordFreqDictionary, NON_ALPHABETIC_LANGS

en_uk_dict = set(words.words())


class LetterAuctionEnv(ta.Env):
    """ The environment for Letter Auction Game """
    def __init__(self, starting_coins: int = 100, max_turns: int = 26):
        """
        Initialize the environment for Letter Auction Game.

        Args:
            starting_coins (int):
        """
        self.letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        self.letter_values = [1 for _ in self.letters]
        self.starting_coins = starting_coins
        self.max_turns = max_turns
        # English keeps its bundled A-Z / NLTK-dictionary path unchanged (no new
        # deps, byte-identical output). Non-English content languages are handled
        # lazily via the optional wordfreq backend (see _lang_setup); cached here.
        self._ml_cache: Dict[str, Any] = {}

    @property
    def terminal_render_keys(self):
        return ["rendered_text", "turn"]

    def _content_lang(self) -> str:
        """The single language the auction letters / words are drawn from.

        LetterAuction is single-content-language (all players auction the same
        letters and form words in one language); per-player UI language still
        varies via the locale layer. When players request different languages we
        take player 0's as the content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    def _lang_setup(self, lang: str) -> Tuple[List[str], Callable[[str], bool]]:
        """Return (auctionable letters, word-validity checker) for the content language.

        English uses the fixed A-Z alphabet and the bundled NLTK dictionary,
        exactly as before. Any other alphabetic language uses the language's own
        letters (most-frequent first, uppercased/deduplicated) and validates
        final words via wordfreq. Per-language results are cached.
        """
        if lang == "en":
            return list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), (lambda w: w.lower() in en_uk_dict)
        if lang not in self._ml_cache:
            if lang in NON_ALPHABETIC_LANGS:
                raise ValueError(
                    f"LetterAuction auctions individual letters and does not "
                    f"support the non-alphabetic language '{lang}'."
                )
            d = WordFreqDictionary(lang)
            # Take the most-frequent distinct letters of this language. CAP at 26
            # so the auction has the same structure/length as the English game
            # (26 rounds, default max_turns=26); longer alphabets are truncated to
            # their 26 most common letters.
            letters: List[str] = []
            for ch in d.alphabet():
                u = ch.upper()
                if u not in letters:
                    letters.append(u)
                if len(letters) >= 26:
                    break
            if not letters:
                raise ValueError(f"No letters available for language '{lang}'.")
            self._ml_cache[lang] = (letters, d.is_valid)
        return self._ml_cache[lang]

    def reset(self, num_players: int, seed: Optional[int] = None):
        """ Reset the environment to start a new game """
        # Initialize the game state
        self.state = ta.TwoPlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)

        # Resolve the content language: fixed A-Z + NLTK for English, otherwise
        # the language's own alphabet + wordfreq validity.
        self.letters, self._is_valid_word = self._lang_setup(self._content_lang())
        self.letter_values = [1 for _ in self.letters]

        # Initialize the player state
        self.player_states = {
            0: {
                "coins": self.starting_coins,
                "letters": [],
                "letter_values": [],
                "letter_bid_history": {
                    i: None for i in range(len(self.letters))
                },
                "word": None,
                "word_value": 0,
            },
            1: {
                "coins": self.starting_coins,
                "letters": [],
                "letter_values": [],
                "letter_bid_history": {
                    i: None for i in range(len(self.letters))
                },
                "word": None,
                "word_value": 0,
            }
        }

        # Initialize the game
        self.current_player = 0
        random.shuffle(self.letters)
        self.round_number = 0
        self.round_letter = self.letters[self.round_number]
        self.bid_amount = self.letter_values[self.round_number]

        # intialize the game states
        game_state = {
            "player_states": self.player_states,
            "rendered_text": self.render_text(),
            "turn": self.current_player,
        }
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)


    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        """ Generate the prompt for the current player """
        return self.m(
            "prompt", "intro",
            player_id=player_id,
            coins=self.player_states[player_id]["coins"],
            letters=self.player_states[player_id]["letters"],
            letter=self.round_letter,
            bid_amount=self.bid_amount,
        )

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Execute the player's action in the environment."""
        player_id = self.state.current_player_id

        # Validate player turn
        if player_id != self.current_player:
            raise ValueError(f"Invalid player ID: {player_id}. It is not the turn of player {player_id}.")

        # Record player's action
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        next_player = True  # default behavior

        if self.round_number < len(self.letters):
            # Auction phase
            match = re.search(r"\[(bid \d+|pass)\]", action, re.IGNORECASE)

            if not match:
                self.state.set_invalid_move(reason=self.m("invalid", "bad_bid_format", action=action))
            else:
                action_text = match.group(1).lower()
                # Update bid history if it's the player's first move this round
                if self.player_states[player_id]["letter_bid_history"][self.round_number] is None:
                    self.player_states[player_id]["letter_bid_history"][self.round_number] = "pass" if "pass" in action_text else "bid"

                if "pass" in action_text:
                    next_player = self._pass_bid(player_id)
                else:
                    bid_amount = int(action_text.split()[1])
                    next_player = self._place_bid(player_id, bid_amount)

        else:
            # Word-submission phase
            match = re.search(r"\[([a-zA-Z]+)\]", action)
            if not match:
                self.state.set_invalid_move(reason=self.m("invalid", "bad_word_format", action=action))
            else:
                word = match.group(1).lower()
                self._calculate_word_value(player_id, word)

        # Update the rendered game state
        self.state.game_state["rendered_text"] = self.render_text()

        # Check for game completion
        if self._check_game_done():
            p0_score = self.player_states[0]["word_value"]
            p1_score = self.player_states[1]["word_value"]

            if p0_score > p1_score:
                self.state.set_winner(player_id=0, reason=self.m("outcome", "win", player_id=0, score=p0_score))
            elif p1_score > p0_score:
                self.state.set_winner(player_id=1, reason=self.m("outcome", "win", player_id=1, score=p1_score))
            else:
                self.state.set_draw(reason=self.m("outcome", "draw"))

        return self.state.step(rotate_player=next_player)


    def _pass_bid(self, player_id: int) -> bool:
        """Pass on the current letter, allowing opponent to bid if they haven't yet."""
        opponent_id = 1 - player_id
        letter = self.round_letter
        round_num = self.round_number
        bid_status = self.player_states[opponent_id]["letter_bid_history"][round_num]

        # Decide next_player and round progression based on opponent's status
        if bid_status is None:
            # Opponent hasn't bid yet — it's now their turn
            next_player = True
            cont = self._turn_manager(next_round=False, next_player=next_player)
            message = self.m("auction", "pass", player_id=player_id, letter=letter, cont=cont)

        elif bid_status == "bid":
            # Opponent already bid — they win the letter
            won_amount = self.bid_amount
            self._assign_letter(opponent_id, letter, won_amount)
            next_player = False
            cont = self._turn_manager(next_round=True, next_player=next_player)
            message = self.m("auction", "pass_opp_wins", player_id=player_id, opponent_id=opponent_id, letter=letter, bid_amount=won_amount, cont=cont)

        else:
            # Opponent also passed — no one gets the letter
            next_player = False
            cont = self._turn_manager(next_round=True, next_player=next_player)
            message = self.m("auction", "pass_both", player_id=player_id, opponent_id=opponent_id, letter=letter, cont=cont)

        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)

        return next_player

    def _place_bid(self, player_id: int, bid_amount: int) -> bool:
        """Place a bid on the current letter."""
        opponent_id = 1 - player_id
        letter = self.round_letter
        round_num = self.round_number
        opponent_status = self.player_states[opponent_id]["letter_bid_history"][round_num]

        # Check for invalid bid - not enough coins
        if self.player_states[player_id]["coins"] < bid_amount:
            self.state.set_invalid_move(reason=self.m("invalid", "not_enough_coins", bid_amount=bid_amount))
            return False

        # NEW: Check if bid is high enough when opponent has already bid
        if opponent_status == "bid" and bid_amount <= self.bid_amount:
            self.state.set_invalid_move(reason=self.m("invalid", "bid_too_low", bid_amount=bid_amount, current_bid=self.bid_amount))
            return False

        # Case 1: Opponent has not bid yet
        if opponent_status is None:
            self.bid_amount = bid_amount
            next_player = True
            cont = self._turn_manager(next_round=False, next_player=next_player)
            message = self.m("auction", "bid", player_id=player_id, bid_amount=bid_amount, letter=letter, cont=cont)

        # Case 2: Opponent has already bid
        elif opponent_status == "bid":
            # At this point we know bid_amount > self.bid_amount due to the check above
            # This player becomes the top bidder; opponent will be asked again
            self.bid_amount = bid_amount
            next_player = True
            cont = self._turn_manager(next_round=False, next_player=next_player)
            message = self.m("auction", "bid", player_id=player_id, bid_amount=bid_amount, letter=letter, cont=cont)

        # Case 3: Opponent passed
        else:
            # This player automatically wins the letter
            self._assign_letter(player_id, letter, bid_amount)
            next_player = True
            cont = self._turn_manager(next_round=True, next_player=next_player)
            message = self.m("auction", "bid_opp_pass", player_id=player_id, opponent_id=opponent_id, letter=letter, bid_amount=bid_amount, cont=cont)

        self.state.add_observation(message=message, observation_type=ta.ObservationType.GAME_MESSAGE)

        return next_player


    def _assign_letter(self, player_id: int, letter: str, bid_amount: int) -> None:
        """ Assign the letter to the player """
        self.player_states[player_id]["letters"].append(letter)
        self.player_states[player_id]["letter_values"].append(bid_amount)
        self.player_states[player_id]["coins"] -= bid_amount

    def _turn_manager(self, next_round: bool = False, next_player: Optional[bool] = False):
        """
        Manage the turns and rounds in the game, and return the continuation
        message (a localized message) for the next player or the end of auction.

        Args:
            next_round (bool, optional): Move to the next round. Defaults to False.
            next_player (bool, optional): Move to the next player. Defaults to False.

        Returns:
            A LocalizedMessage for the next prompt / end-of-auction announcement.
        """

        if next_player:
            # we switch the player
            self.current_player = 1 - self.current_player

        if next_round:
            # we advance to the next round if within the rounds
            self.round_number += 1
            if self.round_number < len(self.letters):
                self.round_letter = self.letters[self.round_number]
                self.bid_amount = self.letter_values[self.round_number]
                return self.m("turn", "start_bid", current_player=self.current_player, letter=self.round_letter, bid_amount=self.bid_amount)
            else:
                # the auction is over
                return self.m("turn", "auction_over")

        return self.m("turn", "bid_more", current_player=self.current_player, letter=self.round_letter, bid_amount=self.bid_amount)


    def _calculate_word_value(self, player_id: int, word: str) -> None:
        """ Calculate the value of the player's chosen word based on the bids """
        # check if the word is valid
        word = word.upper()

        if not self._is_valid_word(word):
            self.player_states[player_id]["word"] = ""
            self.player_states[player_id]["word_value"] = 0

            self.state.set_invalid_move(reason=self.m("invalid", "not_a_word", word=word))
            return

        # check if the word is valid based on the letters
        for letter in word:
            if letter not in self.player_states[player_id]["letters"]:
                self.player_states[player_id]["word"] = ""
                self.player_states[player_id]["word_value"] = 0

                self.state.set_invalid_move(reason=self.m("invalid", "missing_letter", word=word, letter=letter))
                return

        # calculate the word value
        word_value = sum(self.player_states[player_id]["letter_values"][self.player_states[player_id]["letters"].index(letter)] for letter in word)
        self.player_states[player_id]["word"] = word
        self.player_states[player_id]["word_value"] = word_value

        message = self.m("word", "chosen", player_id=player_id, word=word, word_value=self.player_states[player_id]["word_value"])
        self.state.add_observation(from_id=ta.GAME_ID, to_id=-1, message=message, observation_type=ta.ObservationType.GAME_ACTION_DESCRIPTION)

        # move to the next round
        self._turn_manager(next_round=False, next_player=True)

    def _check_game_done(self) -> bool:
        """ Check if the game is done """
        for player_id in self.player_states:
            if self.player_states[player_id]["word"] is None:
                return False

        return True

    def render_text(self) -> str:
        """
        Render the game state.

        Returns:
            str: The rendered game state.
        """
        rendered_text = f"Round {self.round_number + 1}/{len(self.letters) + 1}\n" # +1 for the word phase
        rendered_text += f"All letters: {self.letters}\n"
        rendered_text += f"Current letter: {self.round_letter}\n"
        rendered_text += f"Player 0: {self.player_states[0]['coins']} coins, {self.player_states[0]['letters']}\n"
        rendered_text += f"Player 1: {self.player_states[1]['coins']} coins, {self.player_states[1]['letters']}\n"
        rendered_text += f"Current player: {self.current_player}\n"
        return rendered_text

