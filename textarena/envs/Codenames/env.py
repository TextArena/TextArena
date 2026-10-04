import functools
import importlib.resources
import json
import re
from typing import Any, Dict, Tuple, Union
import textarena as ta
from textarena.utils.word_lists import get_blocked_words


@functools.lru_cache(maxsize=None)
def _bundled_word_lists() -> Dict[str, Tuple[str, ...]]:
    """Board-word candidates shipped with the env in words.json.

    The lists are the nouns of NLTK's Basic English ("basic") and full English ("hardcore")
    word lists as tagged by NLTK's part-of-speech tagger, frozen in their original order.
    """
    with importlib.resources.files("textarena.envs.Codenames").joinpath("words.json").open("r", encoding="utf-8") as file:
        data = json.load(file)
    blocked = get_blocked_words()
    return {level: tuple(word for word in data[level] if word not in blocked) for level in ("basic", "hardcore")}


class CodenamesEnv(ta.GameEnv):
    min_players = 4
    max_players = 4
    mdp_includes_actions = False
    broadcast_actions = False  # raw clues/guesses are echoed only to their author
    _CLUE_RE = re.compile(r"([a-z]+)\s+([0-9]{1,2})", re.IGNORECASE)
    _GUESS_RE = re.compile(r"([a-z]+)", re.IGNORECASE)

    hardcore = ta.Param(
        False, "Draw board words from the list built from NLTK's full English word list (29,406 words) instead of the "
               "one built from its Basic English list (423 words), which produces rarer words.",
    )
    max_turns = ta.Param(80, "The total number of moves (clues and guesses) before the turn-limit result applies.", min=1)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_word_list(hardcore=self.hardcore)

    def _load_word_list(self, hardcore: bool = False) -> None:
        candidates = _bundled_word_lists()["hardcore" if hardcore else "basic"]
        self.word_list = list(dict.fromkeys(
            word for word in candidates
            if word != "pass" and len(word) < 8 and re.fullmatch(r"[a-z]+", word)
        ))
        if len(self.word_list) < 25:
            raise RuntimeError("Codenames requires at least 25 unique alphabetic words")

    def setup(self) -> Dict[str, Any]:
        assignments = ["R"]*9 + ["B"]*8 + ["N"]*7 + ["A"] # Create a list of 25 assignments: 9 Red (R), 8 Blue (B), 7 Neutral (N), and 1 Assassin (A)
        self.rng.shuffle(assignments) # Shuffle the assignments to randomize their placement
        self.board = {word: team for word, team in zip(self.rng.sample(self.word_list, 25), assignments)} # Assign each word to a team
        return {
            "turn": 0,
            "team_turn": 0,
            "guessed_words": set(),
            "last_clue": None,
            "last_number": 0,
            "remaining_guesses": 0,
        }

    def roles(self) -> Dict[int, str]:
        return {
            0: "Red Spymaster",
            1: "Red Operative",
            2: "Blue Spymaster",
            3: "Blue Operative",
        }

    def on_start(self) -> None:
        for player_id, role in self.roles().items():
            self.set_role(player_id, role)

    def prompt(self, player_id: int) -> str:
        prompt = (
            "You are playing Codenames, a 2v2 word deduction game. Each team (Red and Blue) has a Spymaster and an Operative.\nRules:\n"
            "1. The board has 25 words: 9 Red (R), 8 Blue (B), 7 Neutral (N) and 1 Assassin (A). Only the Spymasters see which is which. Red moves first.\n"
            "2. The Spymaster gives a clue: one alphabetic word and a number from 1 to 25 (e.g., 'wind 2'). The clue word must not be a board word, contain one, or be contained in one (e.g., 'sea' while 'seal' is on the board); such a clue loses the game immediately.\n"
            "3. The Operative then guesses one board word at a time (e.g., 'breeze'), up to the number + 1 guesses, or replies 'pass' to end the turn. "
            "Guessing one of your own words lets you continue; a Neutral or opposing word ends the turn; the Assassin loses the game immediately.\n"
            "4. A team wins as soon as all of its words are revealed, even if the other team revealed the last one.\n"
            f"5. After {self.max_turns} moves in total (clues and guesses), the team with more of its words revealed wins; equal counts are a draw.\n\n"
        )
        if player_id in [0, 2]: return prompt + f"You are Player {player_id}, the Spymaster for {'Red' if player_id == 0 else 'Blue'} team. Give a one-word clue and number."
        else:                   return prompt + f"You are Player {player_id}, the Operative for {'Red' if player_id == 1 else 'Blue'} team. Guess words based on the clue."

    def render(self, player_id: int) -> str:
        gs = self.game_state
        view = "Codenames Words:\n"
        for word in list(self.board.keys()):
            if player_id in [0, 2]: view += f"{word:<8} {self.board[word]} {'revealed' if word in gs['guessed_words'] else ''}\n" # Show the team label for spymasters
            else:                   view += f"{word:<8} {self.board[word] if word in gs['guessed_words'] else ''}\n"
        if gs["remaining_guesses"] > 0:
            guesses = f"{gs['remaining_guesses']} guess{'es' if gs['remaining_guesses'] != 1 else ''}"
            view += f"Current clue: '{gs['last_clue']} {gs['last_number']}' ({guesses} left this turn)\n"
        view += f"Moves played: {self.state.turn} of {self.max_turns}\n"
        return view

    def _next_player(self, player_id: int, done_guessing: bool=False, skip_guessing: bool=False) -> int:
        match player_id:
            case 0: return 2 if skip_guessing else 1
            case 2: return 0 if skip_guessing else 3
            case 1: return 2 if done_guessing else 1
            case 3: return 0 if done_guessing else 3

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        current_team = "R" if player_id < 2 else "B"

        if player_id in [0, 2]:  # Spymasters give clues
            match = self._CLUE_RE.fullmatch(action)
            if not match:
                return self.invalid("A clue must be one alphabetic word followed by a number from 1 to 25.")
            word = match.group(1).lower()
            number = int(match.group(2))
            if not 1 <= number <= 25:
                return self.invalid("The clue number must be between 1 and 25.")

            # Compare case-insensitively so capitalization cannot bypass the board-word rule.
            if any(word in board_word or board_word in word for board_word in self.board):
                return self.winner(
                    [0, 1] if current_team == "B" else [2, 3],
                    reason=f"Player {player_id} mentioned a clue that is a subset/exact match of a word on the board.",
                )

            gs["last_clue"] = word
            gs["last_number"] = number
            gs["remaining_guesses"] = number + 1 # Operatives can make up to N+1 guesses
            self.broadcast(f"Spymaster of {'Red' if current_team=='R' else 'Blue'} team, Player {player_id}, submitted the clue '{word} {number}'.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            self.set_next_player(self._next_player(player_id))
            return None

        # Operatives guess words
        match = self._GUESS_RE.fullmatch(action)
        if not match:
            return self.invalid("A guess must be one alphabetic board word or 'pass'.")

        guessed_word = match.group(1).lower()

        if guessed_word == "pass":
            gs["remaining_guesses"] = 0
            self.broadcast(
                f"Operative of {'Red' if current_team == 'R' else 'Blue'} team, Player {player_id}, passed.",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )
            self.set_next_player(self._next_player(player_id, done_guessing=True))
            return None

        if guessed_word not in self.board:
            return self.invalid(f"'{guessed_word}' is not on the board.")
        if guessed_word in gs["guessed_words"]:
            return self.invalid(f"'{guessed_word}' has already been revealed.")

        gs["guessed_words"].add(guessed_word)

        if self.board[guessed_word] == "A":
            return self.winner([2, 3] if current_team == "R" else [0, 1], reason=f"Player {player_id} selected the assassin word.")

        if self.board[guessed_word] == current_team:
            if all(word in gs["guessed_words"] for word, team in self.board.items() if team == current_team):
                return self.winner([0, 1] if current_team == "R" else [2, 3], reason=f"Player {player_id} guessed all their team's words!")
            self.broadcast(f"Operative of {'Red' if current_team=='R' else 'Blue'} team, Player {player_id}, correctly guessed '{guessed_word}'.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
            gs["remaining_guesses"] -= 1
            if gs["remaining_guesses"] <= 0:
                gs["remaining_guesses"] = 0
                self.set_next_player(self._next_player(player_id, done_guessing=True))
            else:
                self.set_next_player(player_id)  # keep guessing
            return None

        # Opponent or neutral word: reveal it and end the team's guessing turn.
        opponent_team = "B" if current_team == "R" else "R"
        if all(word in gs["guessed_words"] for word, team in self.board.items() if team == opponent_team):
            return self.winner([0, 1] if opponent_team == "R" else [2, 3], reason=f"Player {player_id} guessed the opponent team's last word!")
        opponent_team_name = "Red" if opponent_team == "R" else "Blue"
        self.broadcast(f"Operative of {'Red' if current_team=='R' else 'Blue'} team, Player {player_id}, wrongly guessed '{guessed_word}'. It is a {opponent_team_name + ' Team' if self.board[guessed_word]==opponent_team else 'Neutral'} word.", ta.ObservationType.GAME_MESSAGE)
        gs["remaining_guesses"] = 0
        self.set_next_player(self._next_player(player_id, done_guessing=True))
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        """A fixed-role team cannot continue safely after one role is eliminated."""
        losing_team = "R" if player_id < 2 else "B"
        winners = [2, 3] if losing_team == "R" else [0, 1]
        return self.winner(winners, reason=f"Player {player_id} forfeited after repeated invalid actions: {reason}")

    def on_turn_limit(self) -> ta.Outcome:
        red_correct  = sum(1 for word, team in self.board.items() if team == "R" and word in self.game_state["guessed_words"])
        blue_correct = sum(1 for word, team in self.board.items() if team == "B" and word in self.game_state["guessed_words"])
        if red_correct > blue_correct:      return self.winner([0, 1], reason=f"Move limit reached ({self.max_turns}). Red revealed {red_correct} vs Blue {blue_correct}.")
        elif blue_correct > red_correct:    return self.winner([2, 3], reason=f"Move limit reached ({self.max_turns}). Blue revealed {blue_correct} vs Red {red_correct}.")
        else:                               return self.draw(reason=f"Move limit reached ({self.max_turns}) with equal score: draw.")
