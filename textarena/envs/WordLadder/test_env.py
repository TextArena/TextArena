"""Offline deterministic tests for the WordLadder environment.

Single-player: transform the start word into the target word by changing one
letter at a time, where every intermediate word must be a valid English word of
the same length. We reconstruct a winning path with a BFS over the environment's
own accepted vocabulary (``env.universal_word_list``). Word format: a bare word.
"""
from collections import deque
import copy

import pytest

from textarena.envs.WordLadder.env import WordLadderEnv


def _fresh(min_distance=3, max_distance=5, max_turns=100):
    env = WordLadderEnv(min_distance=min_distance, max_distance=max_distance, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _bfs_path(env):
    """Find a valid ladder from start to target using the env's own word set."""
    start, target = env.start_word, env.target_word
    length = len(target)
    vocab = {w for w in env.universal_word_list if len(w) == length}
    vocab.add(start)
    vocab.add(target)
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    visited = {start}
    q = deque([(start, [start])])
    while q:
        cur, path = q.popleft()
        if cur == target:
            return path
        for i, orig in enumerate(cur):
            for ch in alphabet:
                if ch == orig:
                    continue
                nxt = cur[:i] + ch + cur[i + 1:]
                if nxt in vocab and nxt not in visited:
                    visited.add(nxt)
                    q.append((nxt, path + [nxt]))
    return None


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert env.current_word == env.start_word
    assert len(env.start_word) == len(env.target_word)
    assert env.start_word != env.target_word


def test_scripted_ladder_wins():
    env = _fresh()
    path = _bfs_path(env)
    assert path is not None
    done = False
    for word in path[1:]:  # skip the start word itself
        done, _ = env.step(word)
    assert done
    assert env.state.rewards == {0: 1}


def test_reaching_target_on_turn_limit_is_still_a_win():
    env = _fresh()
    path = _bfs_path(env)
    assert path is not None
    env.state.max_turns = len(path) - 1
    for word in path[1:]:
        done, _ = env.step(word)
    assert done
    assert env.state.turn == len(path) - 1
    assert env.state.rewards == {0: 1}


def test_invalid_format_rejected():
    env = _fresh()
    done, _ = env.step("no brackets word")
    assert not done
    assert env.state.error_count == 1


def test_wrong_length_rejected():
    env = _fresh()
    # A single-letter word cannot match a multi-letter target length.
    done, _ = env.step("a")
    assert not done
    assert env.state.error_count == 1


def test_non_one_letter_change_rejected():
    env = _fresh()
    # Resubmitting the start word is 0 letters different -> rejected.
    done, _ = env.step(env.start_word)
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("bad one")
    done, _ = env.step("bad two")
    assert done
    # Single-player: repeated invalid ends the game with a completion reward.
    assert 0 <= env.state.rewards[0] <= 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_distance": 0, "max_distance": 2, "max_turns": 3},
        {"min_distance": 4, "max_distance": 3, "max_turns": 4},
        {"min_distance": 4, "max_distance": 5, "max_turns": 3},
        {"min_distance": 3, "max_distance": 5, "max_turns": 4},
        {"min_distance": 1, "max_distance": 2, "max_turns": 0},
    ],
)
def test_invalid_distance_and_turn_bounds_are_rejected(kwargs):
    with pytest.raises(ValueError):
        WordLadderEnv(**kwargs)


def test_impossible_dictionary_fails_instead_of_looping_forever():
    env = WordLadderEnv(min_distance=3, max_distance=3, max_turns=3)
    env.word_list = ["cat", "dog"]
    with pytest.raises(ValueError, match="No word-ladder pair"):
        env.reset(num_players=1, seed=1)


def test_seeded_setup_is_deterministic_and_within_distance():
    first = _fresh()
    second = _fresh()
    assert first.state.game_state == second.state.game_state
    path = _bfs_path(first)
    assert path is not None
    assert first.min_distance <= len(path) - 1 <= first.max_distance


def test_invalid_move_does_not_mutate_ladder():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("two words")
    assert not done
    assert env.state.game_state == before
    assert env.state.turn == 0


def test_renderer_reads_structured_history_without_text_artifacts():
    env = _fresh()
    path = _bfs_path(env)
    assert path is not None
    env.step(path[1])
    board = env.get_board_str()
    assert f"Step 1: {path[0]}" in board
    assert f"Step 2: {path[1]}" in board
    assert "Target Word:" not in board


def test_turn_limit_counts_valid_moves_and_returns_bounded_reward():
    env = _fresh()
    path = _bfs_path(env)
    assert path is not None and len(path) > 2
    env.state.max_turns = 1
    done, _ = env.step(path[1])
    assert done
    assert env.state.turn == 1
    assert 0 <= env.state.rewards[0] <= 1


def test_snapshot_restores_history_and_static_vocabulary():
    env = _fresh()
    vocabulary = env.universal_word_list
    word_list = env.word_list
    path = _bfs_path(env)
    assert path is not None
    snapshot = env.snapshot()
    env.step(path[1])
    env.restore(snapshot)
    assert env.history == [env.start_word]
    assert env.current_word == env.start_word
    assert env.universal_word_list is vocabulary
    assert env.word_list is word_list


@pytest.mark.parametrize("action", ["abc123", "abc_def", "word!", "[two words]"])
def test_malformed_actions_are_rejected(action):
    env = _fresh()
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("min_distance,max_distance", [(5, 7), (8, 12), (13, 15)])
def test_missing_nltk_corpus_supports_registered_distances(
    monkeypatch, min_distance, max_distance
):
    def unavailable(*_args, **_kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr("textarena.envs.WordLadder.env.words.words", unavailable)
    env = WordLadderEnv(
        min_distance=min_distance,
        max_distance=max_distance,
        max_turns=100,
    )
    env.reset(num_players=1, seed=3)
    assert env.start_word in env.universal_word_list
    assert env.target_word in env.universal_word_list
    path = _bfs_path(env)
    assert path is not None
    assert min_distance <= len(path) - 1 <= max_distance
