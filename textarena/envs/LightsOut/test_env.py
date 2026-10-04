"""Deterministic offline tests for Lights Out.

Single-player puzzle. The scramble is random, but the resulting board is always
solvable (it is produced by pressing cells). We read the grid from
``game_state`` and solve it with GF(2) linear algebra, then apply the presses to
reach the win state (reward 1.0).
"""
import copy

import pytest

from textarena.envs.LightsOut.env import LightsOutEnv


def _fresh(size=3):
    env = LightsOutEnv(size=size, max_turns=50)
    env.reset(num_players=1, seed=42)
    return env


def _solve(grid):
    """Return list of (row, col) presses that turn all lights off (GF(2))."""
    n = len(grid)
    N = n * n
    rows = []
    for r in range(n):
        for c in range(n):
            mask = 0
            for dr, dc in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < n and 0 <= nc < n:
                    mask |= 1 << (nr * n + nc)
            rhs = 1 if grid[r][c] else 0
            rows.append([mask, rhs])
    pivot_for = {}
    r = 0
    for col in range(N):
        piv = None
        for i in range(r, len(rows)):
            if (rows[i][0] >> col) & 1:
                piv = i
                break
        if piv is None:
            continue
        rows[r], rows[piv] = rows[piv], rows[r]
        for i in range(len(rows)):
            if i != r and ((rows[i][0] >> col) & 1):
                rows[i][0] ^= rows[r][0]
                rows[i][1] ^= rows[r][1]
        pivot_for[col] = r
        r += 1
    for mask, rhs in rows:
        if mask == 0 and rhs == 1:
            return None  # inconsistent (should not happen)
    x = [0] * N
    for col, ri in pivot_for.items():
        x[col] = rows[ri][1]
    return [(i // n, i % n) for i in range(N) if x[i]]


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.state.game_state["moves_made"] == 0
    assert env.state.game_state["solved"] is False


def test_solver_wins():
    env = _fresh(size=3)
    presses = _solve(env.state.game_state["grid"])
    assert presses is not None
    done = False
    for (r, c) in presses:
        assert done is False
        done, _ = env.step(f"{r} {c}")
    assert done is True
    assert env.state.rewards == {0: 1.0}
    assert env.state.game_state["solved"] is True
    assert env.state.turn == len(presses)
    assert env.state.game_info[0]["turn_count"] == len(presses)


def test_solver_wins_size5():
    env = _fresh(size=5)
    presses = _solve(env.state.game_state["grid"])
    assert presses is not None
    done = False
    for (r, c) in presses:
        assert done is False
        done, _ = env.step(f"{r} {c}")
    assert done is True
    assert env.state.rewards == {0: 1.0}


@pytest.mark.parametrize("size,example", [(1, "0 0"), (3, "2 2"), (5, "2 3")])
def test_prompt_example_is_on_the_board(size, example):
    env = LightsOutEnv(size=size, max_turns=20)
    env.reset(num_players=1, seed=0)
    assert f"e.g. '{example}'" in env.prompt(0)
    env.step(example)
    assert env.state.error_count == 0 and env.state.turn == 1


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("press 0 0")  # not a bare 'row col' action
    assert done is False
    assert env.state.error_count == 1


def test_out_of_bounds_rejected():
    env = _fresh(size=3)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("9 9")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_oversized_coordinate_is_rejected_without_integer_conversion():
    env = _fresh(size=3)
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(f"{'9' * 1000} 0")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_single_press_toggles_grid():
    env = _fresh(size=3)
    before = [row[:] for row in env.state.game_state["grid"]]
    env.step("1 1")  # center toggles itself + 4 neighbors
    after = env.state.game_state["grid"]
    changed = sum(before[r][c] != after[r][c] for r in range(3) for c in range(3))
    assert changed == 5
    assert env.state.game_state["moves_made"] == 1


@pytest.mark.parametrize("action", ["[0 0", "0 0]", "0 0 trailing", "00", "-1 0"])
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_comma_separated_coordinates_are_valid():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state["grid"])
    done, _ = env.step("1, 1")
    assert not done
    changed = sum(
        before[r][c] != env.state.game_state["grid"][r][c]
        for r in range(3)
        for c in range(3)
    )
    assert changed == 5


@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_many_seeded_resets_are_nontrivial_and_solvable(size):
    for seed in range(40):
        env = LightsOutEnv(size=size, max_turns=20)
        env.reset(num_players=1, seed=seed)
        grid = env.state.game_state["grid"]
        assert env.state.game_state["initial_on"] > 0
        assert not env._is_solved(grid)
        assert _solve(grid) is not None


def test_progress_is_bounded_when_a_move_increases_lit_cells():
    env = _fresh(size=3)
    env.state.game_state["grid"] = [
        [False, False, False],
        [False, True, False],
        [False, False, False],
    ]
    env.state.game_state["initial_on"] = 1
    env.step("1 1")
    assert env._get_percentage_completion() == 0.0


def test_render_and_renderer_follow_live_grid():
    env = _fresh(size=3)
    env.state.game_state["grid"] = [[False] * 3 for _ in range(3)]
    env.state.game_state["grid"][0][0] = True
    assert "0: O . ." in env.render(0)
    assert "███" in env.get_board_str()


def test_double_digit_board_labels_remain_aligned():
    env = LightsOutEnv(size=12, max_turns=50)
    env.reset(num_players=1, seed=42)
    grid = [[False] * 12 for _ in range(12)]
    text_lines = env._grid_to_string(grid).splitlines()
    assert text_lines[0] == "    " + " ".join(f"{i:>2}" for i in range(12))
    assert text_lines[11] == "10: " + " ".join(f"{'.':>2}" for _ in range(12))
    assert any(line.startswith("10 │") for line in env.get_board_str().splitlines())


def test_turn_limit_counts_final_press_and_reward_is_bounded():
    env = LightsOutEnv(size=3, max_turns=1)
    env.reset(num_players=1, seed=42)
    env.state.game_state["grid"] = [[True] * 3 for _ in range(3)]
    env.state.game_state["initial_on"] = 9
    done, _ = env.step("0 0")
    assert done
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1
    assert 0.0 <= env.state.rewards[0] <= 1.0
    assert "33.3%" in env.state.game_info[0]["reason"]
