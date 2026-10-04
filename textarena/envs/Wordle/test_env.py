"""Offline deterministic tests for the Wordle environment.

Wordle is a single-player word puzzle. The secret word is chosen randomly, but
we read it directly from ``env.state.game_state['secret_word']`` so we can script
a guaranteed win. Guess format: a bare word, e.g. 'apple'.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.Wordle.env import WordleEnv
from textarena.utils.word_lists import get_basic_english_words, get_english_words, get_headwords


def _fresh(word_length=5, num_guesses=6):
    env = WordleEnv(word_length=word_length, num_guesses=num_guesses)
    env.reset(num_players=1, seed=42)
    return env


def _valid_nonsecret(env):
    secret = env.state.game_state["secret_word"]
    return next(
        (word for word in sorted(get_english_words()) if len(word) == env.word_length and word != secret),
        None,
    )


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert env.state.game_state["guess_history"] == []
    assert len(env.state.game_state["secret_word"]) == 5


def test_guessing_secret_word_wins():
    env = _fresh()
    secret = env.state.game_state["secret_word"]
    done = env.step(secret)
    assert done
    assert env.state.rewards == {0: 1}


def test_correct_guess_on_last_allowed_turn_wins():
    env = _fresh(num_guesses=1)
    done = env.step(env.state.game_state["secret_word"])
    assert done
    assert env.state.turn == 1
    assert env.state.rewards == {0: 1}


def test_invalid_format_rejected():
    env = _fresh()
    done = env.step("not one word")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("word_length", [5, 7, 4])
def test_format_error_describes_expected_action(word_length):
    env = _fresh(word_length=word_length)
    env.step("not one word")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]
    assert env.action_format.startswith(f"a {word_length}-letter English word, for example '")

    fresh = _fresh(word_length=word_length)
    fresh.step(env.action_format.split("'")[1])
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_wrong_length_rejected():
    env = _fresh()
    # Four-letter word cannot match a five-letter secret.
    done = env.step("abcd")
    assert not done
    assert env.state.error_count == 1


def test_non_english_word_rejected():
    env = _fresh()
    done = env.step("zzzzz")
    assert not done
    assert env.state.error_count == 1


def test_repeated_invalid_moves_end_game():
    env = _fresh()
    env.step("not one word")         # first invalid
    done = env.step("still none")  # second consecutive invalid -> ends
    assert done
    assert 0 <= env.state.rewards[0] <= 1


def test_feedback_recorded_for_valid_non_winning_guess():
    env = _fresh()
    guess = _valid_nonsecret(env)
    assert guess is not None
    done = env.step(guess)
    assert not done
    assert len(env.state.game_state["guess_history"]) == 1
    word, feedback = env.state.game_state["guess_history"][0]
    assert word == guess
    assert len(feedback) == 5
    assert all(f in ("G", "Y", "X") for f in feedback)


def test_guess_is_logged_and_broadcast_as_coming_from_the_player():
    env = _fresh()
    guess = _valid_nonsecret(env)
    assert guess is not None
    env.get_observation()
    start = len(env.state.events)
    env.step(guess)
    echoes = [event for event in env.state.events[start:] if event[2] == ta.ObservationType.PLAYER_ACTION]
    assert echoes == [(0, guess, ta.ObservationType.PLAYER_ACTION, -1)]
    assert (0, guess) in env.state.logs
    _, observations = env.get_observation()
    assert (0, guess, ta.ObservationType.PLAYER_ACTION) in observations


@pytest.mark.parametrize(
    "kwargs",
    [
        {"word_length": 100, "num_guesses": 6},
    ],
)
def test_invalid_or_unavailable_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        WordleEnv(**kwargs)


def test_seeded_setup_is_deterministic_and_normalized():
    first = _fresh()
    second = _fresh()
    assert first.state.game_state["secret_word"] == second.state.game_state["secret_word"]
    assert first.state.game_state["secret_word"].isascii()
    assert first.state.game_state["secret_word"].isalpha()
    assert first.state.game_state["secret_word"].islower()


@pytest.mark.parametrize("action", ["abc123", "abc_def", "two words", "apple!"])
def test_malformed_actions_do_not_consume_a_guess(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done = env.step(action)
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 0


def test_repeated_valid_guess_is_atomic():
    env = _fresh()
    guess = _valid_nonsecret(env)
    assert guess is not None
    env.step(guess)
    before = copy.deepcopy(env.state.game_state)
    done = env.step(guess)
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 1


def test_duplicate_letter_feedback_does_not_overcount():
    env = _fresh()
    env.state.game_state["secret_word"] = "apple"
    assert env._evaluate_guess("allee") == ["G", "Y", "X", "X", "G"]


def test_turn_limit_reward_uses_best_guess_not_latest_guess():
    env = _fresh(num_guesses=2)
    env.state.game_state["secret_word"] = "apple"
    env._check_word = lambda word: True
    env.step("ample")
    done = env.step("zzzzz")
    assert done
    assert env.state.turn == 2
    assert env.state.rewards == {0: 0.8}
    assert "best guess scored 80% (a green letter counts 1, a yellow letter 0.5)" in env.state.game_info[0]["reason"]


def test_renderer_hides_secret_until_terminal():
    env = _fresh()
    secret = env.state.game_state["secret_word"].upper()
    assert secret not in env.get_board_str()
    assert "?" * env.word_length in env.get_board_str()
    env.step(env.state.game_state["secret_word"])
    assert secret in env.get_board_str()


def test_snapshot_restores_guesses_and_word_list():
    env = _fresh()
    word_list = env.word_list
    guess = _valid_nonsecret(env)
    assert guess is not None
    snapshot = env.snapshot()
    env.step(guess)
    env.restore(snapshot)
    assert env.state.game_state["guess_history"] == []
    assert env.state.turn == 0
    assert env.word_list is word_list


def test_uk_and_us_spellings_and_inflections_are_accepted_but_proper_nouns_are_not():
    env = WordleEnv()
    assert all(env._check_word(word) for word in ("apple", "colour", "color", "boxes"))
    assert not any(env._check_word(word) for word in ("paris", "zzzzz"))


@pytest.mark.parametrize("hardcore", [False, True])
@pytest.mark.parametrize("word_length", [5, 7])
def test_secret_words_are_basic_english_or_headwords_and_always_accepted(word_length, hardcore):
    env = WordleEnv(word_length=word_length, hardcore=hardcore)
    source = get_headwords() if hardcore else get_basic_english_words()
    assert env.word_list == sorted(word for word in source if len(word) == word_length)
    assert all(env._check_word(word) for word in env.word_list)


def test_lengths_missing_from_the_secret_list_fall_back_to_the_dictionary():
    env = WordleEnv(word_length=2, num_guesses=3, hardcore=True)
    assert env.word_list
    assert all(len(word) == 2 and env._check_word(word) for word in env.word_list)


def test_prompt_states_the_word_rules_with_an_example_of_the_right_length():
    env = WordleEnv(word_length=7, num_guesses=9)
    env.reset(num_players=1, seed=0)
    prompt = env.state.events[0][1]
    assert "e.g. 'example'" in prompt and "'apple'" not in prompt
    assert "Every guess must be a 7-letter English word from the game's dictionary" in prompt
    assert "you cannot repeat a guess" in prompt
