import functools
import json
import importlib.resources
import os
import re
import unicodedata
from typing import Optional, Set, Tuple, Dict, List, Any, Union

import textarena as ta

_TOKEN = re.compile(r"[^\W_]+")
_ARTICLES = frozenset({"a", "an", "the"})
# Words of a multi-word target that a clue may still use (e.g. "of" for "The Lord of the Rings").
_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "nor", "if", "so", "as", "than", "then", "not", "no",
    "at", "by", "for", "from", "in", "into", "of", "off", "on", "onto", "out", "over", "to", "up", "upon",
    "with", "without", "i", "me", "my", "you", "your", "he", "him", "his", "she", "her", "it", "its", "we",
    "us", "our", "they", "them", "their", "is", "are", "was", "were", "be", "been", "am", "do", "does", "did",
    "de", "del", "der", "des", "di", "du", "el", "en", "la", "le", "les", "und", "van", "von",
})
# Lowercase Cyrillic, Greek and Latin letters that render like the Latin letter they map to.
_CONFUSABLES = str.maketrans({
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o", "р": "p", "с": "c", "т": "t",
    "у": "y", "х": "x", "ѕ": "s", "і": "i", "ј": "j", "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ӏ": "l",
    "α": "a", "β": "b", "γ": "y", "ε": "e", "η": "n", "ι": "i", "κ": "k", "ν": "v", "ο": "o", "ρ": "p",
    "τ": "t", "υ": "u", "χ": "x", "ı": "i", "ɑ": "a", "ɡ": "g",
})
_IN_WORD_GAP = r"(?:[^\w\s]|_)*"  # punctuation splitting a word, as in "ca-mel" or "U.S.A."


