"""Hangman must accept letters from its supported word languages."""

import pytest

from textarena.envs.Hangman.env import HangmanEnv


@pytest.mark.parametrize("word", ["silver", "café", "straße", "ΐ", "κόσμος", "привет", "مرحبا"])
@pytest.mark.parametrize("whole_word", [False, True])
def test_correct_guesses(word, whole_word):
    env = HangmanEnv()
    env.word_list = [word]
    env.reset(num_players=1, seed=42)

    guesses = [word] if whole_word else dict.fromkeys(word)
    for guess in guesses:
        done, _ = env.step(f"[{guess}]")

    assert done
    rewards, info = env.close()
    assert rewards == {0: 1}
    assert not info[0]["invalid_move"]
    assert env.state.game_state["tries_left"] == 6
    assert len(env.state.game_state["current_board"]) == len(word)


def test_repeated_unicode_letter():
    env = HangmanEnv()
    env.word_list = ["café"]
    env.reset(num_players=1, seed=42)

    env.step("[é]")
    assert env.state.game_state["current_board"] == ["_", "_", "_", "É"]
    assert env.state.error_count == 0
    env.step("[É]")
    assert env.state.error_count == 1
    assert env.state.game_state["tries_left"] == 6


@pytest.mark.parametrize("action", ["[123]", "[_]", "[two words]", "[!]", "é"])
def test_invalid_guess_format(action):
    env = HangmanEnv()
    env.word_list = ["café"]
    env.reset(num_players=1, seed=42)

    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["guessed_letters"] == set()
