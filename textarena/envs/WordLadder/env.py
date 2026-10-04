import re
from collections import deque
from typing import Any, Dict, List, Tuple, Union

import textarena as ta
from textarena.envs.WordLadder.renderer import create_board_str
from textarena.utils.word_lists import EnglishDictionary


from nltk.corpus import words


class WordLadderEnv(ta.GameEnv):
    """Single-player Word Ladder environment without networkx."""

    min_players = 1
    max_players = 1
    action_pattern = r"^\s*\[?\s*([a-zA-Z]+)\s*\]?\s*$"
    snapshot_excluded_attributes = ("universal_word_list", "word_list")

    def __init__(self, min_distance: int = 5, max_distance: int = 7, max_turns: int = 100):
        """
        Args:
            min_distance: minimum number of letter-change steps between start and target
            max_distance: maximum number of letter-change steps between start and target
            max_turns:    maximum turns before the game ends in a loss
        """
        if (
            not isinstance(min_distance, int)
            or isinstance(min_distance, bool)
            or min_distance < 1
        ):
            raise ValueError("min_distance must be a positive integer.")
        if (
            not isinstance(max_distance, int)
            or isinstance(max_distance, bool)
            or max_distance < min_distance
        ):
            raise ValueError("max_distance must be an integer greater than or equal to min_distance.")
        if not isinstance(max_turns, int) or isinstance(max_turns, bool) or max_turns < 1:
            raise ValueError("max_turns must be a positive integer.")
        if max_turns < max_distance:
            raise ValueError("max_turns must be at least max_distance so every sampled puzzle is solvable.")
        self.min_distance = min_distance
        self.max_distance = max_distance
        self.max_turns = max_turns
        try:
            source_words = words.words("en-basic")
        except LookupError:
            dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=False)
            source_words = dictionary.get_all_words()
        self.word_list = sorted(
            {
                word.lower()
                for word in source_words
                if isinstance(word, str)
                and word.isascii()
                and word.isalpha()
                and 3 <= len(word) <= 11
            }
        )
        if not self.word_list:
            raise ValueError("The dictionary contains no playable Word Ladder words.")
        self.universal_word_list = self._load_universal_word_list()

    def _load_universal_word_list(self):
        """Use the same normalized vocabulary for generation and validation."""
        return set(self.word_list)

    @staticmethod
    def _one_letter_diff(w1: str, w2: str) -> bool:
        """True when w1 and w2 differ in exactly one position."""
        return len(w1) == len(w2) and sum(a != b for a, b in zip(w1, w2)) == 1

    @staticmethod
    def _build_neighbor_map(words_of_same_len: List[str]) -> Dict[str, List[str]]:
        """For every word, pre-compute the list of neighbours one letter away."""
        word_set = set(words_of_same_len)
        neighbours: Dict[str, List[str]] = {w: [] for w in words_of_same_len}
        alphabet = "abcdefghijklmnopqrstuvwxyz"

        for word in words_of_same_len:
            for i, orig_ch in enumerate(word):
                for ch in alphabet:
                    if ch == orig_ch:
                        continue
                    candidate = word[:i] + ch + word[i + 1 :]
                    if candidate in word_set:
                        neighbours[word].append(candidate)
        return neighbours

    def _find_valid_pairs(self, neighbours: Dict[str, List[str]], min_steps: int, max_steps: int) -> List[Tuple[str, str, List[str]]]:
        """
        BFS from each word to collect (start, target, path) triples whose
        path length ∈ [min_steps, max_steps].  Stops early when distance limit
        is exceeded.  Complexity is manageable because we work per word-length
        bucket and cut off BFS at max_steps.
        """
        valid_pairs = []
        for start in neighbours.keys():
            visited = {start}
            q = deque([(start, [start])])  # (current_word, path_so_far)

            while q:
                current, path = q.popleft()
                dist = len(path) - 1
                if dist > max_steps:
                    continue
                # Avoid (start, start) and enforce distance range
                if start != current and min_steps <= dist <= max_steps:
                    valid_pairs.append((start, current, path))

                if dist == max_steps:
                    continue  # No deeper search past distance cap

                for nxt in neighbours[current]:
                    if nxt not in visited:
                        visited.add(nxt)
                        q.append((nxt, path + [nxt]))
        return valid_pairs

    def _sample_start_target(self) -> Tuple[str, str]:
        """ Pick word length, build neighbour map, then randomly select a (start, target) pair whose shortest path fits distance constraints """
        lengths = list(range(3, 12))
        self.rng.shuffle(lengths)
        for length in lengths:
            bucket = [word for word in self.word_list if len(word) == length]
            if len(bucket) < 2:  # Not enough words to form a ladder
                continue

            neighbours = self._build_neighbor_map(bucket)
            starts = list(neighbours)
            self.rng.shuffle(starts)
            for start in starts:
                distances = {start: 0}
                q = deque([start])
                candidates = []
                while q:
                    current = q.popleft()
                    distance = distances[current]
                    if self.min_distance <= distance <= self.max_distance:
                        candidates.append(current)
                    if distance == self.max_distance:
                        continue
                    for nxt in neighbours[current]:
                        if nxt not in distances:
                            distances[nxt] = distance + 1
                            q.append(nxt)
                if candidates:
                    return start, self.rng.choice(candidates)
        raise ValueError(
            f"No word-ladder pair exists between {self.min_distance} and "
            f"{self.max_distance} steps in the configured dictionary."
        )

    # Convenience accessors kept for renderers/tests; game data lives in game_state.
    @property
    def start_word(self) -> str:
        return self.game_state["start_word"]

    @property
    def target_word(self) -> str:
        return self.game_state["target_word"]

    @property
    def current_word(self) -> str:
        return self.game_state["current_word"]

    @property
    def history(self) -> List[str]:
        return self.game_state["history"]

    def setup(self) -> Dict[str, Any]:
        start_word, target_word = self._sample_start_target()
        game_state = {
            "start_word": start_word, "target_word": target_word,
            "current_word": start_word, "history": [start_word],
        }
        game_state["rendered_text"] = f"Word Ladder History: {' -> '.join(game_state['history'])}.  Target Word: {target_word}\n"
        return game_state

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def _render_text(self) -> str:
        return f"Word Ladder History: {' -> '.join(self.history)}.  Target Word: {self.target_word}\n"

    def prompt(self, player_id: int) -> str:
        return (
            f"You are Player {player_id}.  Your goal is to reach the target word "
            "by changing **one letter at a time**.\n"
            f"- Start word:  **{self.start_word}**\n"
            f"- Target word: **{self.target_word}**\n"
            "Submit each move as the word itself, e.g.  `word`.\n"
            "History appears below as you play.  Good luck!\n"
        )

    def apply(self, player_id: int, move: re.Match) -> Union[ta.Outcome, ta.Invalid, None]:
        gs = self.game_state
        next_word = move.group(1).lower()

        # Validation checks
        if len(next_word) != len(self.target_word):
            return self.invalid(f"`{next_word}` has wrong length; target is {len(self.target_word)} letters.")
        if next_word not in self.universal_word_list:
            return self.invalid(f"`{next_word}` is not a recognised English word.")
        if not self._one_letter_diff(self.current_word, next_word):
            return self.invalid(f"`{next_word}` is not exactly one letter different from `{self.current_word}`.")

        gs["current_word"] = next_word
        gs["history"].append(next_word)
        gs["rendered_text"] = self._render_text()

        if next_word == self.target_word:
            return self.outcome({0: 1}, reason="Congratulations! You reached the target word.")
        self.message(player_id, f"Nice! Keep going.\n{self._render_text()}", ta.ObservationType.GAME_MESSAGE)
        return None

    def on_turn_limit(self) -> ta.Outcome:
        pct_complete = self._get_percentage_completion()
        reason = f"The turn limit has been reached. You reached `{self.current_word}` which shares {round(pct_complete * 100)}% of its letters with the target `{self.target_word}`."
        return self.outcome({0: pct_complete}, reason=reason)

    def on_invalid_limit(self, player_id: int, reason: str) -> ta.Outcome:
        return self.outcome({0: self._get_percentage_completion()}, reason=f"Invalid Move: {reason}")

    def _get_percentage_completion(self) -> float:
        """ Compute the percentage of matching letters between current and target word. Returns a float in [0.0, 1.0] """
        matches = sum(c1 == c2 for c1, c2 in zip(self.current_word, self.target_word))
        return matches / len(self.target_word)
