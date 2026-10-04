"""Offline deterministic tests for the single-player Set environment."""
import itertools
import random
import re
import time

import pytest

from textarena.envs.Set.env import SetEnv, _is_set


def _fresh():
    env = SetEnv()
    env.reset(num_players=1, seed=42)
    return env


def _find_set(board):
    """Return 1-based indices (a, b, c) of a valid Set on the board, or None."""
    for combo in itertools.combinations(range(len(board)), 3):
        cards = (board[combo[0]], board[combo[1]], board[combo[2]])
        if _is_set(cards):
            return tuple(i + 1 for i in combo)
    return None


def _find_non_set(board):
    for combo in itertools.combinations(range(len(board)), 3):
        cards = (board[combo[0]], board[combo[1]], board[combo[2]])
        if not _is_set(cards):
            return tuple(i + 1 for i in combo)
    return None


def test_reset_initial_state():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["board"]) == 12
    assert len(gs["deck"]) == 81 - 12
    assert gs["score"] == 0
    assert gs["num_turns"] == 0


def test_valid_set_scores_a_point():
    env = _fresh()
    indices = _find_set(env.state.game_state["board"])
    assert indices is not None, "seed 42 board should contain a Set"
    done, _ = env.step(f"{indices[0]}, {indices[1]}, {indices[2]}")
    assert not done
    assert env.state.game_state["score"] == 1
    assert env.state.game_state["num_turns"] == 1


def test_non_set_wastes_turn():
    env = _fresh()
    indices = _find_non_set(env.state.game_state["board"])
    assert indices is not None
    done, _ = env.step(f"{indices[0]}, {indices[1]}, {indices[2]}")
    assert not done
    assert env.state.game_state["score"] == 0
    assert env.state.game_state["num_turns"] == 1


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("I pick no cards")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["num_turns"] == 0  # malformed => turn not consumed


def test_huge_numeric_indices_are_rejected_without_integer_parse_failure():
    env = _fresh()
    action = f"{'9' * 5000}, 1, 2"
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["num_turns"] == 0


def test_out_of_range_indices_rejected():
    env = _fresh()
    done, _ = env.step("1, 2, 999")
    assert not done
    assert env.state.error_count == 1


def test_game_ends_after_20_turns_reward_equals_score():
    env = _fresh()
    # Repeatedly submit a valid-range but non-Set triple so the board never
    # changes (the board always contains a Set with this seed), guaranteeing a
    # deterministic score of 0 across all 20 turns.
    non_set = _find_non_set(env.state.game_state["board"])
    assert non_set is not None
    done = False
    for _ in range(20):
        assert not done
        done, _ = env.step(f"{non_set[0]}, {non_set[1]}, {non_set[2]}")
    assert done
    assert env.state.game_state["num_turns"] == 20
    assert env.state.rewards == {0: env.state.game_state["score"]}
    assert env.state.rewards == {0: 0}


def test_duplicate_indices_are_invalid_and_atomic():
    env = _fresh()
    board_before = list(env.state.game_state["board"])
    done, _ = env.step("1, 1, 1")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["num_turns"] == 0
    assert env.state.game_state["score"] == 0
    assert env.state.game_state["board"] == board_before


def test_malformed_action_does_not_trigger_no_set_deal():
    env = _fresh()
    c1 = ("one", "red", "open", "oval")
    c2 = ("two", "green", "striped", "diamond")
    missing = ("three", "purple", "solid", "squiggle")
    env.state.game_state["board"] = [c1, c2]
    env.state.game_state["deck"] = [missing]
    done, _ = env.step("not a selection")
    assert not done
    assert env.state.game_state["board"] == [c1, c2]
    assert env.state.game_state["deck"] == [missing]


def test_no_set_board_deals_until_a_set_exists():
    env = _fresh()
    c1 = ("one", "red", "open", "oval")
    c2 = ("two", "green", "striped", "diamond")
    missing = ("three", "purple", "solid", "squiggle")
    env.state.game_state["board"] = [c1, c2]
    env.state.game_state["deck"] = [missing]
    assert env._ensure_set_available()
    assert env.state.game_state["board"] == [c1, c2, missing]
    assert env.state.game_state["deck"] == []


