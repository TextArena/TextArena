"""Offline deterministic tests for the WordSearch environment.

Single-player: the player must locate hidden words on a grid by giving the
start/end coordinates of each word. We read the hidden word placements from
``env.placed_words`` so we can script a guaranteed full solve. Move format:
'start_row start_col end_row end_col'.
"""
import copy

import pytest

from textarena.envs.WordSearch.env import WordSearchEnv
from textarena.utils.word_lists import get_common_words, get_headwords


def _fresh(max_turns=None):
    env = WordSearchEnv(max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _endpoints(word, row, col, direction):
    if direction == "across":
        return row, col, row, col + len(word) - 1
    return row, col, row + len(word) - 1, col


def _correct_guesses(env):
    return [" ".join(map(str, _endpoints(word, *placement))) for word, placement in env.placed_words.items()]


def _incorrect_guesses(env, count):
    """Distinct single-cell selections; every placed word has at least two letters."""
    size = len(env.state.game_state["board"])
    cells = [(row, col) for row in range(size) for col in range(size)][:count]
    assert len(cells) == count
    return [f"{row} {col} {row} {col}" for row, col in cells]


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert len(env.placed_words) >= 1
    assert env.num_incorrect_tries == 20


def test_full_solve_wins():
    env = _fresh()
    placements = dict(env.placed_words)  # snapshot
    done = False
    for word, (row, col, direction) in placements.items():
        sr, sc, er, ec = _endpoints(word, row, col, direction)
        done, _ = env.step(f"{sr} {sc} {er} {ec}")
    assert done
    assert env.state.rewards == {0: 1.0}
    assert env.state.turn == len(placements)
    assert env.state.game_info[0]["turn_count"] == len(placements)


def test_invalid_format_rejected():
    env = _fresh()
    done, _ = env.step("I have no coordinates")
    assert not done
    assert env.state.error_count == 1


def test_out_of_bounds_rejected():
    env = _fresh()
    size = len(env.state.game_state["board"])
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(f"0 0 0 {size + 5}")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_oversized_coordinate_is_atomic_invalid():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(f"{'9' * 1000} 0 0 0")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_incorrect_attempt_decrements_tries():
    env = _fresh()
    # A zero-length selection can never match a placed word (all words len>=2).
    done, _ = env.step("0 0 0 0")
    assert not done
    assert env.num_incorrect_tries == 19


def test_finding_one_word_marks_it_correct():
    env = _fresh()
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    sr, sc, er, ec = _endpoints(word, row, col, direction)
    env.step(f"{sr} {sc} {er} {ec}")
    assert word in env.correct_words


@pytest.mark.parametrize(
    "action",
    ["[0 0 0 0", "0 0 0 0]", "0, 0, 0, 0", "0 0 0", "0 0 0 0 trailing"],
)
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_repeated_successful_guess_in_either_direction_is_atomic_invalid():
    env = _fresh()
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    sr, sc, er, ec = _endpoints(word, row, col, direction)
    env.step(f"{sr} {sc} {er} {ec}")
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(f"{er} {ec} {sr} {sc}")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_diagonal_selection_cannot_match_horizontal_word():
    env = _fresh()
    horizontal = next(
        (item for item in env.placed_words.items() if item[1][2] == "across"),
        None,
    )
    if horizontal is None:
        pytest.skip("seed did not place a horizontal word")
    word, (row, col, _) = horizontal
    tries_before = env.num_incorrect_tries
    done, _ = env.step(f"{row} {col} {row + 1} {col + len(word) - 1}")
    assert not done
    assert word not in env.correct_words
    assert env.num_incorrect_tries == tries_before - 1


def test_many_seeded_boards_place_exactly_five_extractable_words():
    for seed in range(40):
        env = WordSearchEnv(max_turns=20)
        env.reset(num_players=1, seed=seed)
        assert len(env.placed_words) == env.num_words
        for word, (row, col, direction) in env.placed_words.items():
            sr, sc, er, ec = _endpoints(word, row, col, direction)
            assert env._extract_word(env.game_state["board"], sr, sc, er, ec) == word
            assert env._check_word(env.game_state["board"], sr, sc, er, ec)


def test_nonoverlapping_short_words_are_all_placeable_across_seeds():
    env = WordSearchEnv(max_turns=20)
    env.word_list = ["AB", "CD", "EF", "GH", "IJ"]

    for seed in range(40):
        env.reset(num_players=1, seed=seed)
        assert set(env.placed_words) == set(env.word_list)
        for word, (row, col, direction) in env.placed_words.items():
            endpoints = _endpoints(word, row, col, direction)
            assert env._extract_word(env.game_state["board"], *endpoints) == word


def test_seeded_instances_repeat_without_state_leakage():
    first = _fresh()
    second = _fresh()
    assert first.state.game_state == second.state.game_state
    old_board = first.state.game_state["board"]

    word, (row, col, direction) = next(iter(first.placed_words.items()))
    first.step(" ".join(map(str, _endpoints(word, row, col, direction))))
    first.reset(num_players=1, seed=42)
    assert first.state.game_state == second.state.game_state
    assert first.state.game_state["board"] is not old_board


def test_snapshot_restores_attempt_history_and_highlights():
    env = _fresh()
    snapshot = env.snapshot()
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    action = " ".join(map(str, _endpoints(word, row, col, direction)))
    env.step(action)
    assert env.highlighted_positions

    env.restore(snapshot)
    assert not env.highlighted_positions
    assert not env.attempted_coordinates
    env.step(action)
    assert word in env.correct_words


def test_renderer_tracks_highlighted_positions():
    env = _fresh()
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    action = " ".join(map(str, _endpoints(word, row, col, direction)))
    env.step(action)
    assert f"[{word[0]}]" in env.get_board_str()


def test_helpers_reject_bad_bounds_and_direction():
    env = _fresh()
    grid = [["."] * 5 for _ in range(5)]
    assert not env._can_place_word(grid, "DOG", "across", -1, 0)
    assert not env._can_place_word(grid, "DOG", "down", 0, -1)
    assert not env._can_place_word(grid, "DOG", "diagonal", 0, 0)
    assert not env._can_place_word(grid, "DOG", "across", 0, 3)


@pytest.mark.parametrize("kwargs", [{"max_turns": 0}, {"max_turns": True}, {"hardcore": "yes"}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        WordSearchEnv(**kwargs)


def test_explicit_guess_cap_counts_correct_guesses_and_awards_word_progress():
    env = _fresh(max_turns=1)
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    action = " ".join(map(str, _endpoints(word, row, col, direction)))
    done, _ = env.step(action)
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.rewards == {0: 1 / len(env.placed_words)}
    assert "limit of 1 guesses" in env.state.game_info[0]["reason"]


def test_default_game_allows_all_incorrect_attempts_after_finding_a_word():
    env = _fresh()
    env.step(_correct_guesses(env)[0])
    misses = _incorrect_guesses(env, env.MAX_INCORRECT_TRIES)
    for miss in misses[:-1]:
        done, _ = env.step(miss)
        assert not done
    assert env.num_incorrect_tries == 1
    done, _ = env.step(misses[-1])
    assert done
    assert env.state.turn == 1 + env.MAX_INCORRECT_TRIES
    assert env.state.rewards == {0: round(1 / env.num_words, 3)}
    assert env.state.game_info[0]["reason"].startswith("No more incorrect tries remaining")


def test_default_guess_cap_is_never_reached_by_the_longest_game():
    env = _fresh()
    assert env.max_turns == env.num_words + env.MAX_INCORRECT_TRIES
    for guess in _correct_guesses(env)[:-1]:
        done, _ = env.step(guess)
        assert not done
    for miss in _incorrect_guesses(env, env.MAX_INCORRECT_TRIES):
        done, _ = env.step(miss)
    assert done
    assert env.state.turn == env.num_words - 1 + env.MAX_INCORRECT_TRIES < env.max_turns
    assert env.state.game_info[0]["reason"].startswith("No more incorrect tries remaining")
    assert env.state.rewards == {0: round((env.num_words - 1) / env.num_words, 3)}


def test_prompt_states_the_limits_that_can_end_the_game():
    default_prompt = _fresh().prompt(0)
    assert "You have a total of 20 incorrect attempts. Correct guesses do not use them up" in default_prompt
    assert "guesses in total" not in default_prompt

    capped_prompt = _fresh(max_turns=10).prompt(0)
    assert "The game also ends after 10 guesses in total, correct or incorrect." in capped_prompt


@pytest.mark.parametrize("hardcore", [False, True])
def test_words_come_from_the_common_words_or_headwords(hardcore):
    first = WordSearchEnv(hardcore=hardcore)
    second = WordSearchEnv(hardcore=hardcore)
    expected = get_headwords() if hardcore else get_common_words()
    assert first.word_list == sorted(word.upper() for word in expected)

    first.reset(num_players=1, seed=3)
    second.reset(num_players=1, seed=3)
    assert first.state.game_state == second.state.game_state
    assert set(first.placed_words) <= set(first.word_list)
    done = False
    for guess in _correct_guesses(first):
        done, _ = first.step(guess)
    assert done and first.state.rewards == {0: 1.0}
