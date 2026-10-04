"""Deterministic game-logic tests for Game2048 (single player).

Tile spawns are random, so we overwrite ``game_state['board']`` to script
guaranteed merges/outcomes.
"""
import copy

import pytest

from textarena.envs.Game2048.env import Game2048Env


def _fresh(target_tile=4, board_size=2):
    env = Game2048Env(target_tile=target_tile, board_size=board_size)
    env.reset(num_players=1, seed=42)
    return env


def test_reaching_target_tile_wins():
    env = _fresh(target_tile=4, board_size=2)
    env.state.game_state["board"] = [[2, 2], [0, 0]]
    done, _ = env.step("left")  # merges into a 4 -> reaches target
    assert done and env.state.rewards == {0: 1.0}
    assert sum(cell != 0 for row in env.state.game_state["board"] for cell in row) == 1
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def test_merge_increases_score():
    env = _fresh(target_tile=2048, board_size=2)
    env.state.game_state["board"] = [[2, 2], [0, 0]]
    done, _ = env.step("left")
    assert not done and env.state.game_state["score"] == 4


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no direction")
    assert not done and env.state.error_count == 1


def test_no_change_move_rejected():
    env = _fresh(target_tile=2048, board_size=2)
    # A single tile in the top-left cannot move further up/left.
    env.state.game_state["board"] = [[2, 0], [0, 0]]
    before = copy.deepcopy(env.state.game_state)
    rng_before = env.rng.getstate()
    done, _ = env.step("up")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before
    assert env.rng.getstate() == rng_before


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("also garbage")
    assert done and env.state.game_info[0]["invalid_move"] is True


def test_each_tile_merges_at_most_once():
    env = _fresh(target_tile=2048, board_size=4)
    assert env._compress_and_merge([2, 2, 2, 2]) == ([4, 4, 0, 0], 8)
    assert env._compress_and_merge([2, 2, 4, 0]) == ([4, 4, 0, 0], 4)


@pytest.mark.parametrize("action", ["[left", "left]", "left now", "A", "LEFT_RIGHT"])
def test_parser_rejects_noncanonical_actions(action):
    env = _fresh(target_tile=2048, board_size=2)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_paired_legacy_brackets_remain_valid():
    env = _fresh(target_tile=2048, board_size=2)
    env.state.game_state["board"] = [[2, 0], [0, 0]]
    done, _ = env.step("[right]")
    assert not done
    assert env.state.game_state["board"][0][1] == 2


@pytest.mark.parametrize(
    "kwargs",
    [
        {"target_tile": 2},
        {"target_tile": 12},
        {"target_tile": Game2048Env.MAX_TARGET_TILE * 2},
        {"board_size": 1},
        {"board_size": 11},
        {"board_size": True},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        Game2048Env(**kwargs)


def test_seeded_rngs_and_snapshot_restore_spawn_exactly():
    first = _fresh(target_tile=2048, board_size=2)
    second = _fresh(target_tile=2048, board_size=2)
    assert first.state.game_state == second.state.game_state

    board = [[2, 0], [0, 0]]
    first.state.game_state["board"] = copy.deepcopy(board)
    second.state.game_state["board"] = copy.deepcopy(board)
    snapshot = first.snapshot()
    first.step("right")
    expected = copy.deepcopy(first.state.game_state)

    first.restore(snapshot)
    first.step("right")
    second.step("right")
    assert first.state.game_state == expected == second.state.game_state


def test_repeat_reset_replays_seed_without_aliasing_old_state():
    env = _fresh(target_tile=2048, board_size=4)
    expected = copy.deepcopy(env.state.game_state)
    old_board = env.state.game_state["board"]
    env.step("left")
    env.reset(num_players=1, seed=42)
    assert env.state.game_state == expected
    assert env.state.game_state["board"] is not old_board


def test_spawned_full_board_without_merges_terminates_as_loss():
    env = _fresh(target_tile=2048, board_size=2)
    env.state.game_state["board"] = [[8, 16], [32, 0]]
    done, _ = env.step("down")
    assert done
    assert env._check_status() == "lose"
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert 0.0 < env.state.rewards[0] < 1.0
