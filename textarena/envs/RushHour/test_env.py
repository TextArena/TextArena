"""Deterministic offline tests for the RushHour environment.

Puzzles are randomly generated, so win/blocked scenarios are scripted by editing
the vehicle layout directly after reset.
"""
from collections import deque
import random

import pytest

import textarena as ta
from textarena.envs.registration import ENV_REGISTRY
from textarena.envs.RushHour.env import RushHourEnv, _Vehicle

REGISTERED_IDS = sorted(
    env_id for env_id, spec in ENV_REGISTRY.items() if spec.entry_point == "textarena.envs.RushHour.env:RushHourEnv"
)


def _fresh(seed=42, **kwargs):
    env = RushHourEnv(**kwargs)
    env.reset(num_players=1, seed=seed)
    return env


def _start_from(env, *vehicles):
    """Replace the generated puzzle with a scripted layout that also counts as the starting position."""
    env.initial_layout = [vehicle.copy() for vehicle in vehicles]
    env.game_state["vehicles"] = {vehicle.vid: vehicle.copy() for vehicle in vehicles}


def _end_with_invalid_moves(env):
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    return env.state.rewards[0]


def test_scripted_win_drives_red_car_out():
    env = _fresh()
    # Place the red car one step from the exit with a clear path.
    x = _Vehicle("X", 2, 3, 2, True)
    env.state.game_state["vehicles"] = {"X": x}
    done, _ = env.step("X+")  # slides X to the exit edge
    assert not done
    done, _ = env.step("X+")  # crosses the board boundary
    assert done
    assert env.state.rewards == {0: 1.0}


def test_prompt_explains_directions_and_limit_as_the_rules_apply_them():
    env = _fresh(max_turns=40)
    prompt = env.prompt(0)
    assert "'+' moves a horizontal vehicle right or a vertical vehicle down; '-' moves it left or up." in prompt
    assert "You have 40 moves." in prompt
    env.state.game_state["vehicles"] = {
        "X": _Vehicle("X", 2, 1, 2, True),
        "A": _Vehicle("A", 0, 4, 2, False),
    }
    for action in ("A+", "X+", "A-", "X-"):
        done, _ = env.step(action)
        assert not done and env.state.error_count == 0
        if action == "A+":
            assert (env.game_state["vehicles"]["A"].row, env.game_state["vehicles"]["A"].col) == (1, 4)
        if action == "X+":
            assert env.game_state["vehicles"]["X"].col == 2
    assert _positions(env) == {"X": (2, 1, 2, True), "A": (0, 4, 2, False)}


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("move the red car")
    assert not done
    assert env.state.error_count == 1


def test_unknown_car_rejected():
    env = _fresh()
    # 'Z' matches the action regex but is never a real vehicle id.
    done, _ = env.step("Z+")
    assert not done
    assert env.state.error_count == 1


def test_blocked_move_rejected():
    env = _fresh()
    x = _Vehicle("X", 2, 0, 2, True)
    blocker = _Vehicle("A", 2, 2, 2, False)  # occupies (2,2), blocking X forward
    env.state.game_state["vehicles"] = {"X": x, "A": blocker}
    done, _ = env.step("X+")
    assert not done
    assert env.state.error_count == 1


def _positions(env):
    return {
        vid: (v.row, v.col, v.length, v.horizontal)
        for vid, v in env.game_state["vehicles"].items()
    }


def _solution(env, max_states=50000):
    start = {
        vid: vehicle.copy()
        for vid, vehicle in env.game_state["vehicles"].items()
    }
    queue = deque([(start, [])])
    seen = {env._get_state_hash(start)}
    while queue and len(seen) <= max_states:
        vehicles, path = queue.popleft()
        for vid, vehicle in vehicles.items():
            for forward, suffix in ((True, "+"), (False, "-")):
                if not env._can_move(vehicles, vehicle, forward):
                    continue
                nxt = {key: value.copy() for key, value in vehicles.items()}
                nxt[vid].move(forward)
                npath = path + [f"{vid}{suffix}"]
                if env._is_solved_state(nxt):
                    return npath
                key = env._get_state_hash(nxt)
                if key not in seen:
                    seen.add(key)
                    queue.append((nxt, npath))
    return None


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("seed", range(8))
def test_generated_puzzles_are_valid_solvable_and_deterministic(difficulty, seed):
    first = _fresh(seed=seed, difficulty=difficulty)
    second = _fresh(seed=seed, difficulty=difficulty)
    assert _positions(first) == _positions(second)
    assert not first._is_solved()
    assert _solution(first) is not None

    occupied = []
    for vehicle in first.game_state["vehicles"].values():
        assert all(
            0 <= r < first.BOARD_SIZE and 0 <= c < first.BOARD_SIZE
            for r, c in vehicle.cells()
        )
        occupied.extend(vehicle.cells())
    assert len(occupied) == len(set(occupied))


def test_generated_solution_can_be_executed_for_win():
    env = _fresh(seed=17, difficulty="hard")
    solution = _solution(env)
    assert solution
    done = False
    for action in solution:
        done, _ = env.step(action)
    assert done
    assert env.state.rewards == {0: 1.0}


