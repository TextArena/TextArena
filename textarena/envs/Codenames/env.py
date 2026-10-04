import re
from nltk.corpus import words
from nltk import pos_tag
from typing import Any, Dict, Optional, Union
import textarena as ta


class CodenamesEnv(ta.GameEnv):
    min_players = 4
    max_players = 4
    broadcast_actions = False  # raw clues/guesses are echoed only to their author
    _CLUE_RE = re.compile(r"^\s*\[?\s*([a-z]+)\s+([0-9]{1,2})\s*\]?\s*$", re.IGNORECASE)
    _GUESS_RE = re.compile(r"^\s*\[?\s*([a-z]+)\s*\]?\s*$", re.IGNORECASE)
    _FALLBACK_WORDS = (
        "anchor", "apple", "arrow", "badge", "beach", "bear", "bell", "bridge",
        "brush", "cabin", "camel", "candle", "castle", "chair", "cloud", "crown",
        "dance", "doctor", "dragon", "drum", "eagle", "engine", "field", "flame",
        "forest", "giant", "glass", "glove", "grace", "hammer", "heart", "horse",
        "island", "knife", "lemon", "light", "maple", "moon", "mouse", "needle",
        "ocean", "olive", "panda", "paper", "pearl", "piano", "pilot", "queen",
        "river", "robot", "shadow", "shark", "shell", "ship", "snake", "spoon",
        "star", "stone", "storm", "table", "tiger", "tower", "train", "whale",
    )

    def __init__(self, hardcore: Optional[bool] = False, max_turns: int = 80):
        if not isinstance(hardcore, bool):
            raise ValueError("hardcore must be a boolean")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer")
        self._load_word_list(hardcore=hardcore)
        self.max_turns = max_turns

    def _load_word_list(self, hardcore: bool = False) -> None:
        try:
            word_list = words.words("en-basic" if not hardcore else "en")
            noun_mask = [tag == "NN" for _, tag in pos_tag(word_list)]
            candidates = [w.lower() for w, is_noun in zip(word_list, noun_mask) if is_noun]
        except LookupError:
            # Importing an environment must never trigger a network download.
            candidates = list(self._FALLBACK_WORDS)
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
            "1. The Spymaster gives a one-word clue + number (e.g., 'wind 2') based on the team's secret words (the clue may not contain any of the words on the board).\n"
            "2. The Operative guesses up to N+1 words, one at a time (e.g., 'breeze') based on the clue. They can also 'pass'.\n"
            "3. Avoid guessing opponent words, neutral words (N), or the Assassin (A), which causes instant loss.\n"
            "4. First team to guess all their words wins.\n\n"
        )
        if player_id in [0, 2]: return prompt + f"You are Player {player_id}, the Spymaster for {'Red' if player_id == 0 else 'Blue'} team. Give a one-word clue and number."
        else:                   return prompt + f"You are Player {player_id}, the Operative for {'Red' if player_id == 1 else 'Blue'} team. Guess words based on the clue."

    def render(self, player_id: int) -> str:
        view = "Codenames Words:\n"
        for word in list(self.board.keys()):
            if player_id in [0, 2]: view += f"{word:<8} {self.board[word]} {'revealed' if word in self.game_state['guessed_words'] else ''}\n" # Show the team label for spymasters
            else:                   view += f"{word:<8} {self.board[word] if word in self.game_state['guessed_words'] else ''}\n"
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
