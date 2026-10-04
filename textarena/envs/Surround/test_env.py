"""Offline, deterministic tests for the Surround environment.

Surround is an FFA "light-cycle" game with simultaneous moves. Players submit a
direction token (``up/down/left/right`` or w/a/s/d, brackets tolerated); an unparsable action
kills that player immediately. Ranking-based rewards span [-1, +1]. All spawns are
deterministic via ``seed=42``. We use a compact 5x5 board.
"""
import copy

import pytest

from textarena.envs.Surround.env import SurroundEnv


def _fresh(width=5, height=5, max_turns=100, num_players=2):
    env = SurroundEnv(width=width, height=height, max_turns=max_turns)
    env.reset(num_players=num_players, seed=42)
    return env


def test_reset_spawns_distinct_and_interior():
    env = _fresh()
    players = env.state.game_state["players"]
    assert set(players.keys()) == {0, 1}
    positions = [players[p].position for p in players]
    assert len(set(positions)) == len(positions)  # distinct spawns
    for (x, y) in positions:
        assert 0 <= x < env.width and 0 <= y < env.height
        assert all(players[p].alive for p in players)


def test_invalid_move_kills_and_ends_two_player_game():
    env = _fresh()
    done, _ = env.step("this is not a direction")
    assert done
    # The lone survivor (player 1) is ranked best (+1); the crasher worst (-1).
    assert env.state.rewards == {0: -1.0, 1: 1.0}


def test_valid_move_leaves_trail_and_moves_head():
    env = _fresh()
    players = env.state.game_state["players"]
    start0 = players[0].position
    start1 = players[1].position
    # Two "up" moves complete one simultaneous resolution.
    env.step("up")
    env.step("[up]")  # brackets tolerated
    board = env.state.game_state["board"]
    trails = sum(1 for row in board for cell in row if cell is not None)
    assert trails >= 2  # both heads left a trail behind
    assert players[0].position != start0
    assert players[1].position != start1


def test_turn_limit_results_in_draw():
    env = _fresh(max_turns=2)
    done = False
    for action in ["up", "up", "right", "right"]:
        done, _ = env.step(action)
        if done:
            break
    assert done
    assert env.state.game_state["round"] == 2
    # Both players still alive at the turn limit -> single ranking group -> all 0.
    assert env.state.rewards == {0: 0.0, 1: 0.0}


def test_board_too_small_raises():
    with pytest.raises(ValueError):
        SurroundEnv(width=2, height=2)
    with pytest.raises(ValueError):
        SurroundEnv(width=3, height=3)


def test_player_capacity_is_checked_against_interior_on_reset():
    env = SurroundEnv(width=5, height=5)
    with pytest.raises(ValueError):
        env.reset(num_players=10, seed=42)  # only nine interior cells

    env = SurroundEnv(width=10, height=10)
    env.reset(num_players=15, seed=42)
    assert len({player.position for player in env.game_state["players"].values()}) == 15


def test_head_on_collision_kills_both_and_keeps_old_heads_as_trails():
    env = _fresh()
    players = env.game_state["players"]
    players[0].position = (1, 2)
    players[1].position = (3, 2)
    env.game_state["board_state"] = env._ascii_board(env.game_state["board"], players)
    env.step("right")
    done, _ = env.step("left")
    assert done
    assert env.state.rewards == {0: 0.0, 1: 0.0}
    assert env.game_state["board"][2][1] == 0
    assert env.game_state["board"][2][3] == 1


def test_swapping_head_positions_is_a_collision_for_both():
    env = _fresh()
    players = env.game_state["players"]
    players[0].position = (1, 2)
    players[1].position = (2, 2)
    env.game_state["board_state"] = env._ascii_board(env.game_state["board"], players)
    env.step("right")
    done, _ = env.step("left")
    assert done
    assert not players[0].alive and not players[1].alive


def test_invalid_move_in_multiplayer_updates_board_immediately():
    env = _fresh(num_players=3)
    player = env.game_state["players"][0]
    old_position = player.position
    done, _ = env.step("not-a-direction")
    assert not done
    assert not player.alive
    x, y = old_position
    assert env.game_state["board"][y][x] == 0
    assert "0" not in env.game_state["board_state"]


def test_sealed_action_is_not_visible_to_next_player():
    env = _fresh()
    env.get_observation()  # consume Player 0's initial messages
    env.step("up")
    pid, observations = env.get_observation()
    assert pid == 1
    assert all(message.strip().lower() != "up" for _, message, _ in observations)


def test_get_board_str_and_snapshot_round_trip():
    env = _fresh()
    snapshot = env.snapshot()
    start_positions = {
        pid: player.position for pid, player in env.game_state["players"].items()
    }
    env.step("up")
    env.restore(snapshot)
    assert {
        pid: player.position for pid, player in env.game_state["players"].items()
    } == start_positions
    assert isinstance(env.get_board_str(), str)
    assert env.get_board_str() == env.game_state["board_state"]


def test_oversized_action_kills_once_and_does_not_stall_round():
    env = _fresh(num_players=3)
    players = env.game_state["players"]
    players[1].position = (1, 1)
    players[2].position = (3, 3)
    env.game_state["board_state"] = env._ascii_board(env.game_state["board"], players)

    oversized = "x" * (env.max_action_chars + 1)
    done, _ = env.step(oversized)
    assert not done
    assert env.state.eliminated == [0]
    assert not players[0].alive
    assert env.state.current_player_id == 1

    env.step("right")
    done, _ = env.step("left")
    assert not done
    assert env.game_state["round"] == 1
    assert env.game_state["pending_actions"] == {0: None, 1: None, 2: None}


def test_non_string_action_is_an_immediate_consistent_death():
    env = _fresh()
    done, _ = env.step(None)
    assert done
    assert env.state.eliminated == [0]
    assert not env.game_state["players"][0].alive
    assert env.state.rewards == {0: -1.0, 1: 1.0}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 5.5},
        {"height": "5"},
        {"max_turns": 0},
        {"max_turns": 1.5},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SurroundEnv(**kwargs)
