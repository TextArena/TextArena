"""Offline deterministic tests for the WordChains environment.

Two-player game: each word must (1) start with the last letter of the previous
word, (2) be exactly one letter longer than the previous word, (3) be a valid
unused English word. A player loses only by making an invalid move. We read the
hidden requirements from ``env.state.game_state`` to script guaranteed moves.
Word format: bare word, e.g. 'apple' (brackets tolerated).
"""
import copy

from textarena.envs.WordChains.env import WordChainsEnv
from textarena.envs.WordChains.renderer import create_board_str


def _fresh():
    env = WordChainsEnv()
    env.reset(num_players=2, seed=42)
    return env


def _find_valid_word(env):
    """Search the dictionary for a legal next word, or return None."""
    gs = env.state.game_state
    letter = gs["required_start_letter"]
    length = gs["required_length"]
    used = gs["used_words"]
    for w in env.dictionary.get_all_words():
        if len(w) == length and w.startswith(letter) and w not in used and w.isalpha():
            return w
    return None


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    gs = env.state.game_state
    assert gs["required_length"] == len(gs["current_word"]) + 1
    assert gs["required_start_letter"] == gs["current_word"][-1].lower()


def test_valid_move_updates_state_and_rotates():
    env = _fresh()
    word = _find_valid_word(env)
    assert word is not None
    prev_len = env.state.game_state["required_length"]
    done, _ = env.step(word)
    assert not done
    assert env.state.game_state["current_word"] == word
    assert env.state.game_state["required_length"] == prev_len + 1
    assert env.state.current_player_id == 1  # turn rotated


def test_invalid_format_rejected():
    env = _fresh()
    done, _ = env.step("not a single word")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_wrong_length_rejected():
    env = _fresh()
    letter = env.state.game_state["required_start_letter"]
    # Single-letter word starting with the required letter -> wrong length.
    done, _ = env.step(f"[{letter}]")  # brackets tolerated
    assert not done
    assert env.state.error_count == 1


def test_wrong_start_letter_rejected():
    env = _fresh()
    gs = env.state.game_state
    length = gs["required_length"]
    letter = gs["required_start_letter"]
    # Build a word of the right length that starts with a different letter.
    other = "a" if letter != "a" else "b"
    done, _ = env.step(other * length)
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("not a valid word format one")
    done, _ = env.step("not a valid word format two")
    assert done
    # Offender is player 0; opponent wins.
    assert env.state.rewards == {0: -1, 1: 1}


def test_starting_word_always_has_a_legal_successor():
    for seed in range(10):
        env = WordChainsEnv()
        env.reset(num_players=2, seed=seed)
        assert _find_valid_word(env) is not None


def test_seeded_reset_is_deterministic():
    first = _fresh()
    second = _fresh()
    assert first.state.game_state == second.state.game_state


def test_parser_rejects_digits_underscores_and_adversarial_text():
    for action in ("abc123", "abc_def", "word\nsecond", "I choose apple"):
        env = _fresh()
        before = copy.deepcopy(env.state.game_state)
        done, _ = env.step(action)
        assert not done
        assert env.state.game_state == before
        assert env.state.current_player_id == 0


def test_repeated_word_invalid_is_atomic():
    env = _fresh()
    word = _find_valid_word(env)
    assert word is not None
    env.state.game_state["used_words"].add(word)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(word)
    assert not done
    assert env.state.game_state == before


def test_snapshot_restores_word_history_and_dictionary_resource():
    env = _fresh()
    dictionary = env.dictionary
    word_list = env.word_list
    snapshot = env.snapshot()
    word = _find_valid_word(env)
    assert word is not None
    env.step(word)
    env.restore(snapshot)
    assert env.state.game_state["used_words"] == {env.state.game_state["current_word"]}
    assert env.state.current_player_id == 0
    assert env.dictionary is dictionary
    assert env.word_list is word_list


def test_renderer_order_is_stable_for_equal_length_words():
    state = {
        "current_word": "dog",
        "required_start_letter": "g",
        "required_length": 4,
        "used_words": {"dog", "cat", "ape"},
    }
    board = create_board_str(state)
    assert board.index("- ape") < board.index("- cat") < board.index("- dog")


def test_missing_nltk_corpus_uses_offline_dictionary(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr("textarena.envs.WordChains.env.words.words", unavailable)
    env = WordChainsEnv()
    env.reset(num_players=2, seed=4)
    assert env.word_list
    assert _find_valid_word(env) is not None
