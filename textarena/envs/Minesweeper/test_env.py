"""Deterministic offline tests for the Minesweeper environment.

Because mine placement is random and only happens on the first move, several tests
script the internal grid directly (after reset) to obtain guaranteed outcomes.
"""
import copy
import random
import re

import pytest

from textarena.envs.Minesweeper.env import MinesweeperEnv


def _fresh(rows=8, cols=8, num_mines=10, **kwargs):
    env = MinesweeperEnv(
        rows=rows,
        cols=cols,
        num_mines=num_mines,
        **kwargs,
    )
    env.reset(num_players=1, seed=42)
    return env


def _scripted(env):
    """Install a tiny, fully-known 1x3 board: mine, adjacent-1, safe-0."""
    env.grid = [[-1, 1, 0]]
    env.rows, env.cols = 1, 3
    env.first_move = False
    env.revealed = [[False, False, False]]
    env.flags = [[False, False, False]]
    env.initial_move_pos = (0, 2)
    return env


def test_reset_initializes_board():
    env = _fresh(rows=5, cols=5, num_mines=4)
    assert len(env.revealed) == 5 and len(env.revealed[0]) == 5
    assert all(not env.revealed[r][c] for r in range(5) for c in range(5))
    assert env.first_move is True


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("reveal 0 0")
    assert not done
    assert env.state.error_count == 1


def test_out_of_bounds_rejected():
    env = _fresh(rows=4, cols=4, num_mines=2)
    done, _ = env.step("99 99")
    assert not done
    assert env.state.error_count == 1


def test_scripted_win_reveals_all_safe_cells():
    env = _scripted(_fresh(rows=2, cols=3, num_mines=0))
    done, _ = env.step("0 2")  # flood-fill reveals (0,2) then (0,1)
    assert done
    assert env.state.rewards == {0: 1}
    assert env.revealed == [[False, True, True]]


def test_hitting_mine_is_terminal_loss():
    env = _scripted(_fresh(rows=2, cols=3, num_mines=0))
    done, _ = env.step("0 0")  # (0,0) is the mine
    assert done
    assert env.state.error_count == 0
    assert env.state.rewards == {0: 0.0}
    assert "*" in env.render(0)


def test_already_revealed_cell_rejected():
    env = _fresh(rows=4, cols=4, num_mines=2)
    env.revealed[0][0] = True
    done, _ = env.step("0 0")
    assert not done
    assert env.state.error_count == 1


def test_first_move_is_always_safe():
    env = _fresh(rows=5, cols=5, num_mines=3)
    done, _ = env.step("2 2")
    assert not done  # first move can never detonate a mine
    assert env.grid[2][2] != -1


@pytest.mark.parametrize("seed", range(30))
def test_mine_generation_is_exact_safe_and_seeded(seed):
    first = _fresh(rows=6, cols=7, num_mines=8)
    second = _fresh(rows=6, cols=7, num_mines=8)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    first.step("3 3")
    second.step("3 3")
    assert first.grid == second.grid
    mines = {
        (r, c)
        for r in range(first.rows)
        for c in range(first.cols)
        if first.grid[r][c] == -1
    }
    assert len(mines) == 8
    assert all(not (2 <= r <= 4 and 2 <= c <= 4) for r, c in mines)


def test_reset_and_first_move_do_not_consume_global_rng():
    random.seed(1001)
    expected = random.getstate()
    env = _fresh(rows=5, cols=5, num_mines=4)
    env.step("2 2")
    assert random.getstate() == expected


@pytest.mark.parametrize(
    "action",
    ["0 0 extra", "[0 0", "0 0]", "0,,0", "-1 0", "reveal 0 0", ""],
)
def test_exact_parser_rejects_malformed_coordinates_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before
    assert env.state.turn == 0


def test_comma_and_space_separated_coordinates_are_equivalent():
    comma = _fresh(rows=5, cols=5, num_mines=3)
    space = _fresh(rows=5, cols=5, num_mines=3)
    comma.step("2, 2")
    space.step("2 2")
    assert comma.grid == space.grid
    assert comma.revealed == space.revealed


def test_oversized_numeric_action_is_invalid_without_first_move_setup():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(f"{'9' * env.max_action_chars} 0")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before


def test_zero_mine_board_wins_on_first_reveal():
    env = _fresh(rows=3, cols=3, num_mines=0)
    done, _ = env.step("1 1")
    assert done
    assert env.state.rewards == {0: 1}
    assert all(all(row) for row in env.revealed)


def test_turn_limit_returns_safe_cell_completion():
    env = _fresh(rows=4, cols=4, num_mines=1, max_turns=1)
    env.first_move = False
    env.initial_move_pos = (0, 0)
    env.grid = [
        [-1, 1, 0, 0],
        [1, 1, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    env.revealed = [[False] * 4 for _ in range(4)]
    env.flags = [[False] * 4 for _ in range(4)]
    done, _ = env.step("0 1")
    assert done
    assert 0.0 <= env.state.rewards[0] < 1.0
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


def test_completion_reuses_cached_initial_flood_fill(monkeypatch):
    env = _fresh(rows=8, cols=8, num_mines=10)
    env.step("4 4")
    assert env.game_state["initial_revealed"] is not None

    def fail_if_recomputed(*args, **kwargs):
        raise AssertionError("initial flood fill should be cached")

    monkeypatch.setattr(env, "_initial_reveal_mask", fail_if_recomputed)
    assert 0.0 <= env._get_percentage_completion() <= 1.0


def test_snapshot_restore_recovers_grid_backed_aliases():
    env = _fresh(rows=5, cols=5, num_mines=3)
    snapshot = env.snapshot()
    env.step("2 2")
    assert not env.first_move
    env.restore(snapshot)
    assert env.first_move
    assert env.grid is env.game_state["grid"]
    assert env.revealed is env.game_state["revealed"]


@pytest.mark.parametrize("rows,cols,num_mines", [(5, 5, 5), (8, 8, 10), (10, 10, 20), (12, 12, 30)])
def test_prompt_examples_fit_the_board_and_state_the_mine_count(rows, cols, num_mines):
    env = _fresh(rows=rows, cols=cols, num_mines=num_mines)
    _, observation = env.get_observation()
    prompt = observation[0][1]
    examples = re.findall(r"'(\d+) (\d+)'", prompt)
    assert examples
    assert all(int(r) < rows and int(c) < cols for r, c in examples)
    assert f"{num_mines} hidden mines" in prompt
    assert f"{env.max_turns} turns" in prompt
    done, _ = env.step(" ".join(examples[0]))
    assert env.state.error_count == 0 and env.state.turn == 1


def test_renderer_honors_flags_and_multi_digit_coordinates():
    env = _fresh(rows=5, cols=12, num_mines=3)
    env.flags[0][11] = True
    rendered = env.render(0)
    assert "11" in rendered
    assert "F" in rendered
    assert env.get_board_str() in rendered


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rows": 0},
        {"cols": 0},
        {"num_mines": -1},
        {"rows": 3, "cols": 3, "num_mines": 1},
        {"rows": 4, "cols": 4, "num_mines": 8},
        {"max_turns": 0},
        {"rows": 101, "cols": 100},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        MinesweeperEnv(**kwargs)
