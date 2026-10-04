import json
import importlib.resources
import os
import re
import unicodedata
from typing import Optional, Tuple, Dict, List, Any, Union

import textarena as ta


class TabooEnv(ta.GameEnv):
    """ Environment for Taboo Game. """
    min_players = 4
    max_players = None  # any even count >= 4 (two teams)
    snapshot_excluded_attributes = ("data",)

    def __init__(
        self,
        categories: Union[str, List[str]],
        max_rounds: int,
        max_attempts_per_player: int,
        data_path: Optional[str] = None,
    ):
        """
        Initialize the Taboo game environment.
        Args:
            categories (Union[str, List[str]]): Either a single category or a list of categories to include in the game.
            max_rounds (int): Maximum number of rounds.
            max_attempts_per_player (int): Attempts per player per round.
            data_path (str, optional): Path to the JSON file containing the taboo words.
        """
        if isinstance(categories, str):
            categories = [categories]
        elif isinstance(categories, list):
            categories = list(categories)
        else:
            raise ValueError("categories must be a category name or a list of category names.")
        if not categories or any(not isinstance(category, str) or not category.strip() for category in categories):
            raise ValueError("At least one non-empty category must be provided.")
        if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 1:
            raise ValueError("max_rounds must be a positive integer.")
        if (
            not isinstance(max_attempts_per_player, int)
            or isinstance(max_attempts_per_player, bool)
            or max_attempts_per_player < 1
        ):
            raise ValueError("max_attempts_per_player must be a positive integer.")

        self.categories = categories
        self.max_rounds = max_rounds
        self.max_attempts_per_player = max_attempts_per_player
        self.data_path = data_path

    @property
    def terminal_render_keys(self):
        return ["word_to_guess", "taboo_words"]

    @staticmethod
    def _clean_text(value: str) -> str:
        """Normalize configured text while preserving its display casing."""
        return " ".join(unicodedata.normalize("NFKC", value).split())

    @classmethod
    def _normalize_for_match(cls, value: str) -> str:
        normalized = cls._clean_text(value).casefold()
        return "".join(
            char for char in normalized if unicodedata.category(char) != "Cf"
        )

    @classmethod
    def _contains_forbidden_word(cls, action: str, forbidden_words: List[str]) -> bool:
        """Match words and multi-word phrases across harmless separator variants."""
        normalized_action = cls._normalize_for_match(action)
        for forbidden in forbidden_words:
            normalized_word = cls._normalize_for_match(forbidden)
            if not normalized_word:
                continue

            exact_pattern = re.compile(r"(?<!\w)" + re.escape(normalized_word) + r"(?!\w)")
            if exact_pattern.search(normalized_action):
                return True

            # A phrase cannot be evaded by replacing spaces with punctuation,
            # e.g. "ice-cream" for the forbidden phrase "ice cream".
            tokens = re.findall(r"[^\W_]+", normalized_word, re.UNICODE)
            if len(tokens) > 1:
                phrase_pattern = re.compile(
                    r"(?<!\w)" + r"[\W_]+".join(map(re.escape, tokens)) + r"(?!\w)"
                )
                if phrase_pattern.search(normalized_action):
                    return True
        return False

    @classmethod
    def _parse_guess(cls, action: str) -> Optional[str]:
        """Return a normalized title-like guess, or None for malformed text."""
        if not isinstance(action, str) or any(char in action for char in "\r\n"):
            return None
        guess = action.strip()
        if guess.startswith("[") and guess.endswith("]"):
            guess = guess[1:-1].strip()
        if not guess or any(unicodedata.category(char).startswith("C") for char in guess):
            return None
        if not any(char.isalpha() or char.isdigit() for char in guess):
            return None
        return cls._normalize_for_match(guess)

    def _load_data(self, data_path: Optional[str] = None) -> Dict[str, List[str]]:
        """Load the word list based on the specified categories from the JSON file."""
        if data_path is not None:
            if not os.path.isfile(data_path):
                raise FileNotFoundError(f"Taboo words data file not found at: {data_path}")
            with open(data_path, "r", encoding="utf-8") as file:
                full_data = json.load(file)
        else:
            with importlib.resources.files("textarena.envs.Taboo").joinpath("words.json").open(
                "r", encoding="utf-8"
            ) as file:
                full_data = json.load(file)

        if not isinstance(full_data, dict):
            raise ValueError("Taboo data must be a JSON object keyed by category.")
        missing_categories = [category for category in self.categories if category not in full_data]
        if missing_categories:
            raise ValueError(f"Categories not found in data file: {', '.join(missing_categories)}")

        data: Dict[str, List[str]] = {}
        for category in self.categories:
            category_data = full_data[category]
            if not isinstance(category_data, dict):
                raise ValueError(f"Category '{category}' must contain a mapping of targets to taboo words.")
            for target, taboo_words in category_data.items():
                if (
                    not isinstance(target, str)
                    or not target.strip()
                    or not isinstance(taboo_words, list)
                    or any(not isinstance(word, str) for word in taboo_words)
                ):
                    raise ValueError(f"Category '{category}' contains an invalid word entry.")
                # Empty entries in legacy data carry no rule and must not become
                # an empty regex alternative that rejects every possible clue.
                clean_target = self._clean_text(target)
                clean_taboo_words = [
                    self._clean_text(word) for word in taboo_words if word.strip()
                ]
                data[clean_target] = clean_taboo_words

        if not data:
            raise ValueError(f"No words found for selected categories: {', '.join(self.categories)}")
        return data

    def reset(self, num_players: int, seed: Optional[int] = None):
        assert num_players % 2 == 0, "Number of players must be even for Taboo game."
        assert num_players >= 4, "Taboo game requires at least 4 players."
        super().reset(num_players=num_players, seed=seed)

    def setup(self) -> Dict[str, Any]:
        self.data = self._load_data(self.data_path)
        num_players = self.state.num_players
        num_teams = 2
        self.team_size = num_players // num_teams

        # Give both teams the full pool in independently shuffled orders. A fixed
        # 20-card slice made long registered games crash after enough correct guesses.
        all_pairs = list(self.data.items())
        team_word_pairs = {}
        for team_id in range(num_teams):
            team_word_pairs[team_id] = all_pairs.copy()
            self.rng.shuffle(team_word_pairs[team_id])

        word_to_guess, taboo_words = team_word_pairs[0][0]
        return {
            "word_to_guess": word_to_guess,
            "taboo_words": taboo_words,
            "team_word_pairs": team_word_pairs,
            "team_word_indices": {team_id: 0 for team_id in range(num_teams)},
            "current_team": 0,
            "round": 1,
            "max_rounds": self.max_rounds,
            "turn_in_round": 0,
            "max_turns_per_round": self.max_attempts_per_player * (num_players // num_teams),
            "score": {team_id: 0 for team_id in range(num_teams)},
        }

    def roles(self) -> Dict[int, str]:
        # The first player of each team is the Clue Giver, the rest are Guessers.
        return {pid: ("Clue Giver" if pid % self.team_size == 0 else "Guesser") for pid in range(self.state.num_players)}

    def prompt(self, player_id: int) -> str:
        team_id = self._get_team_id(player_id)
        if self.state.role_mapping[player_id] == "Clue Giver":
            return (
                f"You are Player {player_id}, the Clue Giver for Team {team_id} in the Taboo game.\n"
                "Your goal is to provide clues to help the Guesser guess the word without using the taboo words or the word to guess.\n"
                f"Each player may make up to {self.max_attempts_per_player} actions during each team turn.\n"
                "On your turn, simply type your clue.\n"
            )
        else:
            return (
                f"You are Player {player_id}, the Guesser for Team {team_id} in the Taboo game.\n"
                "Your goal is to guess the secret word based on the clues provided by the Clue Giver.\n"
                f"Each player may make up to {self.max_attempts_per_player} actions during each team turn.\n"
                "On your turn, simply reply with your guess. For example: 'elephant'.\n"
            )

    def on_start(self):
        # Tell the starting Clue Giver the first word.
        gs = self.game_state
        if self.state.role_mapping[self.state.current_player_id] == "Clue Giver":
            self.message(self.state.current_player_id, f"The current word to guess is '{gs['word_to_guess']}'. Taboo words: {', '.join(gs['taboo_words'])}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def action_echo_target(self, player_id: int, action: str) -> Optional[int]:
        return None  # actions are echoed only to the acting player's team, inside apply

    def apply(self, player_id: int, action: str) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        if self.state.role_mapping[player_id] == "Clue Giver":
            if not action.strip():
                return self.invalid("The clue must not be empty.")
            forbidden_words = gs["taboo_words"] + [gs["word_to_guess"]]
            if self._contains_forbidden_word(action, forbidden_words):
                return self.invalid(f"The Clue Giver (Player {player_id}) mentioned a taboo word, or the target word.")
            next_player = self._next_player_within_team(player_id)
            correct_guess = False

        else:  # Guesser
            guess = self._parse_guess(action)
            if guess is None:
                return self.invalid("Invalid guess format. Please reply with just your guess, e.g., 'apple'.")
            correct_guess = guess == self._normalize_for_match(gs["word_to_guess"])
            next_player = gs["current_team"] * self.team_size if correct_guess else self._next_player_within_team(player_id)

        # Invalid actions must not mutate state or enter a teammate's observation.
        for teammate_id in self._get_team_members(player_id):
            self.message(teammate_id, action, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
        gs["turn_in_round"] += 1

        if correct_guess:
            current_team = gs["current_team"]
            gs["score"][current_team] += 1
            gs["team_word_indices"][current_team] += 1
            self.broadcast(
                f"Team {current_team} scored a point! Current score: {gs['score']}",
                ta.ObservationType.GAME_ACTION_DESCRIPTION,
            )

        if self._is_end_of_round():
            return self._finish_team_turn()

        if correct_guess:
            current_team = gs["current_team"]
            if gs["team_word_indices"][current_team] >= len(gs["team_word_pairs"][current_team]):
                return self._final_outcome("The word pool was exhausted.")
            self._update_word_for_team(current_team)
            self._notify_clue_givers_new_word(current_team, "The next word to guess is")

        self.set_next_player(next_player)
        return None

    def on_invalid_limit(self, player_id: int, reason: str) -> Optional[ta.Outcome]:
        if self.state.role_mapping[player_id] == "Clue Giver":
            # Penalty: the team loses the current word and play passes to the next team.
            gs = self.game_state
            gs["team_word_indices"][gs["current_team"]] += 1
            return self._finish_team_turn()
        # Repeated malformed guesses forfeit one action so adversarial text cannot
        # hold the game on the same player forever.
        gs = self.game_state
        gs["turn_in_round"] += 1
        if self._is_end_of_round():
            return self._finish_team_turn()
        self.set_next_player(self._next_player_within_team(player_id))
        return None

    # ------------------------------------------------------------ team helpers
    def _get_team_id(self, player_id: int) -> int:
        return player_id // self.team_size

    def _get_team_members(self, player_id: int) -> List[int]:
        team_id = self._get_team_id(player_id)
        return [pid for pid in range(self.state.num_players) if pid // self.team_size == team_id]

    def _get_next_team(self, current_team: int) -> int:
        return (current_team + 1) % (self.state.num_players // self.team_size)

    def _next_player_within_team(self, player_id: int) -> int:
        team_id = self._get_team_id(player_id)
        return team_id * self.team_size + (player_id % self.team_size + 1) % self.team_size

    # ------------------------------------------------------------- game logic
    def _is_end_of_round(self) -> bool:
        return self.game_state["turn_in_round"] >= self.game_state["max_turns_per_round"]

    def _switch_to_next_team(self) -> int:
        gs = self.game_state
        next_team = self._get_next_team(gs["current_team"])
        gs["current_team"] = next_team
        gs["turn_in_round"] = 0
        if next_team == 0:
            gs["round"] += 1
        return next_team

    def _get_current_word_for_team(self, team_id: int) -> Tuple[str, List[str]]:
        gs = self.game_state
        current_word_idx = gs["team_word_indices"][team_id]
        team_words = gs["team_word_pairs"][team_id]
        if current_word_idx >= len(team_words):
            raise ValueError(f"Team {team_id} has no more words available.")
        return team_words[current_word_idx]

    def _update_word_for_team(self, team_id: int) -> None:
        word_to_guess, taboo_words = self._get_current_word_for_team(team_id)
        self.game_state["word_to_guess"] = word_to_guess
        self.game_state["taboo_words"] = taboo_words

    def _notify_clue_givers_new_word(self, team_id: int, team_message: str) -> None:
        gs = self.game_state
        message = f"{team_message} The word to guess is '{gs['word_to_guess']}'. Taboo words: {', '.join(gs['taboo_words'])}."
        for pid in range(self.state.num_players):
            if pid // self.team_size == team_id and self.state.role_mapping[pid] == "Clue Giver":
                self.message(pid, message, ta.ObservationType.GAME_ACTION_DESCRIPTION)

    def _notify_team_switch(self, next_team: int) -> None:
        self.broadcast(f"Team {1 - next_team} has finished their turn. It is now Team {next_team}'s turn to play.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self._notify_clue_givers_new_word(next_team, f"It is Team {next_team}'s turn now.")

    def _finish_team_turn(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        next_team = self._switch_to_next_team()
        outcome = self._check_game_end()
        if outcome is not None:
            return outcome
        if gs["team_word_indices"][next_team] >= len(gs["team_word_pairs"][next_team]):
            return self._final_outcome("The word pool was exhausted.")
        self._update_word_for_team(next_team)
        self.set_next_player(next_team * self.team_size)
        self._notify_team_switch(next_team)
        return None

    def _check_game_end(self) -> Optional[ta.Outcome]:
        gs = self.game_state
        if gs["round"] <= gs["max_rounds"]:
            return None
        return self._final_outcome(f"All {self.max_rounds} rounds were completed.")

    def _final_outcome(self, prefix: str) -> ta.Outcome:
        gs = self.game_state
        scores = gs["score"]
        max_score = max(scores.values())
        winning_teams = [team_id for team_id, score in scores.items() if score == max_score]
        if len(winning_teams) == 1:
            winning_team = winning_teams[0]
            team_members = [i for i in range(self.state.num_players) if i // self.team_size == winning_team]
            return self.winner(team_members, reason=f"{prefix} Team {winning_team} won with score {max_score}.")
        return self.draw(reason=f"{prefix} The game ended in a draw with both teams scoring {max_score}.")
