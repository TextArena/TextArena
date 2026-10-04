"""Offline deterministic tests for the single-player Slitherlink environment.

The puzzle is generated from a random rectangular loop seeded by ``seed``. We
replicate that exact RNG sequence to recover the solution edges and script a
guaranteed win.
"""
import random

import pytest

from textarena.envs.Slitherlink.env import SlitherlinkEnv


def _fresh(rows=2, cols=2, **kwargs):
    env = SlitherlinkEnv(rows=rows, cols=cols, **kwargs)
    env.reset(num_players=1, seed=42)
    return env


def _solution_edges(rows, cols, seed):
    """Replicate SlitherlinkEnv._generate_random_loop for the given seed."""
    rng = random.Random(seed)
    min_size = 2
    max_width = min(cols, 4)
    max_height = min(rows, 4)
    width = rng.randint(min_size, max_width)
    height = rng.randint(min_size, max_height)
    start_r = rng.randint(0, rows - height)
    start_c = rng.randint(0, cols - width)

    h_edges, v_edges = set(), set()
    for c in range(start_c, start_c + width):
        h_edges.add((start_r, c))
        h_edges.add((start_r + height, c))
    for r in range(start_r, start_r + height):
        v_edges.add((r, start_c))
        v_edges.add((r, start_c + width))
    return h_edges, v_edges


def test_reset_initial_state():
    env = _fresh()
    assert env.state.num_players == 1
    assert not env.state.done
    assert len(env.clues) == 2 and len(env.clues[0]) == 2
    # No edges drawn yet.
    assert not env.h_edges and not env.v_edges


def test_drawing_the_solution_loop_wins():
    env = _fresh(rows=2, cols=2)
    # There must be at least one clue for the puzzle to be solvable.
    assert any(c is not None for row in env.clues for c in row)

    h_edges, v_edges = _solution_edges(2, 2, 42)
    actions = [f"h {r} {c}" for (r, c) in h_edges] + [f"v {r} {c}" for (r, c) in v_edges]
    done = False
    for a in actions:
        assert not done
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 1.0}


def test_toggle_edge_mutates_state():
    env = _fresh()
    env.step("h 0 0")
    assert (0, 0) in env.h_edges
    # Toggling again removes it.
    env.step("h 0 0")
    assert (0, 0) not in env.h_edges


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("toggle horizontal 0 0")
    assert not done
    assert env.state.error_count == 1


def test_edge_outside_board_is_rejected():
    env = _fresh(rows=2, cols=2)
    done, _ = env.step("h 9 9")
    assert not done
    assert env.state.error_count == 1


def test_repeated_invalid_move_yields_numeric_progress_reward():
    env = _fresh()
    env.step("garbage one")
    done, _ = env.step("garbage two")
    assert done
    assert isinstance(env.state.rewards[0], float)
    assert env.state.rewards[0] == pytest.approx(env._progress())


@pytest.mark.parametrize("seed", range(30))
def test_generated_solution_satisfies_every_clue_and_is_deterministic(seed):
    first = SlitherlinkEnv(rows=5, cols=6)
    second = SlitherlinkEnv(rows=5, cols=6)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert first.clues == second.clues
    assert (
        first.game_state["solution_h_edges"]
        == second.game_state["solution_h_edges"]
    )
    assert (
        first.game_state["solution_v_edges"]
        == second.game_state["solution_v_edges"]
    )
    first.h_edges.update(first.game_state["solution_h_edges"])
    first.v_edges.update(first.game_state["solution_v_edges"])
    assert first._progress() == 1.0
    assert first._is_solved()


@pytest.mark.parametrize("seed", range(100))
def test_small_generated_puzzles_always_have_at_least_one_clue(seed):
    env = SlitherlinkEnv(rows=2, cols=2)
    env.reset(num_players=1, seed=seed)
    assert any(clue is not None for row in env.clues for clue in row)


def test_reset_does_not_consume_global_rng():
    random.seed(73)
    expected = random.getstate()
    env = _fresh()
    assert random.getstate() == expected


@pytest.mark.parametrize(
    "action",
    ["h 0 0 extra", "[h 0 0", "h 0 0]", "h -1 0", "x 0 0", "", "h 0"],
)
def test_exact_parser_rejects_malformed_actions_atomically(action):
    env = _fresh()
    before_h = set(env.h_edges)
    before_v = set(env.v_edges)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.h_edges == before_h
    assert env.v_edges == before_v
    assert env.state.turn == 0


def test_edge_boundaries_accept_last_valid_and_reject_first_invalid():
    env = _fresh(rows=3, cols=4)
    env.step("h 3 3")
    env.step("v 2 4")
    assert (3, 3) in env.h_edges
    assert (2, 4) in env.v_edges
    before = (set(env.h_edges), set(env.v_edges))
    env.step("h 4 3")
    assert env.state.error_count == 1
    assert (env.h_edges, env.v_edges) == before


def test_oversized_numeric_action_is_invalid_without_edges():
    env = _fresh()
    done, _ = env.step(f"h {'9' * env.max_action_chars} 0")
    assert not done
    assert env.state.error_count == 1
    assert not env.h_edges and not env.v_edges


def test_disconnected_loops_do_not_solve_even_when_all_clues_match():
    env = _fresh(rows=4, cols=4)
    env.h_edges.update({(0, 0), (1, 0), (3, 3), (4, 3)})
    env.v_edges.update({(0, 0), (0, 1), (3, 3), (3, 4)})
    env.game_state["clues"] = [
        [env._cell_edge_count(r, c) for c in range(4)]
        for r in range(4)
    ]
    assert env._progress() == 1.0
    assert not env._is_solved()


def test_turn_limit_returns_current_clue_progress():
    env = _fresh(max_turns=1)
    done, _ = env.step("h 0 0")
    assert done
    assert env.state.rewards == {0: pytest.approx(env._progress())}
    assert "limit" in env.state.game_info[0]["reason"].lower()


def test_snapshot_restore_recovers_edge_set_aliases():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("h 0 0")
    assert (0, 0) in env.h_edges
    env.restore(snapshot)
    assert (0, 0) not in env.h_edges
    assert env.h_edges is env.game_state["h_edges"]


def test_current_and_terminal_render_show_edges_and_progress():
    env = _fresh()
    assert "Clues satisfied" in env.render(0)
    actions = [
        *(f"h {r} {c}" for r, c in env.game_state["solution_h_edges"]),
        *(f"v {r} {c}" for r, c in env.game_state["solution_v_edges"]),
    ]
    done = False
    for action in actions:
        done, _ = env.step(action)
    assert done
    terminal = env.render(0)
    assert "───" in terminal and "│" in terminal
    assert "100%" in terminal


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rows": 1},
        {"cols": 1},
        {"max_turns": 0},
        {"rows": True},
        {"rows": 101, "cols": 100},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SlitherlinkEnv(**kwargs)
