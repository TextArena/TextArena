"""SpellingBee must offer exactly ``num_letters`` unique letters, drawn by English letter frequency."""
import random
from collections import Counter

import pytest

from textarena.envs.SpellingBee.env import SpellingBeeEnv


def _bare_env(num_letters: int) -> SpellingBeeEnv:
    # Skip __init__ so the test does not have to build the English dictionary.
    env = SpellingBeeEnv.__new__(SpellingBeeEnv)
    env.num_letters = num_letters
    return env


@pytest.mark.parametrize("num_letters", [1, 4, 7, 10, 26])
def test_exactly_num_letters_unique_letters(num_letters):
    env = _bare_env(num_letters)
    random.seed(0)
    for _ in range(500):
        letters = env._generate_allowed_letters()
        assert len(letters) == num_letters
        assert letters <= set("abcdefghijklmnopqrstuvwxyz")


def test_letters_follow_english_frequency():
    env = _bare_env(7)
    random.seed(0)
    counts = Counter()
    for _ in range(2000):
        counts.update(env._generate_allowed_letters())
    # 'e' (12.70) should be offered far more often than 'z' (0.07) or 'q' (0.10).
    assert counts["e"] > 10 * max(counts["z"], counts["q"], 1)


def test_same_seed_same_letters():
    env = _bare_env(7)
    random.seed(123)
    first = env._generate_allowed_letters()
    random.seed(123)
    assert env._generate_allowed_letters() == first


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
