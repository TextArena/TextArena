"""Offline deterministic tests for Hangman (single player).

The target word is random but readable from game_state, so we can script exact
letter/word guesses. reward=1 on a full solve; on running out of tries the
reward is the fraction of correctly revealed characters.
"""
import copy
import string

import pytest

import textarena.envs.Hangman.env as hangman_module
import textarena.utils.word_lists as word_lists
from textarena.envs.Hangman.env import HangmanEnv
from textarena.utils.word_lists import get_basic_english_words, get_headwords


def _fresh():
    env = HangmanEnv()
    env.reset(num_players=1, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["tries_left"] == 6
    assert gs["current_board"] == ["_"] * len(gs["target_word"])
    assert gs["guessed_letters"] == set()
    assert env.state.done is False


def test_full_word_guess_wins():
    env = _fresh()
    word = env.state.game_state["target_word"]
    done, _ = env.step(word)
    assert done
    assert env.state.rewards == {0: 1}


def test_letter_by_letter_solve_wins():
    env = _fresh()
    unique_letters = list(dict.fromkeys(env.state.game_state["target_letters"]))
    done = False
    for letter in unique_letters:
        done, _ = env.step(letter)
    assert done
    assert env.state.game_state["current_board"] == env.state.game_state["target_letters"]
    assert env.state.rewards == {0: 1}


def test_correct_letter_reveals_and_continues():
    env = _fresh()
    first = env.state.game_state["target_letters"][0]
    done, _ = env.step(first)
    assert not done
    assert env.state.game_state["current_board"][0] == first
    assert env.state.game_state["tries_left"] == 6  # no penalty for a correct letter


def test_running_out_of_tries_loses():
    env = _fresh()
    target = set(env.state.game_state["target_letters"])
    wrong = [c for c in string.ascii_uppercase if c not in target][:6]
    done = False
    for letter in wrong:
        assert not done
        done, _ = env.step(letter)
    assert done
    assert env.state.game_state["tries_left"] == 0
    # No letters revealed -> 0% completion -> reward 0.0
    assert env.state.rewards == {0: 0.0}


def test_invalid_format_does_not_end_game():
    env = _fresh()
    done, _ = env.step("no brackets here")
    assert not done
    assert env.state.error_count == 1


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("no brackets here")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice

    assert "for example 'L' or 'LIGHT'" in env.action_format
    for example in ("L", "LIGHT"):
        fresh = _fresh()
        fresh.step(example)
        assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_repeated_letter_is_invalid():
    env = _fresh()
    first = env.state.game_state["target_letters"][0]
    env.step(first)            # valid, reveals
    done, _ = env.step(first)  # same letter again -> invalid
    assert not done
    assert env.state.error_count == 1


def test_wrong_full_word_consumes_a_try():
    env = _fresh()
    target = env.state.game_state["target_word"].upper()
    wrong = next(word for word in ("ALPHA", "BRAVO", "CHARLIE") if word != target)
    done, _ = env.step(wrong)
    assert not done
    assert env.state.game_state["tries_left"] == 5
    assert wrong in env.state.game_state["guessed_words"]


def test_six_wrong_full_words_reach_terminal_state():
    env = _fresh()
    target = env.state.game_state["target_word"].upper()
    wrong_words = [
        word
        for word in ("ALPHA", "BRAVO", "CHARLIE", "DELTA", "ECHO", "FOXTROT", "GOLF")
        if word != target
    ][:6]
    for word in wrong_words:
        done, _ = env.step(word)
    assert done
    assert env.state.game_state["tries_left"] == 0
    assert env.state.turn == 6
    assert env.state.rewards == {0: 0.0}


def test_repeated_wrong_word_is_invalid_and_atomic():
    env = _fresh()
    target = env.state.game_state["target_word"].upper()
    wrong = next(word for word in ("ALPHA", "BRAVO") if word != target)
    env.step(wrong)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(wrong)
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 1


@pytest.mark.parametrize("action", ["A1", "two words", "under_score", "word!"])
def test_malformed_actions_are_atomic(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 0


def test_targets_are_seeded_ascii_words():
    first = _fresh()
    second = _fresh()
    target = first.state.game_state["target_word"]
    assert target == second.state.game_state["target_word"]
    assert target.isascii() and target.isalpha() and target.islower()
    assert len(target) >= 3


def test_non_boolean_dictionary_mode_is_rejected():
    with pytest.raises(ValueError):
        HangmanEnv(hardcore="yes")


def test_renderer_hides_target_until_terminal():
    env = _fresh()
    target = env.state.game_state["target_word"].upper()
    assert target not in env.get_board_str()
    assert "_ " in env.get_board_str() or "Word: _" in env.get_board_str()
    env.step(env.state.game_state["target_word"])
    assert f"Answer: {target}" in env.get_board_str()


def test_snapshot_restores_lives_and_guesses():
    env = _fresh()
    word_list = env.word_list
    target = env.state.game_state["target_word"].upper()
    wrong = next(word for word in ("ALPHA", "BRAVO") if word != target)
    snapshot = env.snapshot()
    env.step(wrong)
    env.restore(snapshot)
    assert env.state.game_state["tries_left"] == 6
    assert env.state.game_state["guessed_words"] == set()
    assert env.state.turn == 0
    assert env.word_list is word_list


def test_long_adversarial_word_costs_only_one_try():
    env = _fresh()
    action = "Z" * 10_000
    if action == env.state.game_state["target_word"].upper():
        pytest.skip("Impossible defensive guard")
    done, _ = env.step(action)
    assert not done
    assert env.state.game_state["tries_left"] == 5


class _MissingCorpus:
    def words(self, *args, **kwargs):
        raise LookupError("corpus unavailable")


@pytest.mark.parametrize("hardcore", [False, True])
def test_secret_words_do_not_depend_on_the_nltk_corpus(monkeypatch, hardcore):
    monkeypatch.setattr(word_lists, "words", _MissingCorpus())
    monkeypatch.setattr(hangman_module, "words", _MissingCorpus(), raising=False)
    env = HangmanEnv(hardcore=hardcore)
    source = get_headwords() if hardcore else get_basic_english_words()
    assert env.word_list == sorted(word for word in source if len(word) >= 3)
    env.reset(num_players=1, seed=2)
    assert env.state.game_state["target_word"] in env.word_list


def test_hardcore_secret_words_exclude_proper_nouns():
    env = HangmanEnv(hardcore=True)
    assert not {"aaron", "aaronic", "paris", "london"} & set(env.word_list)
    assert all(word.isascii() and word.isalpha() and word.islower() for word in env.word_list)


def test_prompt_says_wrong_words_cost_a_try_and_repeats_are_invalid():
    env = _fresh()
    prompt = env.state.events[0][1]
    assert "every wrong word guess costs one try" in prompt
    assert "Repeating a letter or word you already guessed is an invalid move" in prompt
