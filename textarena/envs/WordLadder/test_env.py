"""Offline deterministic tests for the WordLadder environment.

Single-player: transform the start word into the target word by changing one
letter at a time, where every intermediate word must be a valid English word of
the same length. Puzzles are generated from the Basic English words in
``env.word_list``; moves are checked against the full dictionary in
``env.universal_word_list``. We reconstruct ladders with a BFS over either
vocabulary. Word format: a bare word.
"""
from collections import deque
import copy

import pytest

import textarena as ta
from textarena.envs.registration import ENV_REGISTRY
from textarena.envs.WordLadder.env import WordLadderEnv
from textarena.utils import word_lists
from textarena.utils.word_lists import get_basic_english_words

REGISTERED_IDS = sorted(
    env_id for env_id, spec in ENV_REGISTRY.items()
    if spec.entry_point == "textarena.envs.WordLadder.env:WordLadderEnv"
)


class _MissingCorpus:
    def words(self, *_args, **_kwargs):
        raise LookupError("corpus unavailable")


def _without_nltk(monkeypatch):
    monkeypatch.setattr("textarena.envs.WordLadder.env.words", _MissingCorpus())
    monkeypatch.setattr("textarena.utils.word_lists.words", _MissingCorpus())


def _fresh(min_distance=3, max_distance=5, max_turns=100):
    env = WordLadderEnv(min_distance=min_distance, max_distance=max_distance, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _bfs_path(env, vocabulary=None, start=None):
    """Find a shortest ladder from start (default: the start word) to target; defaults to the accepted words."""
    start, target = start or env.start_word, env.target_word
    length = len(target)
    if vocabulary is None:
        vocabulary = env.universal_word_list
    vocab = {w for w in vocabulary if len(w) == length}
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


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("no brackets word")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]
    assert f"a {len(env.target_word)}-letter English word that differs from '{env.start_word}'" in env.action_format

    next_word = _bfs_path(env)[1]
    env.step(next_word)
    assert env.state.turn == 1 and env.state.error_count == 0
    assert f"differs from '{next_word}'" in env.action_format


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
    # Single-player: repeated invalid ends the game with a completion reward, nothing for the start word.
    assert env.state.rewards == {0: 0}


@pytest.mark.parametrize("env_id", REGISTERED_IDS)
@pytest.mark.parametrize("seed", range(5))
def test_immediate_invalid_policy_scores_zero_on_registered_configs(env_id, seed):
    env = ta.make(env_id)
    env.reset(num_players=1, seed=seed)
    for _ in range(5):
        done, _ = env.step("@@@ not a move @@@")
        if done:
            break
    assert done
    assert env.close()[0] == {0: 0}


def test_partial_progress_counts_ladder_moves_cut_from_the_start_distance():
    env = _fresh()
    path = _bfs_path(env)
    distance = len(path) - 1
    assert distance >= 2
    for word in path[1:-1]:  # stop one word short of the target
        done, _ = env.step(word)
        assert not done
    env.step("bad one")
    done, _ = env.step("bad two")
    assert done
    assert env.state.rewards == {0: pytest.approx((distance - 1) / distance)}


def test_moving_away_and_back_earns_nothing():
    env = _fresh()
    path = _bfs_path(env)
    for word in (path[1], path[0], path[1], path[0]):
        done, _ = env.step(word)
        assert not done and env.state.error_count == 0
    env.step("bad one")
    done, _ = env.step("bad two")
    assert done and env.state.rewards == {0: 0}


def test_matching_more_letters_of_the_target_is_not_progress_by_itself():
    env = _fresh()
    env.state.game_state.update(start_word="boot", target_word="heat", current_word="boot", history=["boot"])
    # "hoot" matches the h and t of "heat" ("boot" only the t), but its ladder to "heat" is no shorter.
    assert len(_bfs_path(env, start="hoot")) >= len(_bfs_path(env))
    done, _ = env.step("hoot")
    assert not done
    env.step("bad one")
    done, _ = env.step("bad two")
    assert done and env.state.rewards == {0: 0}


def test_shortening_the_ladder_scores_without_matching_more_letters():
    env = _fresh()
    env.state.game_state.update(start_word="good", target_word="cord", current_word="good", history=["good"])
    start_distance = len(_bfs_path(env)) - 1
    distance = len(_bfs_path(env, start="food")) - 1
    assert distance < start_distance  # "food" matches the same o and d of "cord" as "good"
    done, _ = env.step("food")
    assert not done
    env.step("bad one")
    done, _ = env.step("bad two")
    assert done
    assert env.state.rewards == {0: pytest.approx((start_distance - distance) / start_distance)}


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
    common_path = _bfs_path(first, first.word_list)
    assert common_path is not None
    assert first.min_distance <= len(common_path) - 1 <= first.max_distance
    # Other dictionary words may offer a shortcut, never a longer shortest ladder.
    assert len(_bfs_path(first)) <= len(common_path)


def test_every_puzzle_word_is_an_accepted_move():
    env = _fresh()
    assert set(env.word_list) <= env.universal_word_list
    assert len(env.universal_word_list) > 2 * len(env.word_list)


def test_dictionary_words_beyond_the_puzzle_vocabulary_are_accepted():
    env = _fresh()
    assert {"hear", "bear", "pan"} <= env.universal_word_list
    env.state.game_state.update(
        start_word="fear", target_word="meal", current_word="fear", history=["fear"]
    )
    for word in ("bear", "hear", "heal"):
        done, _ = env.step(word)
        assert not done and env.state.error_count == 0
    assert env.history == ["fear", "bear", "hear", "heal"]
    done, _ = env.step("meal")
    assert done and env.state.rewards == {0: 1}


def test_non_dictionary_word_is_rejected_atomically():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("q" * len(env.target_word))
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_prompt_states_which_words_count():
    env = _fresh()
    prompt = env.prompt(0)
    assert f"must have {len(env.target_word)} letters" in prompt
    assert "British and American English dictionaries counts" in prompt
    assert "plurals and other inflected forms" in prompt
    assert "proper nouns and abbreviations do not" in prompt
    assert f"You have {env.max_turns} moves" in prompt


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
    distance = len(path) - 1
    assert env.state.rewards == {0: pytest.approx(1 / distance)}
    assert f"closing {round(100 / distance)}% of the start word's ladder distance" in env.state.game_info[0]["reason"]


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
    _without_nltk(monkeypatch)
    env = WordLadderEnv(
        min_distance=min_distance,
        max_distance=max_distance,
        max_turns=100,
    )
    env.reset(num_players=1, seed=3)
    basic = get_basic_english_words()
    assert env.word_list == sorted(word for word in basic if 3 <= len(word) <= 11)
    assert len(env.word_list) == 828
    assert env.start_word in basic and env.target_word in basic
    assert {"hear", "bear", "pan"} <= env.universal_word_list
    assert set(env.word_list) <= env.universal_word_list
    path = _bfs_path(env, env.word_list)
    assert path is not None
    assert min_distance <= len(path) - 1 <= max_distance


@pytest.mark.parametrize("min_distance,max_distance", [(5, 7), (13, 15)])
def test_puzzles_are_identical_with_and_without_nltk(monkeypatch, min_distance, max_distance):
    def puzzles():
        env = WordLadderEnv(min_distance=min_distance, max_distance=max_distance, max_turns=100)
        result = []
        for seed in range(5):
            env.reset(num_players=1, seed=seed)
            result.append((env.start_word, env.target_word))
        return env.word_list, result

    with_nltk = puzzles()
    _without_nltk(monkeypatch)
    word_lists._load_basic_english.cache_clear()
    assert puzzles() == with_nltk