def test_construction_and_reset_do_not_consume_global_rng():
    random.seed(90210)
    expected = random.getstate()
    _fresh(seed=3)
    assert random.getstate() == expected


def test_generation_is_solvable_by_construction_without_search(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("setup must not run exhaustive solvability search")

    monkeypatch.setattr(RushHourEnv, "_is_solvable", fail_if_called)
    env = _fresh(seed=99, difficulty="hard")
    assert not env._is_solved()
    assert _solution(env) is not None


@pytest.mark.parametrize(
    "action",
    ["X++", "X+ now", "[X+", "X+]", "XX+", "1+", ""],
)
def test_exact_parser_rejects_malformed_actions_atomically(action):
    env = _fresh()
    before = _positions(env)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert _positions(env) == before


def test_oversized_action_is_invalid_without_vehicle_mutation():
    env = _fresh()
    before = _positions(env)
    done, _ = env.step("X" * (env.MAX_ACTION_CHARS + 1))
    assert not done
    assert env.state.error_count == 1
    assert _positions(env) == before


def test_turn_limit_returns_partial_reward():
    env = _fresh(max_turns=1)
    _start_from(env, _Vehicle("X", 2, 0, 2, True))  # 5 moves from a solution
    done, _ = env.step("X+")  # 4 moves left
    assert done
    assert env.state.rewards == {0: pytest.approx(1 / 5)}
    assert "limit" in env.state.game_info[0]["reason"].lower()


@pytest.mark.parametrize("env_id", REGISTERED_IDS)
@pytest.mark.parametrize("seed", range(5))
def test_immediate_invalid_policy_scores_zero_on_registered_configs(env_id, seed):
    env = ta.make(env_id)
    env.reset(num_players=1, seed=seed)
    for _ in range(5):
        done, _ = env.step("@@@ not a move @@@")
        if done:
            break
    assert done
    assert env.close()[0] == {0: 0}


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
@pytest.mark.parametrize("seed", range(8))
def test_starting_position_scores_zero_even_with_the_red_car_near_the_exit(difficulty, seed):
    env = _fresh(seed=seed, difficulty=difficulty)
    assert _end_with_invalid_moves(env) == 0


def test_partial_progress_counts_moves_cut_from_the_optimal_solution():
    env = _fresh(seed=7)
    solution = _solution(env)
    assert len(solution) >= 4
    for action in solution[:3]:
        done, _ = env.step(action)
        assert not done
    assert _end_with_invalid_moves(env) == pytest.approx(3 / len(solution))


def test_moving_back_and_forth_or_away_from_the_exit_earns_nothing():
    env = _fresh()
    _start_from(env, _Vehicle("X", 2, 2, 2, True), _Vehicle("A", 0, 0, 2, False))  # 3 moves from a solution
    for action in ("A+", "A-", "X+", "X-", "X-", "A+"):  # ends with X one square further from the exit
        done, _ = env.step(action)
        assert not done
    assert _end_with_invalid_moves(env) == 0


def test_partial_credit_follows_the_solver_not_the_red_car_column():
    env = _fresh()
    # X is one square from the exit, but truck B blocks it and must drive down three squares first: 5 moves.
    _start_from(env, _Vehicle("X", 2, 3, 2, True), _Vehicle("B", 0, 5, 3, False))
    assert env._moves_to_solve(env.game_state["vehicles"]) == 5
    env.step("X-")  # 6 moves left
    env.step("X+")  # back to 5
    env.step("B+")  # 4
    env.step("B+")  # 3
    assert _end_with_invalid_moves(env) == pytest.approx(2 / 5)


def test_solver_distance_is_exact_and_respects_the_move_limit():
    env = _fresh()
    layout = {"X": _Vehicle("X", 2, 0, 2, True)}
    assert env._moves_to_solve(layout) == 5
    assert env._moves_to_solve(layout, max_moves=5) == 5
    assert env._moves_to_solve(layout, max_moves=4) is None
    assert env._moves_to_solve({"X": _Vehicle("X", 2, 5, 2, True)}) == 0


def test_snapshot_restore_recovers_vehicle_objects_and_render():
    env = _fresh()
    env.game_state["vehicles"] = {"X": _Vehicle("X", 2, 0, 2, True)}
    snapshot = env.snapshot()
    env.step("X+")
    assert env.game_state["vehicles"]["X"].col == 1
    env.restore(snapshot)
    assert env.game_state["vehicles"]["X"].col == 0
    assert ">" in env.render(0)


def test_terminal_render_shows_red_car_crossing_exit():
    env = _fresh()
    env.game_state["vehicles"] = {"X": _Vehicle("X", 2, 4, 2, True)}
    done, _ = env.step("X+")
    assert done
    terminal_board = env.render(0)
    assert "X" in terminal_board and ">" in terminal_board


@pytest.mark.parametrize(
    "kwargs",
    [{"difficulty": "impossible"}, {"max_turns": 0}, {"max_turns": True}],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        RushHourEnv(**kwargs)
