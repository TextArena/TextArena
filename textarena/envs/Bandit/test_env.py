"""Deterministic game-logic tests for Bandit-v1."""
import copy

import pytest
from textarena.envs.Bandit.env import BanditEnv


def _fresh(num_turns=2):
    env = BanditEnv(buttons=["red", "blue"], num_turns=num_turns)
    env.reset(num_players=1, seed=42)
    return env


def _best_button(env):
    gt = env.state.game_state["ground_truth"]
    return max(gt, key=gt.get)


def test_reset_builds_ground_truth_and_history():
    env = _fresh()
    gs = env.state.game_state
    assert set(gs["ground_truth"].keys()) == {"red", "blue"}
    assert gs["history"] == {"red": [], "blue": []}
    assert env.state.current_player_id == 0


def test_pressing_button_records_history():
    env = _fresh(num_turns=5)
    env.step("red")
    hist = env.state.game_state["history"]
    # exactly one reward (0.0 or 1.0) recorded for the pressed button
    assert len(hist["red"]) == 1
    assert hist["red"][0] in (0.0, 1.0)


def test_invalid_format_increments_error_count():
    env = _fresh()
    done = env.step("I choose nothing")
    assert not done
    assert env.state.error_count == 1


def test_invalid_button_increments_error_count():
    env = _fresh()
    done = env.step("green")  # well formed but not a real button
    assert not done
    assert env.state.error_count == 1


def test_game_ends_after_budget_and_returns_reward():
    env = _fresh(num_turns=2)
    best = _best_button(env)
    env.step(best)  # turn 0
    env.step(best)  # turn 1
    done = env.step(best)  # turn 2 -> final decision
    assert done
    assert env.state.rewards is not None
    assert 0 in env.state.rewards
    assert env.state.turn == 3
    assert env.state.game_info[0]["turn_count"] == 3


def test_correct_final_choice_should_reward_one():
    env = _fresh(num_turns=2)
    best = _best_button(env)
    env.step(best)
    env.step(best)
    env.step(best)
    assert env.state.rewards == {0: 1.0}


def test_incorrect_final_choice_scores_zero():
    env = _fresh(num_turns=0)
    best = _best_button(env)
    wrong = next(button for button in env.buttons if button != best)
    done = env.step(wrong)
    assert done
    assert env.state.rewards == {0: 0.0}
    assert env.game_state["history"] == {"red": [], "blue": []}


def test_second_consecutive_invalid_reply_scores_zero():
    env = _fresh()
    assert not env.step("green")
    assert env.step("green")
    assert env.state.rewards == {0: 0}


@pytest.mark.parametrize(
    "choice,expected",
    [("green", 1.0), ("red", 0.0), ("blue", 0.0)],
)
def test_final_choice_is_scored_against_the_argmax_button(choice, expected):
    env = BanditEnv(buttons=["red", "blue", "green"], num_turns=0)
    env.reset(num_players=1, seed=42)
    env.game_state["ground_truth"] = {"red": 0.2, "blue": 0.3, "green": 0.6}
    done = env.step(choice)
    assert done
    assert env.state.rewards == {0: pytest.approx(expected)}


def test_invalid_final_choice_does_not_consume_a_turn():
    env = _fresh(num_turns=0)
    before = copy.deepcopy(env.game_state)
    done = env.step("not-a-button")
    assert not done
    assert env.state.turn == 0
    assert env.game_state == before
    done = env.step(_best_button(env))
    assert done and env.state.turn == 1


@pytest.mark.parametrize("action", ["RED", "Red"])
def test_button_names_are_case_insensitive(action):
    env = _fresh(num_turns=2)
    done = env.step(action)
    assert not done
    assert env.state.error_count == 0
    assert len(env.game_state["history"]["red"]) == 1


def test_final_choice_is_case_insensitive():
    env = _fresh(num_turns=0)
    done = env.step(_best_button(env).upper())
    assert done
    assert env.state.rewards == {0: 1.0}


def test_case_variants_of_distinct_buttons_must_match_exactly():
    env = BanditEnv(buttons=["red", "Red"], num_turns=2)
    env.reset(num_players=1, seed=42)
    done = env.step("RED")
    assert not done
    assert env.state.error_count == 1
    env.step("Red")
    assert env.state.error_count == 0
    assert len(env.game_state["history"]["Red"]) == 1


def test_unknown_button_feedback_lists_the_buttons():
    env = _fresh()
    env.get_observation()
    env.step("green")
    _, observations = env.get_observation()
    assert any("Choose one of: red, blue." in message for _, message, _ in observations)


def test_prompt_explains_the_final_answer_and_its_scoring():
    env = _fresh(num_turns=3)
    prompt = env.state.events[0][1]
    assert "After your 3 presses, reply with the name of the button you believe has the highest mean reward" in prompt
    assert "a correct answer scores 1" in prompt


@pytest.mark.parametrize("action", ["[red", "red]"])
def test_unmatched_brackets_are_rejected_atomically(action):
    env = _fresh(num_turns=0)
    before = copy.deepcopy(env.game_state)
    done = env.step(action)
    assert not done
    assert env.state.turn == 0
    assert env.game_state == before


def test_non_text_and_oversized_actions_are_rejected_atomically():
    env = _fresh(num_turns=0)
    before = copy.deepcopy(env.game_state)
    done = env.step(None)
    assert not done
    assert env.game_state == before
    env.reset(num_players=1, seed=42)
    done = env.step("x" * (env.max_action_chars + 1))
    assert not done
    assert env.game_state == before


def test_seeded_rng_snapshot_reset_and_statistics_are_pure():
    first = _fresh(num_turns=3)
    second = _fresh(num_turns=3)
    assert first.game_state == second.game_state
    snapshot = first.snapshot()
    before = copy.deepcopy(first.game_state)
    stats = first._observe_statistics()
    assert first.game_state == before
    assert "played 0 times" in stats
    first.step("red")
    sampled = copy.deepcopy(first.game_state)
    first.restore(snapshot)
    first.step("red")
    assert first.game_state == sampled
    first.reset(num_players=1, seed=42)
    assert first.game_state == before


def test_button_configuration_is_copied():
    buttons = ["red", "blue"]
    env = BanditEnv(buttons=buttons, num_turns=1)
    buttons.append("green")
    env.reset(num_players=1, seed=42)
    assert env.buttons == ["red", "blue"]
    assert set(env.game_state["history"]) == {"red", "blue"}


def test_summary_exposes_samples_but_not_hidden_probabilities():
    env = BanditEnv(buttons=["red", "blue"], num_turns=1, include_summary=True)
    env.reset(num_players=1, seed=42)
    env.get_observation()
    env.step("red")
    _, observations = env.get_observation()
    text = "\n".join(message for _, message, _ in observations)
    assert "Summary:" in text
    for probability in env.game_state["ground_truth"].values():
        assert repr(probability) not in text


@pytest.mark.parametrize(
    "kwargs",
    [
        {"buttons": []},
        {"buttons": ["red", "red"]},
        {"buttons": [""]},
        {"buttons": [" red"]},
        {"buttons": ["[red]"]},
        {"buttons": ["x" * 129]},
        {"p_gap": -0.1},
        {"p_gap": 0.81},
        {"p_gap": float("nan")},
        {"num_turns": -1},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        BanditEnv(**kwargs)


def test_player_bounds_are_enforced():
    env = _fresh()
    with pytest.raises(ValueError):
        env.reset(num_players=0)
    with pytest.raises(ValueError):
        env.reset(num_players=2)
