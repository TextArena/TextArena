import importlib.util
import random
from pathlib import Path

import pytest

from textarena.utils.jury import OpenRouterJury
from textarena.utils.word_lists import (
    get_basic_english_words,
    get_blocked_words,
    get_common_words,
    get_english_words,
    get_headwords,
    is_english_word,
)

ROOT = Path(__file__).resolve().parents[1]


def _load_word_list_builder():
    spec = importlib.util.spec_from_file_location("build_word_lists", ROOT / "scripts" / "build_word_lists.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_word_lists_match_their_sources():
    for name, text in _load_word_list_builder().build().items():
        path = ROOT / "textarena" / "utils" / "data" / name
        assert path.read_text(encoding="utf-8") == text, f"{name} is stale: run python scripts/build_word_lists.py"


def test_affix_rules_honour_conditions_strips_and_cross_products(tmp_path):
    builder = _load_word_list_builder()
    aff = tmp_path / "test.aff"
    aff.write_text(
        "PFX A Y 1\nPFX A 0 re .\n\n"
        "PFX U N 1\nPFX U 0 un .\n\n"
        "SFX S Y 3\nSFX S y ies [^aeiou]y\nSFX S 0 s [aeiou]y\nSFX S 0 s [^sxzhy]\n\n"
        "SFX T N 1\nSFX T 0 est [^ey]\n\n"
        "SFX V N 1\nSFX V e ive .\n",
        encoding="utf-8",
    )
    prefixes, suffixes = builder.read_affixes(aff)

    def expand(word, flags):
        return builder.expand(word, set(flags), prefixes, suffixes)

    assert expand("try", "AS") == {"try", "tries", "retry", "retries"}
    assert expand("play", "US") == {"play", "plays", "unplay"}  # U is not cross-product
    assert expand("tall", "AT") == {"tall", "tallest", "retall"}  # neither is T
    assert expand("abuse", "V") == {"abuse", "abusive"}
    assert expand("act", "V") == {"act"}  # the strip "e" must be present

    aff.write_text("SFX S Y 2\nSFX S 0 s .\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing rules"):
        builder.read_affixes(aff)


def test_english_words_hold_inflections_but_no_invented_forms():
    words = get_english_words()
    assert isinstance(words, frozenset) and 90_000 < len(words) < 120_000
    assert all(word.isascii() and word.isalpha() and word.islower() for word in words)
    assert {"congeniality", "congenialities", "running", "walked", "happier", "churches", "boxes", "boys"} <= words
    assert {"colour", "color", "colours", "colors"} <= words
    assert not {"congenialitys", "concaveed", "confesss", "alwaies"} & words
    assert not {"paris", "london", "dog's"} & words


def test_is_english_word_ignores_letter_case():
    assert is_english_word("Colour") and is_english_word("APPLE")
    assert not is_english_word("Zzzzz")


def test_secret_word_pools_never_contain_blocked_words():
    blocked = get_blocked_words()
    assert len(blocked) > 100 and all(word == word.strip().lower() for word in blocked)
    for pool in (get_headwords(), get_common_words(), get_basic_english_words()):
        assert not pool & blocked


def test_only_a_and_i_count_as_single_letter_words():
    assert is_english_word("a") and is_english_word("I")
    assert not any(is_english_word(letter) for letter in "bcdefghjklmnopqrstuvwxyz")
    assert {word for word in get_english_words() if len(word) == 1} == {"a", "i"}


def test_basic_english_is_bundled_and_accepted():
    basic = get_basic_english_words()
    assert len(basic) == 849  # Ogden's 850 words without the capitalized "I"
    assert {"apple", "water", "the", "about"} <= basic
    assert basic <= get_english_words()


def test_common_words_are_ordinary_base_words_of_the_bundled_dictionaries():
    common, headwords = get_common_words(), get_headwords()
    full = get_english_words()
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


class _Juror:
    def __init__(self, response):
        self.response = response

    def __call__(self, prompt):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_jury_rejects_invalid_or_failed_votes():
    jury = OpenRouterJury.__new__(OpenRouterJury)
    jury.options = ["Affirmative", "Negative"]
    jury.jury = [_Juror("Affirmative because..."), _Juror(RuntimeError("offline"))]

    with pytest.raises(RuntimeError, match="2 of 2 jurors"):
        jury.evaluate("context")


def test_jury_accepts_quoted_or_punctuated_votes():
    jury = OpenRouterJury.__new__(OpenRouterJury)
    jury.options = ["Affirmative", "Negative"]
    jury.jury = [_Juror("'Affirmative'"), _Juror(" negative. "), _Juror("**Affirmative**"), _Juror("“Negative”")]

    assert jury.evaluate("context") == {"Affirmative": 0.5, "Negative": 0.5}


@pytest.mark.parametrize("reply", ["`Negative`", "[Negative]", "Vote: Negative", "**Answer**: negative", "Negative,"])
def test_jury_accepts_labelled_or_formatted_votes(reply):
    jury = OpenRouterJury.__new__(OpenRouterJury)
    jury.options = ["Affirmative", "Negative"]
    jury.jury = [_Juror(reply)]

    assert jury.evaluate("context") == {"Affirmative": 0.0, "Negative": 1.0}


def test_jury_asks_again_only_after_an_unusable_reply():
    class Juror:
        def __init__(self, replies):
            self.replies, self.calls = list(replies), 0

        def __call__(self, prompt):
            self.calls += 1
            return self.replies.pop(0)

    jury = OpenRouterJury.__new__(OpenRouterJury)
    jury.options = ["Affirmative", "Negative"]
    steady, wavering = Juror(["Affirmative"]), Juror(["I lean Negative", "Negative"])
    jury.jury = [steady, wavering]

    assert jury.evaluate("context") == {"Affirmative": 0.5, "Negative": 0.5}
    assert (steady.calls, wavering.calls) == (1, 2)
