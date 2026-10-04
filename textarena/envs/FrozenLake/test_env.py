"""Deterministic game-logic tests for FrozenLake (single player).

The hole layout is random per seed, so we read the grid from
``env.state.game_state`` and BFS a guaranteed-safe path to the goal.
"""
from collections import deque

import pytest

from textarena.envs.FrozenLake.env import FrozenLakeEnv


def _fresh(size=4, num_holes=3, **kwargs):
    env = FrozenLakeEnv(size=size, num_holes=num_holes, **kwargs)
    env.reset(num_players=1, seed=42)
    return env


def _safe_path(grid, start, goal, size):
    dirs = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    queue = deque([(start, [])])
    seen = {start}
    while queue:
        (r, c), path = queue.popleft()
        if (r, c) == goal:
            return path
        for name, (dr, dc) in dirs.items():
            nr, nc = r + dr, c + dc
            if 0 <= nr < size and 0 <= nc < size and (nr, nc) not in seen and grid[nr][nc] != "H":
                seen.add((nr, nc))
                queue.append(((nr, nc), path + [name]))
    return None


def test_reaching_goal_wins():
    env = _fresh()
    gs = env.state.game_state
    path = _safe_path(gs["grid"], gs["player_pos"], gs["goal_pos"], env.size)
    assert path is not None, "expected a solvable grid"
    done = False
    for move in path:
        done, _ = env.step(move)
    assert done and env.state.rewards == {0: 1.0}


def test_falling_into_hole_ends_game():
    env = _fresh()
    # Stage a hole directly to the right of the start for a deterministic loss.
    env.state.game_state["grid"][0][1] = "H"
    done, _ = env.step("right")
    assert done and env.state.rewards[0] < 1.0


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no direction here")
    assert not done and env.state.error_count == 1


def test_walking_into_wall_rejected():
    env = _fresh()
    # Start is the top-left corner; moving up steps off the board.
    done, _ = env.step("up")
    assert not done and env.state.error_count == 1


def test_wasd_alias_moves_player():
    env = _fresh()
    gs = env.state.game_state
    # Pick any safe neighbour of the start and move there via its WASD alias.
    aliases = {"s": (1, 0), "d": (0, 1)}  # down, right (both stay in bounds from (0,0))
    for key, (dr, dc) in aliases.items():
        nr, nc = dr, dc
        if gs["grid"][nr][nc] != "H":
            start = gs["player_pos"]
            done, _ = env.step(key)
            assert not done and gs["player_pos"] == (nr, nc) and gs["player_pos"] != start
            return
    raise AssertionError("expected at least one safe neighbour of the start")


@pytest.mark.parametrize("seed", range(30))
def test_generated_grids_have_exact_hole_count_and_safe_path(seed):
    env = FrozenLakeEnv(size=5, num_holes=6, randomize_start_goal=True)
    env.reset(num_players=1, seed=seed)
    gs = env.game_state
    assert sum(cell == "H" for row in gs["grid"] for cell in row) == 6
    assert gs["grid"][gs["start_pos"][0]][gs["start_pos"][1]] != "H"
    assert gs["grid"][gs["goal_pos"][0]][gs["goal_pos"][1]] == "G"
    assert _safe_path(gs["grid"], gs["start_pos"], gs["goal_pos"], env.size) is not None


@pytest.mark.parametrize("seed", range(20))
def test_max_density_generation_is_direct_exact_and_solvable(seed, capsys):
    env = FrozenLakeEnv(size=10, num_holes=81, randomize_start_goal=True)
    env.reset(num_players=1, seed=seed)
    gs = env.game_state
    assert sum(cell == "H" for row in gs["grid"] for cell in row) == 81
    assert _safe_path(gs["grid"], gs["start_pos"], gs["goal_pos"], env.size)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    "action",
    ["right now", "[right", "right]", "right,down", "9", ""],
)
def test_parser_rejects_malformed_input_without_moving(action):
    env = _fresh(num_holes=0)
    before = env.game_state["player_pos"]
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["player_pos"] == before
    assert env.state.turn == 0


def test_randomized_prompt_names_actual_endpoints():
    env = _fresh(num_holes=0, randomize_start_goal=True)
    assert str(env.game_state["start_pos"]) in env.prompt(0)
    assert str(env.game_state["goal_pos"]) in env.prompt(0)


def test_turn_limit_uses_closeness_and_counts_only_valid_moves():
    env = _fresh(num_holes=0, max_turns=6)
    for move in ["right", "left"] * 2 + ["up", "right"]:  # 'up' hits the wall and does not count
        done, _ = env.step(move)
        assert not done
    done, _ = env.step("left")
    assert done
    assert env.state.turn == 6
    assert env.state.rewards == {0: 0.0}
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


def test_prompt_states_coordinates_walls_and_move_limit():
    prompt = _fresh(max_turns=40).prompt(0)
    assert "goal at (3, 3) (row, column)" in prompt
    assert "moving off the grid is an invalid move" in prompt
    assert "You have 40 moves." in prompt


def test_hole_loss_is_terminal_and_render_identifies_hole():
    env = _fresh(num_holes=0)
    env.game_state["grid"][0][1] = "H"
    done, _ = env.step("right")
    assert done
    assert 0.0 <= env.state.rewards[0] < 1.0
    assert "P/H" in env.render(0)


def test_render_does_not_alias_or_mutate_grid():
    env = _fresh(num_holes=0)
    before = [row[:] for row in env.game_state["grid"]]
    assert "Current Board" in env.render(0)
    assert env.game_state["grid"] == before


def test_oversized_action_is_invalid_without_moving():
    env = _fresh(num_holes=0)
    before = env.game_state["player_pos"]
    done, _ = env.step("x" * (env.max_action_chars + 1))
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["player_pos"] == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"size": 4, "num_holes": 10},
        {"size": 4, "max_turns": 5},
        {"size": 60},  # the default 100 moves cannot cover the 118-step shortest path
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        FrozenLakeEnv(**kwargs)
