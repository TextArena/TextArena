"""Deterministic game-logic tests for Nim-v1.

Moves take the form 'pile quantity', e.g. '0 3'. Whoever removes the
last object(s) wins. We use small custom pile configurations to script
short, fully deterministic games.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.Nim.env import NimEnv


def test_taking_last_object_wins():
    env = NimEnv(piles=[1])
    env.reset(num_players=2, seed=42)
    done = env.step("0 1")  # P0 takes the only object
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_second_player_can_win():
    env = NimEnv(piles=[2])
    env.reset(num_players=2, seed=42)
    env.step("0 1")            # P0 removes 1, one left
    done = env.step("0 1")  # P1 removes the last -> P1 wins
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_removing_more_than_available_is_invalid():
    env = NimEnv(piles=[3])
    env.reset(num_players=2, seed=42)
    done = env.step("0 9")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["piles"] == [3]


def test_out_of_range_pile_is_invalid():
    env = NimEnv(piles=[3, 4])
    env.reset(num_players=2, seed=42)
    done = env.step("5 1")
    assert not done
    assert env.state.error_count == 1


def test_bad_format_is_invalid():
    env = NimEnv(piles=[3])
    env.reset(num_players=2, seed=42)
    done = env.step("take one from pile zero")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize(
    "piles, example",
    [([3, 4, 5], "0 3"), ([4, 2, 3, 7], "0 3"), ([5, 7, 9, 11, 2], "0 3"), ([2, 6], "0 2"), ([0, 5], "1 3")],
)
def test_format_error_describes_expected_action(piles, example):
    env = NimEnv(piles=piles)
    env.reset(num_players=2, seed=42)
    env.step("take one from pile zero")
    notices = [m for _, m, t, _ in env.state.events if t == ta.ObservationType.GAME_ADMIN]
    assert f"Expected {env.action_format}." in notices[-1]
    assert env.action_format.startswith(f"a pile number from 0 to {len(piles) - 1} ")
    assert env.action_format.endswith(f"for example '{example}'")

    fresh = NimEnv(piles=piles)
    fresh.reset(num_players=2, seed=42)
    fresh.step(example)
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


def test_zero_quantity_is_atomic_and_does_not_rotate():
    env = NimEnv(piles=[3])
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.state.game_state)

    done = env.step("0 0")

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ("[0 1", "0 1]"))
def test_unbalanced_brackets_are_rejected(action):
    env = NimEnv(piles=[3])
    env.reset(num_players=2, seed=42)

    done = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["piles"] == [3]


def test_huge_integer_is_rejected_without_conversion_or_mutation(monkeypatch):
    import textarena.envs.Nim.env as nim_module

    env = NimEnv(piles=[3])
    env.reset(num_players=2, seed=42)
    real_int = int

    def guarded_int(text):
        if isinstance(text, str) and len(text) > 1:
            pytest.fail("attempted to convert an unbounded quantity")
        return real_int(text)

    monkeypatch.setattr(nim_module, "int", guarded_int, raising=False)

    done = env.step(f"0 {'9' * 100_000}")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["piles"] == [3]
    admin_messages = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_ADMIN
    ]
    assert len(admin_messages[-1]) < 500


@pytest.mark.parametrize("piles", ([], [0, 0], [-1, 2], [True, 2], "3,4"))
def test_invalid_initial_piles_are_rejected(piles):
    with pytest.raises(ValueError):
        NimEnv(piles=piles)


def test_oversized_initial_configuration_is_rejected():
    with pytest.raises(ValueError, match="piles must be a non-empty list of at most 100 integers"):
        NimEnv(piles=[1] * (NimEnv.MAX_PILES + 1))
    with pytest.raises(ValueError, match="piles must be"):
        NimEnv(piles=[NimEnv.MAX_PILE_SIZE + 1])
    NimEnv(piles=[1] * NimEnv.MAX_PILES)
    NimEnv(piles=(NimEnv.MAX_PILE_SIZE,))


def test_constructor_defensively_copies_initial_piles():
    piles = [1, 2]
    env = NimEnv(piles=piles)
    piles[0] = 99

    env.reset(num_players=2, seed=42)

    assert env.state.game_state["piles"] == [1, 2]


def test_renderer_uses_zero_based_pile_labels():
    env = NimEnv(piles=[0, 2])
    env.reset(num_players=2, seed=42)

    board = env.get_board_str()

    assert "Pile 0:" in board
    assert "Pile 1:" in board
    assert "Row 1:" not in board


def test_renderer_handles_all_empty_terminal_piles():
    env = NimEnv(piles=[1, 2])
    env.reset(num_players=2, seed=42)
    env.state.game_state["piles"] = [0, 0]

    assert env.get_board_str() == "Pile 0: (empty)\nPile 1: (empty)"


def test_renderer_bounds_large_pile_visualization():
    env = NimEnv(piles=[NimEnv.MAX_PILE_SIZE])
    env.reset(num_players=2, seed=42)

    board = env.get_board_str()

    assert board.count("●") == 50
    assert f"({NimEnv.MAX_PILE_SIZE} total)" in board
    assert len(board) < 1_000


def test_terminal_action_is_counted_and_final_state_is_rendered():
    env = NimEnv(piles=[1])
    env.reset(num_players=2, seed=42)

    done = env.step("[0 1]")

    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert "pile 0: 0" in final_board


def test_reset_reuses_constructor_configuration():
    env = NimEnv(piles=[2, 3])
    env.reset(num_players=2, seed=1)
    env.step("1 2")

    env.reset(num_players=2, seed=99)

    assert env.state.game_state["piles"] == [2, 3]
    assert env.state.current_player_id == 0
    assert env.state.turn == 0
