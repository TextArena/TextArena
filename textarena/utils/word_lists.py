"""Utils for Word Lists, common to language games. (by Dilan Hillier)"""

import functools
import importlib.resources
import re
from collections import defaultdict

from nltk.corpus import words

# en.aff flags for regular inflections: plural (S), past tense (D), -ing (G),
# comparative (R) and superlative (T).
_INFLECTION_FLAGS = frozenset("SDGRT")


def _parse_affix_rules(file_content: list[str]):
    # Regular expression pattern to match the affix rules
    pattern = re.compile(r"^(PFX|SFX)\s+(\w+)\s+(Y|N)\s+(\S+)\s+([\'|\w]+)\s+(\S+)$")

    # Lists to store the parsed rules
    prefixes = defaultdict(list)
    suffixes = defaultdict(list)

    # Iterate over each line in the file content
    for line in file_content:
        match = pattern.match(line.strip())
        if match:
            affix_type, flag, can_merge, strip_char, affix, condition = match.groups()
            rule = {
                "flag": flag,
                "can_merge": can_merge == "Y",
                "strip_char": strip_char if strip_char != "0" else None,
                "affix": affix,
                "condition": condition if condition != "." else None,
            }
            if affix_type == "PFX":
                prefixes[flag].append(rule)
            else:
                suffixes[flag].append(rule)

    return prefixes, suffixes


def _parse_condition(condition):
    """Parse the condition string in the affix rules."""
    if not condition:
        return None, None
    pattern = re.compile(r"(\[\^\S+\])?(\S+)?")
    match = pattern.match(condition)
    if match:
        exclude, include = match.groups()
        return exclude, include
    return None, None


def _split(line: str) -> tuple[str, str]:
    """Split a line from a .dic file into a word and its flags."""
    if "/" in line:
        return tuple(line.split("/"))
    return line.strip(), ""


class EnglishDictionary:
    """Dictionary Utils for English words."""

    def __init__(
        self, keep_proper_nouns=False, include_nltk=True, keep_non_alpha=False
    ):
        """Initialize the dictionary."""
        self.include_nltk = include_nltk
        self.keep_non_alpha = keep_non_alpha
        self.keep_proper_nouns = keep_proper_nouns
        self.uk_words = self._load_dic("en_GB.dic", "en.aff")
        # self.uk_words = self.expand(self.uk_words, self.uk_affs)
        self.us_words = self._load_dic("en_US.dic", "en.aff")
        # self.us_words = self.expand(self.us_words, self.us_affs)
        self.nltk_words = self._load_nltk() if include_nltk else set()
        # Ogden's Basic English (NLTK's "en-basic"), bundled so it never depends on NLTK data.
        self.nltk_basic_words = self._filter(set(_load_basic_english()))

    def _filter(
        self,
        word_set: set[str],
    ) -> set[str]:
        filtered = set()
        for word in word_set:
            text = word[0] if isinstance(word, tuple) else word
            # Hunspell lists every letter as an entry; only "a" and "I" are English words.
            if len(text) == 1 and text.lower() not in {"a", "i"}:
                continue
            if word[0].isalpha() or self.keep_non_alpha:
                if word[0].islower() or self.keep_proper_nouns:
                    filtered.add(word)
        return filtered

    def _load_dic(
        self,
        filename: str,
        acc_filename: str,
    ) -> set[str]:
        """Load words from a .dic file inside the package's data folder."""
        with (
            importlib.resources.files("textarena.utils.data")
            .joinpath(filename)
            .open("r") as f
        ):
            lines = f.readlines()[1:]  # Skip first line (word count)
        with (
            importlib.resources.files("textarena.utils.data")
            .joinpath(acc_filename)
            .open("r") as f
        ):
            acc_lines = f.readlines()
        prefixes, suffixes = _parse_affix_rules(acc_lines)
        entries = set(_split(line) for line in lines)
        filtered = self._filter(entries)
        all_words = set()
        # first we add the base words
        for word, flag in filtered:
            all_words.add(word)
        prefixed_words = set()
        for word, flags in filtered:
            for flag in list(flags):
                if flag in prefixes:
                    # apply prefix
                    for rule in prefixes[flag]:
                        # check if the condition is met
                        exclude, include = _parse_condition(rule["condition"])
                        if exclude and any(
                            [word.endswith(exclude_char) for exclude_char in exclude]
                        ):
                            continue
                        if include and not word.endswith(include):
                            continue
                        if rule["strip_char"]:
                            if word.startswith(rule["strip_char"]):
                                new_word = (
                                    word[len(rule["strip_char"]) :] + rule["affix"]
                                )
                                all_words.add(new_word)
                                prefixed_words.add((new_word, flags))
                        else:
                            new_word = rule["affix"] + word
                            all_words.add(new_word)
                            prefixed_words.add(
                                (new_word, flags)
                            )  # may still need to apply suffixes
        for word, flags in filtered:
            for flag in list(flags):
                if flag in suffixes:
                    # apply suffix
                    for rule in suffixes[flag]:
                        # check if the condition is met
                        exclude, include = _parse_condition(rule["condition"])
                        if exclude and any(
                            [word.endswith(exclude_char) for exclude_char in exclude]
                        ):
                            continue
                        if include and not word.endswith(include):
                            continue
                        if rule["strip_char"]:
                            if word.endswith(rule["strip_char"]):
                                new_word = (
                                    word[: -len(rule["strip_char"])] + rule["affix"]
                                )
                                all_words.add(new_word)
                        else:
                            new_word = word + rule["affix"]
                            all_words.add(new_word)
        # finally we do merged prefixes and suffixes
        for word, flags in prefixed_words:
            for flag in list(flags):
                if flag in suffixes:
                    # apply suffix
                    for rule in suffixes[flag]:
                        # continue if flag is not mergeable
                        if not rule["can_merge"]:
                            continue
                        # check if the condition is met
                        exclude, include = _parse_condition(rule["condition"])
                        if exclude and word.endswith(exclude):
                            continue
                        if include and not word.endswith(include):
                            continue
                        if rule["strip_char"]:
                            if word.endswith(rule["strip_char"]):
                                new_word = (
                                    word[: -len(rule["strip_char"])] + rule["affix"]
                                )
                                all_words.add(new_word)
                        else:
                            new_word = word + rule["affix"]
                            all_words.add(new_word)
        all_words = self._filter(all_words)
        return all_words

    def _load_nltk(self) -> set[str]:
        try:
            nltk_words = set(words.words("en"))
        except LookupError:
            # The bundled UK/US dictionaries keep word games functional offline.
            return set()
        return self._filter(nltk_words)

    def is_english_word(self, word: str) -> bool:
        """Check if a word is in the UK and/or US and/or NLTK English dictionary."""
        word = word.lower()
        return word in self.uk_words or word in self.us_words or word in self.nltk_words

    def get_all_words(self) -> set[str]:
        """Get all words in the dictionary as a set"""
        return self.uk_words | self.us_words | self.nltk_words

    def get_basic_words(self) -> set[str]:
        """Get all words of Ogden's Basic English list (bundled; identical on every machine)"""
        return self.nltk_basic_words