@functools.lru_cache(maxsize=4096)
def _phrase_pattern(tokens: Tuple[str, ...]) -> "re.Pattern[str]":
    """Whole-word pattern for a forbidden word or phrase in match form."""
    parts = [_IN_WORD_GAP.join(map(re.escape, tokens[0]))]
    for previous, token in zip(tokens, tokens[1:]):
        # Words may run together ("icecream"), but single letters need a separator so
        # that "U.S." does not match the word "us".
        gap = r"[\W_]*" if len(previous) > 1 and len(token) > 1 else r"[\W_]+"
        parts.append(gap + _IN_WORD_GAP.join(map(re.escape, token)))
    return re.compile(r"(?<![^\W_])" + "".join(parts) + r"(?![^\W_])")


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

    @staticmethod
    def _match_form(value: str) -> str:
        """Text as the rules compare it: case, accents, invisible characters and look-alike letters ignored."""
        decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value).casefold())
        kept = "".join(
            char for char in decomposed if not unicodedata.combining(char) and unicodedata.category(char) != "Cf"
        )
        return " ".join(kept.translate(_CONFUSABLES).split())

    @staticmethod
    def _without_parentheticals(text: str) -> str:
        """Drop qualifiers in parentheses, e.g. 'Kabul (Afghanistan)' -> 'Kabul'."""
        kept, depth = [], 0
        for char in text:
            if char == "(":
                depth += 1
            elif char == ")" and depth:
                depth -= 1
            elif not depth:
                kept.append(char)
        return " ".join("".join(kept).split())

    @classmethod
    def _contains_forbidden_word(cls, action: str, forbidden_words: List[str]) -> bool:
        """Match whole words and phrases, also when split by punctuation or spelled out letter by letter."""
        text = cls._match_form(action)
        spelled_out, run = [], []
        for token in _TOKEN.findall(text) + [""]:
            if len(token) == 1:
                run.append(token)
                continue
            if len(run) > 1:
                spelled_out.append("".join(run))
            run = []
        for forbidden in forbidden_words:
            tokens = tuple(_TOKEN.findall(cls._match_form(forbidden)))
            if not tokens:
                continue
            if _phrase_pattern(tokens).search(text):
                return True
            joined = "".join(tokens)
            if len(joined) > 1 and any(joined in letters for letters in spelled_out):
                return True
        return False

    def _forbidden_words(self) -> List[str]:
        """The target, every taboo word, and each significant word of the target on its own."""
        gs = self.game_state
        core = _TOKEN.findall(self._match_form(self._without_parentheticals(gs["word_to_guess"])))
        target_words = [word for word in core if len(word) > 1 and word not in _FUNCTION_WORDS]
        return [gs["word_to_guess"], *gs["taboo_words"], *target_words]

    @classmethod
    def _answer_keys(cls, text: str) -> Set[str]:
        """Comparison keys of a guess or answer: letters and digits only, a leading article optional."""
        tokens = _TOKEN.findall(cls._match_form(text))
        keys = {"".join(tokens)}
        if len(tokens) > 1 and tokens[0] in _ARTICLES:
            keys.add("".join(tokens[1:]))
        keys.discard("")
        return keys

    @classmethod
    def _is_correct_guess(cls, guess: str, target: str) -> bool:
        """Also accept the target without parenthesized qualifiers or an inverted official-name suffix."""
        names = {target, cls._without_parentheticals(target)}
        for name in list(names):
            inverted = re.fullmatch(r"(.+?),\s*[^,]*\bof", name, re.IGNORECASE)  # "Palestine, State of"
            if inverted:
                names.add(inverted.group(1))
        answers = set().union(*(cls._answer_keys(name) for name in names))
        return bool(cls._answer_keys(guess) & answers)

    @classmethod
    def _parse_guess(cls, action: str) -> Optional[str]:
        """Return the guess text, or None for malformed text."""
        if not isinstance(action, str) or any(char in action for char in "\r\n"):
            return None
        guess = action.strip()
        if not guess or any(unicodedata.category(char).startswith("C") for char in guess):
            return None
        if not any(char.isalpha() or char.isdigit() for char in guess):
            return None
        return guess

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
                    or not _TOKEN.search(target)  # a guess needs a letter or digit to match
                    or not isinstance(taboo_words, list)
                    or any(not isinstance(word, str) for word in taboo_words)
                ):
                    raise ValueError(f"Category '{category}' contains an invalid word entry.")
                # Empty entries in the data carry no rule and must not become
                # an empty regex alternative that rejects every possible clue.
                clean_target = self._clean_text(target)
                clean_taboo_words = [
                    self._clean_text(word) for word in taboo_words if word.strip()
                ]
                data[clean_target] = clean_taboo_words

        if not data:
            raise ValueError(f"No words found for selected categories: {', '.join(self.categories)}")
        return data

    def check_num_players(self, num_players: int) -> None:
        if num_players % 2:
            raise ValueError(f"Taboo needs an even number of players (two equal teams), received {num_players}.")

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
        scoring = (
            "Each correct guess scores a point for the team, and the team moves on to its next word. "
            f"After {self.max_rounds} rounds (one turn per team each), the team with more points wins; equal scores draw.\n"
            f"Each player may make up to {self.max_attempts_per_player} actions during each team turn.\n"
        )
        if self.state.role_mapping[player_id] == "Clue Giver":
            return (
                f"You are Player {player_id}, the Clue Giver for Team {team_id} in the Taboo game.\n"
                "Your goal is to provide clues that help your teammates guess the word without using the taboo words or the word to guess.\n"
                "A clue must not contain the word to guess, any of its words (short words such as 'the' or 'of' excepted), or a taboo word. "
                "Case, accents, punctuation, look-alike letters and spelling a word out letter by letter do not get around this. "
                "Such a clue is rejected; a second rejected clue in a row costs your team its current word and ends its turn.\n"
                + scoring
                + "On your turn, simply type your clue.\n"
            )
        else:
            return (
                f"You are Player {player_id}, a Guesser for Team {team_id} in the Taboo game.\n"
                "Your goal is to guess the secret word based on the clues provided by your team's Clue Giver.\n"
                + scoring
                + "On your turn, simply reply with your guess on a single line. For example: 'elephant'. "
                "Case, accents, punctuation and a leading 'the' or 'a' are ignored, and a qualifier in parentheses may be left out "
                "(e.g. 'Kabul' for 'Kabul (Afghanistan)').\n"
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
        # Rules are checked on exactly the text teammates will see.
        text = self.strip_role_tags(action)
        if self.state.role_mapping[player_id] == "Clue Giver":
            if not text.strip():
                return self.invalid("The clue must not be empty.")
            if self._contains_forbidden_word(text, self._forbidden_words()):
                return self.invalid(f"The Clue Giver (Player {player_id}) mentioned a taboo word, or the target word.")
            next_player = self._next_player_within_team(player_id)
            correct_guess = False

        else:  # Guesser
            guess = self._parse_guess(text)
            if guess is None:
                return self.invalid("Invalid guess format. Please reply with just your guess, e.g., 'apple'.")
            correct_guess = self._is_correct_guess(guess, gs["word_to_guess"])
            next_player = gs["current_team"] * self.team_size if correct_guess else self._next_player_within_team(player_id)

        # Invalid actions must not mutate state or enter a teammate's observation.
        for teammate_id in self._get_team_members(player_id):
            self.message(teammate_id, text, ta.ObservationType.PLAYER_ACTION, from_id=player_id)
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
