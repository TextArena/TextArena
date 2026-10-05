"""Offline, deterministic tests for the Spelling Bee environment."""
import copy
import string
from collections import Counter

import pytest
from textarena.envs.SpellingBee.env import SpellingBeeEnv


class _Dictionary:
    def __init__(self):
        self.words = {"a", "cat", "cats", "cater", "dog", "to"}
        self.queries = []

    def __call__(self, word):
        self.queries.append(word)
        return word in self.words


def _fresh(num_letters: int = 26):
    env = SpellingBeeEnv(num_letters=num_letters, is_word=_Dictionary())
    env.reset(num_players=2, seed=42)
    return env


def test_reset_allowed_letters_and_history():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["allowed_letters"]) == 26
    assert gs["allowed_letters"].issubset(set("abcdefghijklmnopqrstuvwxyz"))
    assert gs["word_history"] == []
    assert env.state.current_player_id == 0


@pytest.mark.parametrize("num_letters", [1, 7, 13, 26])
def test_allowed_letters_are_exactly_num_letters_distinct_letters(num_letters):
    env = SpellingBeeEnv(num_letters=num_letters, is_word=_Dictionary())
    for seed in range(50):
        env.reset(num_players=2, seed=seed)
        letters = env.game_state["allowed_letters"]
        assert len(letters) == num_letters
        assert letters <= set(string.ascii_lowercase)


def test_allowed_letters_are_weighted_by_english_letter_frequency():
    env = SpellingBeeEnv(num_letters=1, is_word=_Dictionary())
    counts = Counter()
    for seed in range(400):
        env.reset(num_players=2, seed=seed)
        counts.update(env.game_state["allowed_letters"])
    common = sum(counts[letter] for letter in "etao")
    rare = sum(counts[letter] for letter in "jqxz")
    assert common > 10 * max(rare, 1)


def test_valid_word_accepted_and_turn_rotates():
    env = _fresh()
    done = env.step("cat")
    assert not done
    assert env.state.game_state["word_history"] == ["cat"]
    # A valid, non-invalid move rotates to the other player.
    assert env.state.current_player_id == 1


def test_non_decreasing_length_enforced():
    env = _fresh()
    env.step("cats")  # length 4 by player 0
    # Player 1 submits a shorter word -> invalid (first offence, no termination).
    done = env.step("to")
    assert not done
    assert env.state.error_count == 1
    # History unchanged after the invalid move.
    assert env.state.game_state["word_history"] == ["cats"]


def test_accepted_words_reach_both_players_and_rejected_words_only_their_author():
    env = _fresh()
    env.step("cat")
    env.step("zzzzz")
    assert ("Player 0 submitted the word: cat", -1) in [(message, to_id) for _, message, _, to_id in env.state.events]
    rejected = [
        (message, to_id) for _, message, _, to_id in env.state.events
        if message == "zzzzz" or message.startswith("Player 1 attempted an invalid move.")
    ]
    assert len(rejected) == 2 and all(to_id == 1 for _, to_id in rejected)


def test_non_english_word_rejected():
    env = _fresh()
    done = env.step("zzzzz")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["word_history"] == []


def test_repeated_word_rejected():
    env = _fresh()
    env.step("cat")   # player 0
    env.step("cats")  # player 1 (len 4 >= 3, valid)
    # Player 0 repeats an already used word -> invalid.
    done = env.step("cat")
    assert not done
    assert env.state.error_count == 1


def test_bad_format_rejected():
    env = _fresh()
    done = env.step("two words")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["word_history"] == []


def test_two_consecutive_invalids_end_game():
    env = _fresh()
    env.step("cat")  # player 0 valid -> now player 1
    # Player 1 submits a too-short word twice in a row.
    done = env.step("to")
    assert not done and env.state.error_count == 1
    done = env.step("to")
    assert done
    # Offender (player 1) loses, player 0 wins.
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.game_info[1]["turn_count"] == 0


