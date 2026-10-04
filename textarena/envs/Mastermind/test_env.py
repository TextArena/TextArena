"""Deterministic offline tests for the Mastermind environment."""
import copy
import re

import pytest

from textarena.envs.Mastermind.env import MastermindEnv


def _fresh(**kwargs):
    env = MastermindEnv(**kwargs)
    env.reset(num_players=1, seed=42)
    return env


def _secret(env):
    return env.state.game_state["secret_code"]


def test_win_by_cracking_code():
    env = _fresh()
    code = _secret(env)
    done, _ = env.step(" ".join(map(str, code)))
    assert done
    assert env.state.rewards == {0: 1}


def test_valid_nonwinning_guess_gives_feedback():
    env = _fresh()
    # A well-formed, in-range, duplicate-free guess distinct from the secret.
    guess = [1, 2, 3, 4]
    assert guess != _secret(env)
    done, _ = env.step(" ".join(map(str, guess)))
    assert not done
    hist = env.state.game_state["history"]
    assert len(hist) == 1
    entry = hist[0]
    assert entry["guess"] == guess
    assert 0 <= entry["black"] <= 4
    assert 0 <= entry["white"] <= 4


def test_invalid_format_increments_error_not_done():
    env = _fresh()
    done, _ = env.step("not a guess at all")
    assert not done
    assert env.state.error_count == 1


def test_wrong_length_rejected():
    env = _fresh()
    done, _ = env.step("1 2 3")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["history"] == []


def test_out_of_range_rejected():
    env = _fresh()  # num_numbers defaults to 6
    done, _ = env.step("6 7 8 9")
    assert not done
    assert env.state.error_count == 1


def test_duplicate_numbers_rejected_when_disallowed():
    env = _fresh()  # duplicate_numbers defaults to False
    done, _ = env.step("1 1 2 3")
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalids_end_game():
    env = _fresh()
    done, _ = env.step("garbage")
    assert not done
    done, _ = env.step("still garbage")
    assert done
    # No successful guesses -> percentage completion is 0.0
    assert env.state.rewards == {0: 0.0}


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("duplicates", [False, True])
def test_secret_generation_is_valid_and_deterministic(seed, duplicates):
    kwargs = {
        "code_length": 5,
        "num_numbers": 7,
        "duplicate_numbers": duplicates,
    }
    first = _fresh(**kwargs)
    second = MastermindEnv(**kwargs)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert _secret(first) == _secret(second)
    assert len(_secret(first)) == 5
    assert all(1 <= value <= 7 for value in _secret(first))
    if not duplicates:
        assert len(set(_secret(first))) == 5


@pytest.mark.parametrize(
    "action",
    [
        "1 2 3 4 extra",
        "[1 2 3 4",
        "1 2 3 4]",
        "1,,2,3,4",
        "1, ,2,3,4",
        "-1 2 3 4",
        "",
    ],
)
def test_exact_parser_rejects_malformed_guesses_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before
    assert env.state.turn == 0


def test_comma_separated_guess_format():
    env = _fresh()
    done, _ = env.step("1, 2, 3, 4")
    assert not done
    assert env.game_state["history"][0]["guess"] == [1, 2, 3, 4]


def test_oversized_numeric_guess_is_invalid_without_history():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(f"{'9' * env.max_action_chars} 2 3 4")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before


def test_large_number_range_generation_does_not_materialize_population():
    env = _fresh(code_length=4, num_numbers=1_000_000)
    assert len(_secret(env)) == 4
    assert all(1 <= number <= 1_000_000 for number in _secret(env))


def test_duplicate_feedback_does_not_overcount_white_pegs():
    env = _fresh(
        code_length=4,
        num_numbers=4,
        duplicate_numbers=True,
    )
    env.game_state["secret_code"] = [1, 1, 2, 2]
    assert env._evaluate_guess([1, 2, 1, 1]) == (1, 2)


def test_repeated_guess_is_invalid_and_history_is_atomic():
    env = _fresh()
    env.step("1 2 3 4")
    before = copy.deepcopy(env.game_state["history"])
    done, _ = env.step("1 2 3 4")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["history"] == before


def test_turn_limit_returns_latest_weighted_feedback():
    env = _fresh(max_turns=1)
    guess = [1, 2, 3, 4]
    assert guess != _secret(env)
    black, white = env._evaluate_guess(guess)
    done, _ = env.step("1 2 3 4")
    assert done
    assert env.state.rewards == {0: pytest.approx((black + white * 0.5) / 4)}
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code_length": 4, "num_numbers": 6, "max_turns": 20, "duplicate_numbers": False},
        {"code_length": 4, "num_numbers": 8, "max_turns": 30, "duplicate_numbers": False},
        {"code_length": 6, "num_numbers": 12, "max_turns": 50, "duplicate_numbers": True},
        {"code_length": 5, "num_numbers": 3, "max_turns": 10, "duplicate_numbers": True},
    ],
)
def test_prompt_example_is_a_legal_guess_for_every_configuration(kwargs):
    env = _fresh(**kwargs)
    _, observation = env.get_observation()
    prompt = observation[0][1]
    example = re.search(r"e\.g\. '([\d ]+)'", prompt).group(1)
    assert f"{kwargs['max_turns']} guesses" in prompt
    env.step(example)
    assert env.state.error_count == 0
    assert env.state.turn == 1


def test_secret_is_hidden_during_play_and_revealed_at_terminal():
    env = _fresh()
    secret_text = " ".join(f"[{value}]" for value in _secret(env))
    current = env.render(0)
    assert "Secret Code: [?] [?] [?] [?]" in current
    assert secret_text not in current
    done, _ = env.step(" ".join(map(str, _secret(env))))
    assert done
    assert secret_text in env.render(0)
    assert env.get_board_str() == env.render(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code_length": 7, "num_numbers": 6, "duplicate_numbers": False},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        MastermindEnv(**kwargs)
