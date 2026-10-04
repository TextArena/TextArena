"""Deterministic game-logic tests for DontSayIt (2 players).

The secret words are random per seed, so we read them from
``env.state.game_state`` to script guaranteed outcomes.
"""
import pytest

import textarena as ta
from textarena.envs.DontSayIt.env import DontSayItEnv


def _fresh(max_turns=6):
    env = DontSayItEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def test_saying_opponents_word_makes_opponent_win():
    env = _fresh()
    opponent_word = env.state.game_state["target_words"][1]
    # Player 0 blurts out player 1's secret word -> player 1 wins.
    done, _ = env.step(f"I believe the answer is {opponent_word}.")
    assert done and env.state.rewards == {1: 1, 0: -1}


def test_turn_limit_ends_in_draw():
    env = _fresh(max_turns=2)
    env.step("zzz")
    done, _ = env.step("zzz")
    assert done and env.state.rewards == {0: 0, 1: 0}


def test_trigger_on_final_turn_takes_precedence_over_draw():
    env = _fresh(max_turns=2)
    env.state.game_state["target_words"] = {0: "apple", 1: "banana"}
    env.step("safe")
    done, _ = env.step("apple")
    assert done and env.state.rewards == {0: 1, 1: -1}


def test_safe_message_does_not_end_game():
    env = _fresh()
    done, _ = env.step("zzz")
    assert not done and env.state.current_player_id == 1


@pytest.mark.parametrize("max_turns", [0, 1, 3, -1, 1.5, True])
def test_invalid_turn_limits_are_rejected(max_turns):
    with pytest.raises(ValueError):
        DontSayItEnv(max_turns=max_turns)


def test_non_boolean_dictionary_mode_is_rejected():
    with pytest.raises(ValueError):
        DontSayItEnv(max_turns=2, hardcore="yes")


def test_targets_are_distinct_and_seeded():
    env = _fresh()
    targets = dict(env.state.game_state["target_words"])
    assert targets[0] != targets[1]
    env.reset(num_players=2, seed=42)
    assert env.state.game_state["target_words"] == targets


def test_each_secret_is_routed_only_to_its_owner():
    env = _fresh()
    targets = env.state.game_state["target_words"]
    prompts = {
        pid: "\n".join(
            message
            for _, message, event_type, to_id in env.state.events
            if event_type == ta.ObservationType.PROMPT and to_id == pid
        )
        for pid in (0, 1)
    }
    assert targets[0] in prompts[0] and targets[1] not in prompts[0]
    assert targets[1] in prompts[1] and targets[0] not in prompts[1]


def test_secret_matching_uses_whole_words_not_substrings():
    env = _fresh()
    env.state.game_state["target_words"] = {0: "art", 1: "cat"}
    done, _ = env.step("Concatenate these strings.")
    assert not done
    done, _ = env.step("harmless")
    assert not done
    done, _ = env.step("écat is still one Unicode word.")
    assert not done

    done, _ = env.step("That piece of ART!")
    assert done and env.state.rewards == {0: 1, 1: -1}


@pytest.mark.parametrize("mention", ["ＣＡＴ", "c\u200bat"])
def test_secret_matching_normalizes_unicode_compatibility_forms(mention):
    env = _fresh()
    env.state.game_state["target_words"] = {0: "apple", 1: "cat"}
    done, _ = env.step(f"Please say {mention}.")
    assert done and env.state.rewards == {0: -1, 1: 1}


def test_saying_own_secret_is_safe():
    env = _fresh()
    env.state.game_state["target_words"] = {0: "apple", 1: "banana"}
    done, _ = env.step("apple")
    assert not done


def test_unlimited_prompt_and_snapshot_restore():
    env = _fresh(max_turns=None)
    assert "no turn limit" in env.prompt(0)
    snapshot = env.snapshot()
    env.step("zzz")
    assert env.state.current_player_id == 1
    env.restore(snapshot)
    assert env.state.current_player_id == 0
    assert env.state.turn == 0


def test_missing_nltk_corpus_uses_offline_dictionary(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr("textarena.envs.DontSayIt.env.words.words", unavailable)
    env = DontSayItEnv(max_turns=2)
    env.reset(num_players=2, seed=2)
    targets = env.state.game_state["target_words"]
    assert targets[0] != targets[1]
    assert all(word.isascii() and word.isalpha() for word in targets.values())