def test_turn_limit_ends_in_a_draw():
    env = SpellingBeeEnv(num_letters=26, is_word=_Dictionary(), max_turns=3)
    env.reset(num_players=2, seed=42)
    assert not env.step("cat")
    assert not env.step("to")  # rejected words do not count toward the limit
    assert not env.step("dog")
    assert env.step("cats")
    assert env.state.rewards == {0: 0, 1: 0}
    assert env.state.turn == 3


def test_default_turn_limit_is_50_and_must_be_positive():
    assert SpellingBeeEnv(is_word=_Dictionary()).max_turns == 50
    with pytest.raises(ValueError, match="max_turns"):
        SpellingBeeEnv(is_word=_Dictionary(), max_turns=0)


def test_illegal_letters_are_rejected_before_dictionary_lookup():
    dictionary = _Dictionary()
    env = SpellingBeeEnv(num_letters=3, is_word=dictionary)
    env.reset(num_players=2, seed=42)
    env.game_state["allowed_letters"] = {"c", "a", "t"}
    before = copy.deepcopy(env.game_state)
    done = env.step("dog")
    assert not done
    assert env.game_state == before
    assert dictionary.queries == []


@pytest.mark.parametrize("action", ["two words", "cat!", "123", "c_at", "[cat"])
def test_non_word_actions_are_rejected_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    env.step(action)
    assert env.state.turn == 0
    assert env.game_state == before


def test_renderer_is_pure():
    env = _fresh()
    env.step("cat")
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert all(len(line) <= 90 for line in board.splitlines())


def test_renderer_handles_all_supported_letter_counts():
    for count in (1, 4, 7, 10, 26):
        env = _fresh(num_letters=count)
        board = env.get_board_str()
        assert all(len(line) <= 90 for line in board.splitlines())


def test_renderer_truncates_long_word_history_entries():
    env = _fresh()
    env.game_state["word_history"] = ["a" * env.max_word_chars]
    assert all(len(line) <= 90 for line in env.get_board_str().splitlines())


def test_word_check_must_be_callable():
    with pytest.raises(ValueError, match="is_word"):
        SpellingBeeEnv(num_letters=7, is_word={"cat"})


def test_default_word_check_accepts_uk_and_us_spellings_and_inflections():
    env = SpellingBeeEnv(num_letters=26)
    env.reset(num_players=2, seed=42)
    words = ["cat", "color", "colour", "colors", "colours"]
    for word in words:
        done = env.step(word)
        assert not done and env.state.error_count == 0
    env.step("zzzzzzz")
    assert env.state.error_count == 1
    assert env.game_state["word_history"] == words


def test_prompt_states_the_word_rules_and_how_a_player_loses():
    env = _fresh(num_letters=7)
    prompt = env.state.events[0][1]
    assert "use only the allowed letters; each letter may be used any number of times" in prompt
    assert "checked against the game's English dictionary" in prompt
    assert "If you submit two invalid words in a row, you lose." in prompt
    assert "If 50 words have been accepted (counting both players) and nobody has lost, the game is a draw." in prompt


def test_dictionary_lookup_failure_is_retryable_and_atomic():
    def failing_lookup(word):
        raise RuntimeError("dictionary unavailable")

    env = SpellingBeeEnv(num_letters=26, is_word=failing_lookup)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    done = env.step("cat")
    assert not done
    assert env.state.error_count == 0
    assert env.state.turn == 0
    assert env.game_state == before


def test_non_text_and_oversized_words_are_rejected_before_lookup():
    dictionary = _Dictionary()
    env = SpellingBeeEnv(num_letters=26, is_word=dictionary)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    env.step(None)
    assert env.game_state == before
    assert dictionary.queries == []
    env.reset(num_players=2, seed=42)
    env.step("a" * (env.max_word_chars + 1))
    assert env.game_state == before
    assert dictionary.queries == []
    env.reset(num_players=2, seed=42)
    env.step(" " * env.max_action_chars + "cat")
    assert env.game_state == before
    assert dictionary.queries == []


def test_player_bounds_are_enforced():
    env = SpellingBeeEnv(num_letters=7, is_word=_Dictionary())
    with pytest.raises(ValueError):
        env.reset(num_players=1)
    with pytest.raises(ValueError):
        env.reset(num_players=3)
