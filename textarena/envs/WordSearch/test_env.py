"""Offline deterministic tests for the WordSearch environment.

Single-player: the player must locate hidden words on a grid by giving the
start/end coordinates of each word. We read the hidden word placements from
``env.placed_words`` so we can script a guaranteed full solve. Move format:
'start_row start_col end_row end_col'.
"""
import copy

import pytest

from textarena.envs.WordSearch.env import WordSearchEnv


def _fresh(max_turns=50):
    env = WordSearchEnv(max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _endpoints(word, row, col, direction):
    if direction == "across":
        return row, col, row, col + len(word) - 1
    return row, col, row + len(word) - 1, col


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


def test_paired_legacy_brackets_remain_valid():
    env = _fresh()
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    sr, sc, er, ec = _endpoints(word, row, col, direction)
    done, _ = env.step(f"[{sr} {sc} {er} {ec}]")
    assert not done
    assert word in env.correct_words


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


@pytest.mark.parametrize("kwargs", [{"max_turns": 0}, {"hardcore": "yes"}])
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        WordSearchEnv(**kwargs)


def test_turn_limit_counts_successful_guess_and_awards_word_progress():
    env = _fresh(max_turns=1)
    word, (row, col, direction) = next(iter(env.placed_words.items()))
    action = " ".join(map(str, _endpoints(word, row, col, direction)))
    done, _ = env.step(action)
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.rewards == {0: 1 / len(env.placed_words)}
