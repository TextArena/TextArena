import random
import importlib

import pytest

from textarena.utils.jury import OpenRouterJury
from textarena.utils.word_lists import EnglishDictionary, get_basic_english_words, get_common_words, get_headwords

word_lists_module = importlib.import_module("textarena.utils.word_lists")


# Stubs replace the module's `words` reference itself: patching an attribute of
# NLTK's lazy corpus loader would load the corpus, which fails when it is missing.
class _FailingCorpus:
    def words(self, *args, **kwargs):
        pytest.fail("unexpected corpus access")


class _MissingCorpus:
    def words(self, *args, **kwargs):
        raise LookupError("corpus unavailable")


def test_secret_word_pools_never_contain_blocked_words():
    blocked = word_lists_module.get_blocked_words()
    assert len(blocked) > 100 and all(word == word.strip().lower() for word in blocked)
    for pool in (get_headwords(), get_common_words(), get_basic_english_words()):
        assert not pool & blocked


@pytest.mark.parametrize("include_nltk", [False, True])
def test_only_a_and_i_count_as_single_letter_words(include_nltk):
    dictionary = EnglishDictionary(include_nltk=include_nltk)
    assert dictionary.is_english_word("a") and dictionary.is_english_word("I")
    assert not any(dictionary.is_english_word(letter) for letter in "bcdefghjklmnopqrstuvwxyz")
    assert {word for word in dictionary.get_all_words() if len(word) == 1} == {"a", "i"}


def test_dictionary_does_not_download_nltk_when_disabled(monkeypatch):
    monkeypatch.setattr(word_lists_module, "words", _FailingCorpus())
    dictionary = EnglishDictionary(include_nltk=False)
    assert dictionary.nltk_words == set()
    assert dictionary.get_basic_words() == get_basic_english_words()


def test_dictionary_falls_back_to_bundled_words_offline(monkeypatch):
    monkeypatch.setattr(word_lists_module, "words", _MissingCorpus())
    dictionary = EnglishDictionary(include_nltk=True)
    assert dictionary.nltk_words == set()
    assert dictionary.us_words
    assert dictionary.uk_words


def test_basic_words_are_identical_without_nltk(monkeypatch):
    expected = EnglishDictionary().get_basic_words()
    expected_module = get_basic_english_words()
    monkeypatch.setattr(word_lists_module, "words", _MissingCorpus())
    word_lists_module._load_basic_english.cache_clear()
    assert EnglishDictionary().get_basic_words() == expected
    assert get_basic_english_words() == expected_module
    assert len(expected) == 849  # Ogden's 850 words; the default filter drops the capitalized "I"
    assert expected_module == expected
    assert {"apple", "water", "the", "about"} <= expected


def test_bundled_basic_english_matches_the_nltk_corpus():
    from nltk.corpus import words

    try:
        nltk_basic = words.words("en-basic")
    except LookupError:
        pytest.skip("NLTK words corpus not installed")
    assert list(word_lists_module._load_basic_english()) == sorted(nltk_basic, key=lambda w: (w.lower(), w))


def test_bundled_word_tiers_are_built_without_nltk(monkeypatch):
    expected = (get_common_words(), get_headwords())
    monkeypatch.setattr(word_lists_module, "words", _FailingCorpus())
    for cached in (get_common_words, get_headwords, word_lists_module._load_headword_flags):
        cached.cache_clear()
    assert (get_common_words(), get_headwords()) == expected


def test_common_words_are_ordinary_base_words_of_the_bundled_dictionaries():
    common, headwords = get_common_words(), get_headwords()
    full = EnglishDictionary(include_nltk=False).get_all_words()
    assert isinstance(common, frozenset) and isinstance(headwords, frozenset)
    assert common < headwords <= full
    assert 10_000 < len(common) < 20_000 and 30_000 < len(headwords) < 50_000
    assert all(word.isascii() and word.isalpha() and word.islower() for word in headwords)
    assert all(len(word) >= 3 for word in headwords)
    assert all(3 <= len(word) <= 8 for word in common)
    assert {"hear", "bear", "pan", "apple", "water"} <= common
    # Spellings that differ between the UK and US lists are headwords but not common words.
    assert {"colour", "color"} <= headwords and not {"colour", "color"} & common
    # Abbreviations, roman numerals and affix-generated forms are in neither tier.
    assert not {"kg", "acct", "xcix", "bears"} & headwords
    assert "bears" in full


def test_jury_uses_injected_rng_without_mutating_global_random_state():
    created_models = []

    class Juror:
        def __call__(self, prompt):
            return "Yes"

    def factory(*, model_name, system_prompt):
        created_models.append(model_name)
        return Juror()

    random.seed(99)
    expected = random.Random(99).random()
    jury = OpenRouterJury(
        options=["Yes", "No"],
        jury_size=3,
        model_names=["a", "b"],
        seed=42,
        agent_factory=factory,
    )

    assert jury.evaluate("context") == {"Yes": 1.0, "No": 0.0}
    assert created_models == ["a", "a", "b"]
    assert random.random() == expected


def test_jury_rejects_invalid_or_failed_votes():
    class Juror:
        def __init__(self, response):
            self.response = response

        def __call__(self, prompt):
            if isinstance(self.response, Exception):
                raise self.response
            return self.response

    jury = OpenRouterJury.__new__(OpenRouterJury)
    jury.options = ["Affirmative", "Negative"]
    jury.jury = [Juror("Affirmative because..."), Juror(RuntimeError("offline"))]

    with pytest.raises(RuntimeError, match="2 of 2 jurors"):
        jury.evaluate("context")
