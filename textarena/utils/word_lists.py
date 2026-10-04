"""English word lists shared by the word games.

Every list is a plain-text file in ``textarena/utils/data/``, so games accept and draw the same words on every
machine. ``english_words.txt``, ``headwords.txt`` and ``common_words.txt`` are built from the UK and US Hunspell
dictionaries by ``scripts/build_word_lists.py``.
"""
import functools
import importlib.resources


@functools.lru_cache(maxsize=None)
def _load(filename: str) -> frozenset[str]:
    text = importlib.resources.files("textarena.utils.data").joinpath(filename).read_text(encoding="utf-8")
    return frozenset(line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#"))


def get_english_words() -> frozenset[str]:
    """Every word of the UK and US dictionaries with its inflections, in lowercase; no proper nouns."""
    return _load("english_words.txt")


def is_english_word(word: str) -> bool:
    """Whether the word, in any letter case, is in `get_english_words()`."""
    return word.lower() in get_english_words()


def get_headwords() -> frozenset[str]:
    """Base words of three or more letters, without inflected forms, abbreviations or blocked words."""
    return _load("headwords.txt")


def get_common_words() -> frozenset[str]:
    """Headwords of three to eight letters that the UK and US dictionaries share and that take a regular
    inflection (plural, -ed, -ing, -er or -est)."""
    return _load("common_words.txt")


@functools.lru_cache(maxsize=None)
def get_basic_english_words() -> frozenset[str]:
    """The 849 lowercase words of Ogden's Basic English (all of it except the pronoun "I")."""
    return frozenset(word for word in _load("en_basic.txt") if word.isalpha() and word.islower())


def get_blocked_words() -> frozenset[str]:
    """Slurs, sexual and vulgar terms that games never draw as secret or board words."""
    return _load("blocked_words.txt")
