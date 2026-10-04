"""Offline deterministic tests for the Wordle environment.

Wordle is a single-player word puzzle. The secret word is chosen randomly, but
we read it directly from ``env.state.game_state['secret_word']`` so we can script
a guaranteed win. Guess format: a bare word, e.g. 'apple'.
"""
import copy

import pytest

from textarena.envs.Wordle.env import WordleEnv


def _fresh(word_length=5, num_guesses=6):
    env = WordleEnv(word_length=word_length, num_guesses=num_guesses)
    env.reset(num_players=1, seed=42)
    return env


def _valid_nonsecret(env):
    secret = env.state.game_state["secret_word"]
    return next(
        (
            word
            for word in sorted(env.dictionary.get_all_words())
            if word.isascii()
            and word.isalpha()
            and len(word) == env.word_length
            and word != secret
        ),
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
    done, _ = env.step(secret)
    assert done
    assert env.state.rewards == {0: 1}


def test_correct_guess_on_last_allowed_turn_wins():
    env = _fresh(num_guesses=1)
    done, _ = env.step(env.state.game_state["secret_word"])
    assert done
    assert env.state.turn == 1
    assert env.state.rewards == {0: 1}


def test_invalid_format_rejected():
    env = _fresh()
    done, _ = env.step("no brackets here")
    assert not done
    assert env.state.error_count == 1


def test_wrong_length_rejected():
    env = _fresh()
    # Four-letter word cannot match a five-letter secret.
    done, _ = env.step("abcd")
    assert not done
    assert env.state.error_count == 1


def test_non_english_word_rejected():
    env = _fresh()
    done, _ = env.step("zzzzz")
    assert not done
    assert env.state.error_count == 1


def test_repeated_invalid_moves_end_game():
    env = _fresh()
    env.step("no brackets")          # first invalid
    done, _ = env.step("still none")  # second consecutive invalid -> ends
    assert done
    assert 0 <= env.state.rewards[0] <= 1


def test_feedback_recorded_for_valid_non_winning_guess():
    env = _fresh()
    guess = _valid_nonsecret(env)
    assert guess is not None
    done, _ = env.step(guess)
    assert not done
    assert len(env.state.game_state["guess_history"]) == 1
    word, feedback = env.state.game_state["guess_history"][0]
    assert word == guess
    assert len(feedback) == 5
    assert all(f in ("G", "Y", "X") for f in feedback)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"word_length": 0, "num_guesses": 6},
        {"word_length": 5, "num_guesses": 0},
        {"word_length": True, "num_guesses": 6},
        {"word_length": 100, "num_guesses": 6},
        {"word_length": 5, "num_guesses": 6, "hardcore": "yes"},
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
    done, _ = env.step(action)
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 0


def test_repeated_valid_guess_is_atomic():
    env = _fresh()
    guess = _valid_nonsecret(env)
    assert guess is not None
    env.step(guess)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(guess)
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
    done, _ = env.step("zzzzz")
    assert done
    assert env.state.turn == 2
    assert env.state.rewards == {0: 0.8}


def test_renderer_hides_secret_until_terminal():
    env = _fresh()
    secret = env.state.game_state["secret_word"].upper()
    assert secret not in env.get_board_str()
    assert "?" * env.word_length in env.get_board_str()
    env.step(env.state.game_state["secret_word"])
    assert secret in env.get_board_str()


def test_snapshot_restores_guesses_and_dictionary_resource():
    env = _fresh()
    dictionary = env.dictionary
    word_list = env.word_list
    guess = _valid_nonsecret(env)
    assert guess is not None
    snapshot = env.snapshot()
    env.step(guess)
    env.restore(snapshot)
    assert env.state.game_state["guess_history"] == []
    assert env.state.turn == 0
    assert env.dictionary is dictionary
    assert env.word_list is word_list


def test_missing_nltk_corpus_uses_offline_dictionary(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr("textarena.envs.Wordle.env.words.words", unavailable)
    env = WordleEnv(word_length=5, num_guesses=2)
    env.reset(num_players=1, seed=1)
    secret = env.state.game_state["secret_word"]
    assert len(secret) == 5
    assert env._check_word(secret)


def test_missing_pos_tagger_does_not_disable_wordle(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise LookupError("tagger unavailable")

    monkeypatch.setattr("textarena.envs.Wordle.env.pos_tag", unavailable)
    env = WordleEnv(word_length=5, num_guesses=2)
    env.reset(num_players=1, seed=1)
    assert env.state.game_state["secret_word"] in env.word_list


def test_partial_nltk_corpus_never_selects_an_unaccepted_target(monkeypatch):
    def partial_corpus(name):
        if name == "en":
            raise LookupError("full corpus unavailable")
        return ["zzzzz"]

    monkeypatch.setattr("textarena.envs.Wordle.env.words.words", partial_corpus)
    monkeypatch.setattr(
        "textarena.envs.Wordle.env.pos_tag",
        lambda tokens: [(tokens[0], "NN")],
    )
    env = WordleEnv(word_length=5, num_guesses=2)
    env.reset(num_players=1, seed=1)
    assert env._check_word(env.state.game_state["secret_word"])
    assert "zzzzz" not in env.word_list
