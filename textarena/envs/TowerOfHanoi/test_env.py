"""Offline, deterministic tests for the Tower of Hanoi environment.

Single-player puzzle: move all disks from tower A to tower C. With 2 disks the
optimal solution is 'A B', 'A C', 'B C', which we script to reach the winning
terminal state (reward 1). Moves use bare ``source target`` tower letters.
"""

import copy

import pytest

from textarena.envs.TowerOfHanoi.env import TowerOfHanoiEnv


def _fresh(num_disks=2, max_turns=100):
    env = TowerOfHanoiEnv(num_disks=num_disks, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_structure():
    env = _fresh()
    towers = env.state.game_state["towers"]
    assert towers["A"] == [2, 1]  # largest at the base, smallest on top
    assert towers["B"] == [] and towers["C"] == []
    assert env.state.current_player_id == 0


def test_solving_two_disks_wins():
    env = _fresh()
    done = False
    for move in ["A B", "A C", "B C"]:
        done, _ = env.step(move)
    assert done
    assert env.state.game_state["towers"]["C"] == [2, 1]
    assert env.state.rewards == {0: 1}
    assert env.state.turn == 3
    assert env.state.game_info[0]["turn_count"] == 3


def test_bad_format_is_invalid():
    env = _fresh()
    done, _ = env.step("move from A to C")
    assert not done
    assert env.state.error_count == 1


def test_larger_on_smaller_rejected():
    env = _fresh()
    env.step("A B")  # disk 1 -> B
    # Now A's top is disk 2; placing it onto B (holding disk 1) is illegal.
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("A B")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_move_from_empty_tower_rejected():
    env = _fresh()
    done, _ = env.step("C A")  # C is empty at the start
    assert not done
    assert env.state.error_count == 1


def test_valid_move_updates_towers():
    env = _fresh()
    done, _ = env.step("A C")  # disk 1 -> C
    assert not done
    assert env.state.game_state["towers"]["C"] == [1]
    assert env.state.game_state["towers"]["A"] == [2]


@pytest.mark.parametrize("action", ["AC", "[A C", "A C]", "A C trailing", "move A C"])
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_paired_legacy_brackets_and_comma_remain_valid():
    env = _fresh()
    done, _ = env.step("[A, C]")
    assert not done
    assert env.state.game_state["towers"] == {"A": [2], "B": [], "C": [1]}


def test_same_tower_move_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("A A")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before
    assert env.state.turn == 0


def test_snapshot_and_repeat_reset_restore_towers():
    env = _fresh()
    initial = copy.deepcopy(env.state.game_state)
    snapshot = env.snapshot()
    env.step("A C")
    env.restore(snapshot)
    assert env.state.game_state == initial

    env.reset(num_players=1, seed=999)
    assert env.state.game_state == initial


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_disks": 0},
        {"num_disks": True},
        {"max_turns": 0},
        {"num_disks": 3, "max_turns": 6},
        {"num_disks": TowerOfHanoiEnv.MAX_DISKS + 1, "max_turns": 2 ** (TowerOfHanoiEnv.MAX_DISKS + 1) - 1},
    ],
)
def test_invalid_or_unsolvable_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        TowerOfHanoiEnv(**kwargs)


def test_turn_limit_counts_final_legal_move_and_returns_partial_reward():
    env = _fresh(num_disks=2, max_turns=3)
    for move in ("A C", "A B", "C A"):
        done, _ = env.step(move)
    assert done
    assert env.state.turn == 3
    assert env.state.game_info[0]["turn_count"] == 3
    assert env.state.rewards == {0: 0.0}