@functools.lru_cache(maxsize=None)
def _load_basic_english() -> tuple[str, ...]:
    """The 850 words of Ogden's Basic English as shipped in en_basic.txt (exported from NLTK's "en-basic")."""
    with (
        importlib.resources.files("textarena.utils.data")
        .joinpath("en_basic.txt")
        .open("r", encoding="utf-8") as f
    ):
        return tuple(line.strip() for line in f if line.strip())


def get_basic_english_words() -> frozenset[str]:
    """Lowercase alphabetic words of Ogden's Basic English (the pronoun "I" excluded); needs no NLTK data."""
    return frozenset(word for word in _load_basic_english() if word.isalpha() and word.islower())


@functools.lru_cache(maxsize=None)
def _load_headword_flags(filename: str) -> dict[str, frozenset[str]]:
    """Map each lowercase ASCII entry of a bundled .dic file to its affix flags."""
    with (
        importlib.resources.files("textarena.utils.data")
        .joinpath(filename)
        .open("r", encoding="utf-8") as f
    ):
        lines = f.readlines()[1:]  # Skip first line (word count)
    flags = defaultdict(set)
    for line in lines:
        word, _, word_flags = line.strip().partition("/")
        if word.isascii() and word.isalpha() and word.islower():
            flags[word].update(word_flags)
    return {word: frozenset(word_flags) for word, word_flags in flags.items()}


@functools.lru_cache(maxsize=None)
def get_blocked_words() -> frozenset[str]:
    """Slurs, sexual and vulgar terms that games never draw as secret or board words."""
    with (
        importlib.resources.files("textarena.utils.data")
        .joinpath("blocked_words.txt")
        .open("r", encoding="utf-8") as f
    ):
        return frozenset(line.strip() for line in f if line.strip() and not line.startswith("#"))


@functools.lru_cache(maxsize=None)
def get_headwords() -> frozenset[str]:
    """Base words of the bundled UK and US dictionaries; needs no NLTK data.

    Lowercase ASCII entries of at least three letters that take at least one
    affix rule. The dictionaries store abbreviations and irregular inflected
    forms without affix rules, so requiring one drops them (along with a few
    base words that never inflect).
    """
    uk, us = _load_headword_flags("en_GB.dic"), _load_headword_flags("en_US.dic")
    blocked = get_blocked_words()
    return frozenset(
        word
        for word in uk.keys() | us.keys()
        if len(word) >= 3 and word not in blocked and (uk.get(word, frozenset()) | us.get(word, frozenset()))
    )


@functools.lru_cache(maxsize=None)
def get_common_words() -> frozenset[str]:
    """Common vocabulary from the bundled dictionaries; needs no NLTK data.

    Headwords of three to eight letters that both the UK and the US dictionary
    list and that take a regular inflection (plural, -ed, -ing, -er or -est):
    ordinary nouns, verbs and adjectives, without long rare words,
    abbreviations, or spellings that differ between British and American
    English. It depends only on the bundled files, so it is identical on
    every machine.
    """
    uk, us = _load_headword_flags("en_GB.dic"), _load_headword_flags("en_US.dic")
    blocked = get_blocked_words()
    return frozenset(
        word
        for word in uk.keys() & us.keys()
        if 3 <= len(word) <= 8 and word not in blocked and (uk[word] | us[word]) & _INFLECTION_FLAGS
    )
