import re, random
from collections import deque
from typing import Any, Dict, List, Tuple, Optional

import textarena as ta
from textarena.envs.WordLadder.renderer import create_board_str
from textarena.envs.utils.word_lists import (
    EnglishDictionary,
    WordFreqDictionary,
    NON_ALPHABETIC_LANGS,
)


# NLTK is only needed to fetch the basic word list
import nltk
from nltk.corpus import words
nltk.download("words")


class WordLadderEnv(ta.Env):
    """Single-player Word Ladder environment without networkx."""

    # Performance cap: for non-English languages the wordfreq pool is ~40k words,
    # so a same-length bucket can hold several thousand entries. Building the
    # one-letter-difference neighbour graph (and BFS-ing over it) across all of
    # them is slow, so we only consider the most-frequent N words of each length.
    # English keeps its (small) en-basic buckets uncapped, exactly as before.
    _ML_BUCKET_CAP = 1500

    def __init__(self, min_distance: int=5, max_distance: int=7, max_turns: int=100):
        """
        Args:
            min_distance: minimum number of letter-change steps between start and target
            max_distance: maximum number of letter-change steps between start and target
            max_turns:    maximum turns before the game ends in a loss
        """
        super().__init__()
        self.min_distance = min_distance
        self.max_distance = max_distance
        self.max_turns = max_turns
        # English path is built eagerly and left exactly as before (no new deps,
        # byte-identical output). Non-English content languages are handled
        # lazily via the optional wordfreq backend (see _ml_word_universe).
        self.word_list = words.words("en-basic") # Source word lists
        self.universal_word_list = self._load_universal_word_list()
        self._en_word_list = self.word_list
        self._en_universal_word_list = self.universal_word_list
        # Per-language caches so the (expensive) neighbour-map build happens
        # once per language rather than once per reset.
        self._ml_dicts: Dict[str, Any] = {}
        self._ml_pool_cache: Dict[str, Tuple[List[str], set]] = {}
        self._ml_neighbor_cache: Dict[str, Dict[int, Dict[str, List[str]]]] = {}

    def _load_universal_word_list(self):
        """Combine NLTK + US/UK spell-check dictionaries (no proper nouns)."""
        dictionary = EnglishDictionary(keep_proper_nouns=False, include_nltk=True)
        return dictionary.get_all_words()

    def _content_lang(self) -> str:
        """The single language the ladder words are drawn from for this episode.

        Word games are single-content-language (start/target/path are in one
        language); per-player UI language still varies via the locale layer.
        When players request different languages we take player 0's as the
        content language.
        """
        lang = getattr(self, "lang", "en")
        if isinstance(lang, dict):
            values = set(lang.values())
            return next(iter(values)) if len(values) == 1 else lang.get(0, "en")
        return lang or "en"

    # ---- non-English (wordfreq) word universe ---------------------------------
    def _ml_word_universe(self, lang: str) -> Tuple[List[str], set]:
        """Return (sampling word_list, validity word set) for a content language."""
        if lang in self._ml_pool_cache:
            return self._ml_pool_cache[lang]
        if lang in NON_ALPHABETIC_LANGS:
            raise ValueError(
                f"Word Ladder changes one letter at a time and does not support "
                f"the non-alphabetic language '{lang}'."
            )
        d = WordFreqDictionary(lang)
        universal = {w.lower() for w in d.get_all_words() if w.isalpha()}
        word_list = list(universal)
        self._ml_dicts[lang] = d
        self._ml_pool_cache[lang] = (word_list, universal)
        return self._ml_pool_cache[lang]

    def _ml_bucket(self, lang: str, length: int) -> List[str]:
        """Most-frequent (up to _ML_BUCKET_CAP) words of a given length."""
        word_list, _ = self._ml_word_universe(lang)
        bucket = [w for w in word_list if len(w) == length]
        if len(bucket) > self._ML_BUCKET_CAP:
            # Rank via the alias-resolved helper (sr/hr -> sh) so aliased langs don't
            # emit a per-word wordfreq "nearest match" warning during the sort.
            d = self._ml_dicts[lang]
            bucket.sort(key=lambda w: d.zipf(w), reverse=True)
            bucket = bucket[: self._ML_BUCKET_CAP]
        return bucket

    def _ml_neighbor_map(self, lang: str, length: int) -> Dict[str, List[str]]:
        """Cached neighbour map for a (language, length) bucket."""
        cache = self._ml_neighbor_cache.setdefault(lang, {})
        if length not in cache:
            cache[length] = self._build_neighbor_map(self._ml_bucket(lang, length))
        return cache[length]

    @staticmethod
    def _one_letter_diff(w1: str, w2: str) -> bool:
        """True when w1 and w2 differ in exactly one position."""
        return len(w1) == len(w2) and sum(a != b for a, b in zip(w1, w2)) == 1

    def _build_neighbor_map(self, words_of_same_len: List[str]) -> Dict[str, List[str]]:
        """For every word, pre-compute the list of neighbours one letter away.

        Uses the alphabet of the words themselves (rather than a hard-coded a-z),
        so accented / non-Latin scripts work too.
        """
        word_set = set(words_of_same_len)
        neighbours: Dict[str, List[str]] = {w: [] for w in words_of_same_len}
        alphabet = sorted({ch for w in words_of_same_len for ch in w})

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
        lengths_tried = [] # Try multiple lengths / attempts in case some buckets have no pairs

        while True:
            # Pick a word length between 3 and 11; avoid repeats if possible
            available_lengths = [L for L in range(3, 12) if L not in lengths_tried] or list(range(3, 12))
            length = random.choice(available_lengths)
            lengths_tried.append(length)

            bucket = [w.lower() for w in self.word_list if len(w) == length]
            if len(bucket) < 2:  # Not enough words to form a ladder
                continue

            neighbours = self._build_neighbor_map(bucket)
            pairs = self._find_valid_pairs(neighbours, self.min_distance, self.max_distance)
            if pairs:
                start, target, _ = random.choice(pairs)
                return start, target

    def _sample_start_target_ml(self, lang: str) -> Tuple[str, str]:
        """Non-English (start, target) sampling with graceful distance fallback.

        Uses cached, frequency-capped neighbour maps. If no pair exists at the
        configured distance we progressively relax the distance range rather
        than crash, so the cross-lingual smoke test always runs to completion.
        """
        lengths = list(range(3, 12))
        random.shuffle(lengths)
        schedules = [
            (self.min_distance, self.max_distance),
            (max(1, self.min_distance // 2), self.max_distance),
            (1, max(self.max_distance, 8)),
            (1, 30),
        ]
        for min_steps, max_steps in schedules:
            for length in lengths:
                neighbours = self._ml_neighbor_map(lang, length)
                if len(neighbours) < 2:
                    continue
                pairs = self._find_valid_pairs(neighbours, min_steps, max_steps)
                if pairs:
                    start, target, _ = random.choice(pairs)
                    return start, target
        raise RuntimeError(
            f"Word Ladder could not generate a start/target pair for language '{lang}'."
        )

    def get_board_str(self):
        return create_board_str(game_state=self.state.game_state)

    def _render_text(self) -> str:
        # Kept in fixed English form: this string is stored in game_state and
        # parsed structurally by the renderer (create_board_str). User-facing
        # progress messages are localized separately via self.m(...).
        return f"Word Ladder History: {' -> '.join(self.history)}.  Target Word: {self.target_word}\n"

    def _history_msg(self):
        """Localized 'Word Ladder History … Target Word …' line (neutral word tokens)."""
        return self.m("board", "history", ladder=" -> ".join(self.history), target=self.target_word)

    def _generate_player_prompt(self, player_id: int, game_state: Dict[int, Any]) -> str:
        return self.m("prompt", "intro", player_id=player_id, start_word=self.start_word, target_word=self.target_word)

    def reset(self, num_players: int, seed: Optional[int] = None):
        """Start a new game."""
        self.state = ta.SinglePlayerState(num_players=num_players, seed=seed, max_turns=self.max_turns)
        lang = self._content_lang()
        if lang == "en":
            # English path: unchanged eager word lists + original sampling.
            self.word_list = self._en_word_list
            self.universal_word_list = self._en_universal_word_list
            self.start_word, self.target_word = self._sample_start_target()
        else:
            word_list, universal = self._ml_word_universe(lang)
            self.word_list = word_list
            self.universal_word_list = universal
            self.start_word, self.target_word = self._sample_start_target_ml(lang)
        self.current_word = self.start_word
        self.history = [self.start_word]
        game_state = {"start_word": self.start_word, "target_word": self.target_word, "rendered_text": self._render_text()}
        self.state.reset(game_state=game_state, player_prompt_function=self._generate_player_prompt)

    def _is_one_alphabet_different(self, next_word: str) -> bool:
        """True if `next_word` differs from `self.current_word` by exactly one letter."""
        return self._one_letter_diff(self.current_word, next_word.lower())

    def step(self, action: str) -> Tuple[bool, ta.Info]:
        """Validate move, update state, and return (game_over, info)."""
        player_id = self.state.current_player_id
        self.state.add_observation(from_id=player_id, to_id=-1, message=action, observation_type=ta.ObservationType.PLAYER_ACTION)

        match = re.search(r"\[([^\W\d_]+)\]", action)
        if not match:
            self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "wrong_format"))
        else:
            next_word = match.group(1).lower()

            # Validation checks
            if len(next_word) != len(self.target_word):
                self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "wrong_length", word=next_word, target_len=len(self.target_word)))

            elif next_word not in self.universal_word_list:
                self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "not_a_word", word=next_word))

            elif not self._is_one_alphabet_different(next_word):
                self.state.set_invalid_move(reward=self._get_percentage_completion(), reason=self.m("invalid", "not_one_different", word=next_word, current=self.current_word))

            else:
                self.current_word = next_word
                self.history.append(next_word)

                if next_word == self.target_word:
                    self.state.set_outcome(reward=1, reason=self.m("outcome", "win"))
                else:
                    self.state.add_observation(from_id=ta.GAME_ID, to_id=player_id, message=self.m("feedback", "progress", history=self._history_msg()), observation_type=ta.ObservationType.GAME_MESSAGE)

        if self.state.check_turn_limit() and not self.state.done:
            pct_complete = self._get_percentage_completion()
            self.state.set_outcome(reward=pct_complete, reason=self.m("outcome", "turn_limit", current=self.current_word, pct=round(pct_complete * 100), target=self.target_word))

        # Update rendered text after every turn
        self.state.game_state["rendered_text"] = self._render_text()
        return self.state.step()


    def _get_percentage_completion(self) -> float:
        """ Compute the percentage of matching letters between current and target word. Returns a float in [0.0, 1.0] """
        matches = sum(c1 == c2 for c1, c2 in zip(self.current_word, self.target_word))
        return matches/len(self.target_word)
