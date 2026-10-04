"""Offline, deterministic tests for the Truth and Deception environment.

This game is fully offline: after a short conversation, the Guesser (player 1)
picks ``Fact 1`` or ``Fact 2``, and the env resolves the winner using the
``is_correct`` flags stored in ``game_state`` (no LLM/network involved). We use
``max_turns=2`` so the guessing phase begins immediately and read the correct
fact from state to script both correct and incorrect guesses.
"""

import json

import pytest

import textarena as ta
from textarena.envs.TruthAndDeception.env import TruthAndDeceptionEnv


def _fresh(max_turns=2):
    env = TruthAndDeceptionEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def _correct_token(env):
    return "Fact 1" if env.state.game_state["fact1"]["is_correct"] else "Fact 2"


def _wrong_token(env):
    return "Fact 2" if env.state.game_state["fact1"]["is_correct"] else "Fact 1"


def test_odd_max_turns_rejected():
    with pytest.raises(ValueError):
        TruthAndDeceptionEnv(max_turns=5)


def test_reset_roles_and_single_correct_fact():
    env = _fresh()
    assert env.state.role_mapping[0] == "Deceiver"
    assert env.state.role_mapping[1] == "Guesser"
    gs = env.state.game_state
    assert gs["fact1"]["is_correct"] != gs["fact2"]["is_correct"]  # exactly one correct
    assert env.state.current_player_id == 0


def test_guesser_correct_guess_wins():
    env = _fresh()
    token = _correct_token(env)
    done, _ = env.step("here is my deceptive message")  # deceiver turn
    assert not done and env.state.current_player_id == 1
    done, _ = env.step(token)  # guesser guesses correctly
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_guesser_wrong_guess_loses():
    env = _fresh()
    token = _wrong_token(env)
    env.step("trust me on this one")  # deceiver turn
    done, _ = env.step(token)         # guesser guesses wrongly
    assert done
    # Deceiver (player 0) wins.
    assert env.state.rewards == {0: 1, 1: -1}


def test_guess_without_valid_token_is_invalid():
    env = _fresh()
    env.step("deceiver message")   # deceiver turn
    done, _ = env.step("I think Fact 1 is correct")  # not an exact guess command
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("max_turns", [None, 0, 1, 3, True])
def test_invalid_turn_configurations_are_rejected(max_turns):
    with pytest.raises(ValueError):
        TruthAndDeceptionEnv(max_turns=max_turns)


def test_default_configuration_is_playable():
    env = TruthAndDeceptionEnv()
    env.reset(num_players=2, seed=1)
    for _ in range(env.max_turns - 1):
        done, _ = env.step("conversation")
        assert not done
    done, _ = env.step(_correct_token(env))
    assert done and env.state.rewards == {0: -1, 1: 1}


def test_only_deceiver_receives_correctness_markers():
    env = _fresh()
    deceiver_messages = [
        message
        for _, message, event_type, to_id in env.state.events
        if event_type == ta.ObservationType.PROMPT and to_id == 0
    ]
    guesser_messages = [
        message
        for _, message, event_type, to_id in env.state.events
        if event_type == ta.ObservationType.PROMPT and to_id == 1
    ]
    assert "(correct)" in "\n".join(deceiver_messages)
    assert "(correct)" not in "\n".join(guesser_messages)
    assert "(wrong)" not in "\n".join(guesser_messages)


def test_guess_tokens_are_conversation_until_final_turn():
    env = _fresh(max_turns=4)
    env.step("opening")
    done, _ = env.step(_correct_token(env))
    assert not done
    assert env.state.current_player_id == 0
    env.step("closing argument")
    done, _ = env.step(_correct_token(env))
    assert done


def test_case_insensitive_guess_is_accepted():
    env = _fresh()
    env.step("message")
    token = "fact 1" if env.state.game_state["fact1"]["is_correct"] else "FACT 2"
    done, _ = env.step(token)
    assert done and env.state.rewards[1] == 1


@pytest.mark.parametrize("fact1_token,fact2_token", [("Ｆａｃｔ　１", "Ｆａｃｔ　２"), ("Fa\u200bct 1", "Fa\u200bct 2")])
def test_unicode_compatibility_guess_is_normalized(fact1_token, fact2_token):
    env = _fresh()
    env.step("message")
    token = fact1_token if env.state.game_state["fact1"]["is_correct"] else fact2_token
    done, _ = env.step(token)
    assert done and env.state.rewards[1] == 1


def test_renderer_hides_answer_until_terminal():
    env = _fresh()
    board = env.get_board_str()
    assert "✅" not in board and "❌" not in board
    assert board.count("?") == 2

    env.step("message")
    env.step(_correct_token(env))
    board = env.get_board_str()
    assert "✅" in board and "❌" in board


def test_malformed_facts_file_is_rejected(tmp_path):
    data_path = tmp_path / "facts.json"
    data_path.write_text(
        json.dumps([{"facts": {"fact1": "A", "fact2": "B"}, "correct_fact": "fact3"}]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        TruthAndDeceptionEnv(max_turns=2, data_path=str(data_path))


def test_equivalent_facts_are_rejected(tmp_path):
    data_path = tmp_path / "facts.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "facts": {"fact1": "Café is open.", "fact2": "ＣＡＦÉ   IS OPEN."},
                    "correct_fact": "fact1",
                }
            ]
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="distinct"):
        TruthAndDeceptionEnv(max_turns=2, data_path=str(data_path))