def test_last_available_set_ends_game_early():
    env = _fresh()
    cards = (
        ("one", "red", "open", "oval"),
        ("two", "green", "striped", "diamond"),
        ("three", "purple", "solid", "squiggle"),
    )
    env.state.game_state["board"] = list(cards)
    env.state.game_state["deck"] = []
    done, _ = env.step("1, 2, 3")
    assert done
    assert env.state.game_state["score"] == 1
    assert env.state.rewards == {0: 1}


def test_cards_are_conserved_after_scoring():
    env = _fresh()
    indices = _find_set(env.state.game_state["board"])
    env.step(", ".join(map(str, indices)))
    gs = env.state.game_state
    all_cards = gs["deck"] + gs["board"] + gs["found_cards"]
    assert len(all_cards) == 81
    assert len(set(all_cards)) == 81


def test_repeat_reset_replays_same_board():
    env = _fresh()
    first_board = list(env.state.game_state["board"])
    indices = _find_set(first_board)
    env.step(", ".join(map(str, indices)))
    env.reset(num_players=1, seed=42)
    assert env.state.game_state["board"] == first_board


def test_snapshot_restore_replays_scoring_move():
    env = _fresh()
    indices = _find_set(env.state.game_state["board"])
    action = ", ".join(map(str, indices))
    before = env.snapshot()
    env.step(action)
    expected = env.snapshot()
    env.restore(before)
    env.step(action)
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


def test_invalid_limit_preserves_points_already_earned():
    env = _fresh()
    indices = _find_set(env.state.game_state["board"])
    env.step(", ".join(map(str, indices)))
    assert env.state.game_state["score"] == 1
    env.step("not a selection")
    done, _ = env.step("still not a selection")
    assert done
    assert env.state.rewards == {0: 1}


def test_seeding_only_happens_through_reset():
    with pytest.raises(TypeError):
        SetEnv(seed=1)


def test_prompt_describes_the_deck_refills_and_early_end():
    env = _fresh()
    prompt = env.state.events[0][1]
    assert "color (red, green, purple), fill (open, striped, solid), and shape (oval, diamond, squiggle)" in prompt
    assert "refilled up to 12 cards" in prompt
    assert "or earlier if no Set remains and the deck is empty" in prompt
    assert "12 or more" not in prompt


def test_valid_non_set_move_ends_when_no_sets_can_remain():
    env = _fresh()
    board = [
        ("one", "red", "open", "oval"),
        ("one", "red", "open", "diamond"),
        ("one", "red", "striped", "oval"),
    ]
    assert not _is_set(tuple(board))
    env.state.game_state["board"] = board
    env.state.game_state["deck"] = []
    done, _ = env.step("1, 2, 3")
    assert done
    assert env.state.rewards == {0: 0}


_REFERENCE_ACTION_REGEX = re.compile(r"([0-9]{1,6})\s*[,\s]\s*([0-9]{1,6})\s*[,\s]\s*([0-9]{1,6})")


def _reference_parse(action):
    m = _REFERENCE_ACTION_REGEX.fullmatch(action.strip())
    return None if m is None else tuple(int(g) for g in m.groups())


def test_tokenized_parser_accepts_exactly_what_the_reference_regex_accepts():
    env = _fresh()
    rng = random.Random(0)
    alphabet = ["1", "2", "12", "1234567", " ", "  ", ",", ", ", "[", "]", "x", "\t", "٣"]
    for _ in range(20000):
        action = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 9)))
        assert env._parse_action(action) == _reference_parse(action), repr(action)


def test_long_whitespace_runs_are_parsed_in_linear_time():
    env = _fresh()
    before = env.state.game_state["num_turns"]
    for action in ("4" + " " * 30000 + "x", " " * 30000 + "1 2 3x", "1" + " ," * 15000 + "2"):
        start = time.perf_counter()
        env.step(action)
        assert time.perf_counter() - start < 0.25, repr(action[:20])
    assert env.state.game_state["num_turns"] == before
