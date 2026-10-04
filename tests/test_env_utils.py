import random
import importlib

import pytest

from textarena.envs.utils.jury import OpenRouterJury
from textarena.envs.utils.word_lists import EnglishDictionary

word_lists_module = importlib.import_module("textarena.envs.utils.word_lists")


def test_dictionary_does_not_download_nltk_when_disabled(monkeypatch):
    monkeypatch.setattr(
        word_lists_module.words,
        "words",
        lambda *args, **kwargs: pytest.fail("unexpected corpus access"),
    )
    dictionary = EnglishDictionary(include_nltk=False)
    assert dictionary.nltk_words == set()
    assert dictionary.nltk_basic_words == set()


def test_dictionary_falls_back_to_bundled_words_offline(monkeypatch):
    def unavailable(*args, **kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr(word_lists_module.words, "words", unavailable)
    dictionary = EnglishDictionary(include_nltk=True)
    assert dictionary.nltk_words == set()
    assert dictionary.nltk_basic_words == set()
    assert dictionary.us_words
    assert dictionary.uk_words


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
