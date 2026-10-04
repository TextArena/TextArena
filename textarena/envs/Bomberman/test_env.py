"""Deterministic tests for two-player Bomberman.

Players alternate single moves (Player 0 first) with the bare commands 'up',
'down', 'left', 'right', 'stay' and 'bomb'. Positions are (x, y) with y growing
downward. Most rule tests replace the generated terrain with an open arena so
positions, walls and blasts can be set up exactly.
"""
import copy
import random

import pytest

import textarena as ta
from textarena.envs.Bomberman.env import TwoPlayerBombermanEnv


def _fresh(seed=42, **kwargs):
    env = TwoPlayerBombermanEnv(**kwargs)
    env.reset(num_players=2, seed=seed)
    return env


def _arena(env, p0, p1, walls=(), pillars=()):
    """Outer wall only, players at p0/p1, plus optional destructible walls and pillars."""
    n = env.grid_size
    grid = [["#" if x in (0, n - 1) or y in (0, n - 1) else "." for x in range(n)] for y in range(n)]
    for x, y in walls:
        grid[y][x] = "+"
    for x, y in pillars:
        grid[y][x] = "#"
    gs = env.game_state
    gs["grid"] = grid
    gs["positions"] = [p0, p1]
    return gs


def _play(env, *actions):
    """Play valid actions in order and return whether the game is done."""
    done = False
    for action in actions:
        assert not done, f"game ended before {action!r}"
        done, _ = env.step(action)
        assert env.state.error_count == 0, f"{action!r} was rejected"
    return done


def _blast_cells(gs):
    return {(x, y) for x, y, _ in gs["blasts"]}


# ---------------------------------------------------------------- arena setup
def test_reset_initial_state():
    env = _fresh()
    gs = env.game_state
    assert gs["positions"] == [(1, 1), (8, 8)]
    assert gs["alive"] == [True, True]
    assert gs["bombs"] == [] and gs["blasts"] == []
    assert env.state.current_player_id == 0
    assert env.state.max_turns == 200  # 100 rounds of two alternating moves
    n = env.grid_size
    assert all(gs["grid"][0][i] == gs["grid"][n - 1][i] == gs["grid"][i][0] == gs["grid"][i][n - 1] == "#" for i in range(n))


@pytest.mark.parametrize("grid_size", [5, 6, 9, 10, 11, 12])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_arena_is_point_symmetric_and_spawns_are_open(grid_size, seed):
    env = _fresh(seed=seed, grid_size=grid_size)
    grid = env.game_state["grid"]
    n = grid_size
    assert all(grid[y][x] == grid[n - 1 - y][n - 1 - x] for y in range(n) for x in range(n))
    for sx, sy in [(1, 1), (n - 2, n - 2)]:
        assert grid[sy][sx] == "."
        assert all(grid[y][x] != "+" for y in range(sy - 1, sy + 2) for x in range(sx - 1, sx + 2))
    # each spawn has its two neighbours along the outer corridor free
    assert grid[1][2] == grid[2][1] == grid[n - 2][n - 3] == grid[n - 3][n - 2] == "."


def test_pillar_lattice_matches_classic_layout_for_odd_sizes():
    env = _fresh(grid_size=11, wall_density=0.0)
    grid = env.game_state["grid"]
    pillars = {(x, y) for y in range(1, 10) for x in range(1, 10) if grid[y][x] == "#"}
    assert pillars == {(x, y) for y in range(2, 10, 2) for x in range(2, 10, 2)}


def test_pillar_lattice_stays_symmetric_for_even_sizes():
    env = _fresh(grid_size=10, wall_density=0.0)
    grid = env.game_state["grid"]
    pillars = {(x, y) for y in range(1, 9) for x in range(1, 9) if grid[y][x] == "#"}
    # pillars sit at an even distance from the nearest outer wall: columns/rows 2, 4, 5 and 7
    assert pillars == {(x, y) for y in (2, 4, 5, 7) for x in (2, 4, 5, 7)}
    assert grid[8][8] == "." and grid[7][7] == "#" and grid[2][2] == "#"


def test_wall_density_extremes():
    empty = _fresh(wall_density=0)
    assert not any(cell == "+" for row in empty.game_state["grid"] for cell in row)

    full = _fresh(wall_density=1)
    grid = full.game_state["grid"]
    pockets = {(x, y) for sx, sy in [(1, 1), (8, 8)] for x in range(sx - 1, sx + 2) for y in range(sy - 1, sy + 2)}
    for y in range(1, 9):
        for x in range(1, 9):
            if (x, y) in pockets:
                assert grid[y][x] in (".", "#")
            elif not full._is_indestructible(x, y):
                assert grid[y][x] == "+"


def test_arena_is_seeded():
    assert _fresh(seed=5).game_state["grid"] == _fresh(seed=5).game_state["grid"]
    assert _fresh(seed=5).game_state["grid"] != _fresh(seed=6).game_state["grid"]


# --------------------------------------------------------------------- moves
def test_valid_move_updates_position_and_passes_turn():
    env = _fresh()
    gs = _arena(env, (3, 3), (6, 6))
    assert not _play(env, "right")
    assert gs["positions"][0] == (4, 3)
    assert env.state.current_player_id == 1
    assert not _play(env, "up")
    assert gs["positions"][1] == (6, 5)
    assert env.state.current_player_id == 0


@pytest.mark.parametrize(
    "setup, action",
    [
        ({"pillars": [(4, 3)]}, "right"),
        ({"walls": [(4, 3)]}, "right"),
        ({}, "down"),        # the other player stands on (3, 4)
        ({}, "left"),        # a bomb lies on (2, 3)
    ],
)
def test_blocked_moves_are_invalid_and_atomic(setup, action):
    env = _fresh()
    gs = _arena(env, (3, 3), (3, 4), **setup)
    gs["bombs"].append({"x": 2, "y": 3, "timer": 3, "owner": 1})
    before = copy.deepcopy(gs)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert gs == before  # nothing moved and the bomb did not tick


def test_outer_wall_blocks_moves_from_spawn():
    env = _fresh()
    done, _ = env.step("up")
    assert not done and env.state.error_count == 1
    assert env.game_state["positions"][0] == (1, 1)


def test_second_bomb_on_same_cell_is_invalid():
    env = _fresh()
    gs = _arena(env, (3, 3), (6, 6))
    _play(env, "bomb", "stay")
    done, _ = env.step("bomb")
    assert not done and env.state.error_count == 1
    assert len(gs["bombs"]) == 1


def test_player_can_walk_off_own_bomb_but_nobody_can_step_onto_it():
    env = _fresh()
    gs = _arena(env, (3, 3), (5, 3))
    _play(env, "bomb", "left", "up")  # P0 drops a bomb and walks off it; P1 comes next to it
    assert gs["positions"] == [(3, 2), (4, 3)]
    done, _ = env.step("left")  # P1 tries to step onto the bomb
    assert not done and env.state.error_count == 1
    assert gs["positions"][1] == (4, 3)


# ----------------------------------------------------------------- explosions
def test_bomb_fuse_counts_both_players_moves():
    env = _fresh()  # bomb_timer=6, bomb_radius=2
    gs = _arena(env, (2, 2), (7, 7))
    _play(env, "bomb")  # move 1
    assert gs["bombs"] == [{"x": 2, "y": 2, "timer": 5, "owner": 0}]
    _play(env, "stay", "right", "stay", "down")  # moves 2-5; Player 0 ends on (3, 3), outside the cross
    assert gs["bombs"][0]["timer"] == 1
    assert not _play(env, "stay")  # move 6: the bomb goes off at the end of it
    assert gs["bombs"] == []
    assert gs["alive"] == [True, True]
    assert _blast_cells(gs) == {(2, 2), (1, 2), (3, 2), (4, 2), (2, 1), (2, 3), (2, 4)}


def test_placer_cannot_outrun_blast_in_a_straight_line():
    env = _fresh()
    gs = _arena(env, (2, 2), (7, 7))
    done = _play(env, "bomb", "stay", "right", "stay", "right", "stay")
    assert done
    assert gs["positions"][0] == (4, 2)
    assert gs["alive"] == [False, True]
    assert env.state.rewards == {0: -1, 1: 1}


def test_opponent_caught_in_blast_loses():
    env = _fresh()
    gs = _arena(env, (2, 2), (2, 4))
    done = _play(env, "bomb", "stay", "right", "stay", "down", "stay")
    assert done
    assert gs["alive"] == [True, False]
    assert env.state.rewards == {0: 1, 1: -1}
    assert "Player 0 wins" in env.state.game_info[0]["reason"]


def test_both_players_caught_is_a_draw():
    env = _fresh()
    gs = _arena(env, (2, 2), (4, 2))
    done = _play(env, "bomb", "stay", "stay", "stay", "stay", "stay")
    assert done
    assert gs["alive"] == [False, False]
    assert env.state.rewards == {0: 0, 1: 0}


def test_walls_stop_blasts_and_destructible_walls_break():
    env = _fresh()
    gs = _arena(env, (2, 2), (4, 2), walls=[(2, 3)], pillars=[(3, 2)])
    done = _play(env, "bomb", "stay", "left", "stay", "up", "stay")
    assert not done
    assert gs["alive"] == [True, True]  # Player 1 is shielded by the pillar
    assert gs["grid"][3][2] == "."      # the destructible wall was destroyed ...
    assert gs["grid"][2][3] == "#"      # ... but the pillar was not
    assert _blast_cells(gs) == {(2, 2), (1, 2), (2, 1), (2, 3)}  # neither wall let the blast through


def test_blast_passes_over_another_bomb_without_detonating_it():
    env = _fresh()
    gs = _arena(env, (6, 6), (7, 7))
    gs["bombs"] = [{"x": 2, "y": 2, "timer": 1, "owner": 0}, {"x": 3, "y": 2, "timer": 3, "owner": 1}]
    _play(env, "stay")
    assert gs["bombs"] == [{"x": 3, "y": 2, "timer": 2, "owner": 1}]
    assert {(3, 2), (4, 2)} <= _blast_cells(gs)  # the blast continued past the bomb
    board_rows = env.get_board_str().splitlines()
    assert board_rows[1 + 2].split()[1 + 3] == "B"  # the bomb is drawn over the blast marker
    assert board_rows[1 + 2].split()[1 + 4] == "*"


@pytest.mark.parametrize("reverse", [False, True])
def test_simultaneous_explosions_use_walls_from_before_the_tick(reverse):
    env = _fresh()
    gs = _arena(env, (2, 2), (7, 7), walls=[(3, 2)])
    bombs = [{"x": 3, "y": 4, "timer": 1, "owner": 1}, {"x": 4, "y": 2, "timer": 1, "owner": 1}]
    gs["bombs"] = list(reversed(bombs)) if reverse else bombs
    # The first bomb breaks the wall at (3, 2); the second bomb's blast must
    # still stop there instead of reaching Player 0 on (2, 2).
    assert not _play(env, "stay")
    assert gs["alive"] == [True, True]
    assert gs["grid"][2][3] == "."
    assert (2, 2) not in _blast_cells(gs)
    assert (3, 2) in _blast_cells(gs)


def test_blast_markers_are_shown_to_both_players_then_expire():
    env = _fresh()
    gs = _arena(env, (6, 6), (7, 7))
    gs["bombs"] = [{"x": 2, "y": 2, "timer": 1, "owner": 0}]
    _play(env, "stay")  # explodes at the end of Player 0's move
    assert "*" in env.render(1)
    _play(env, "stay")
    assert "*" in env.render(0)
    _play(env, "stay")
    assert gs["blasts"] == []
    assert "*" not in env.get_board_str()


def test_blast_markers_are_harmless_to_walk_through():
    env = _fresh()
    gs = _arena(env, (5, 2), (7, 7))
    gs["bombs"] = [{"x": 2, "y": 2, "timer": 1, "owner": 1}]
    _play(env, "stay")
    assert (4, 2) in _blast_cells(gs)
    assert not _play(env, "stay", "left")
    assert gs["positions"][0] == (4, 2)
    assert gs["alive"] == [True, True]


# --------------------------------------------------------------- turn limits
def test_round_limit_is_a_draw_after_both_players_move():
    env = _fresh(max_turns=1)
    assert not _play(env, "right")
    assert _play(env, "up")
    assert env.state.rewards == {0: 0, 1: 0}
    assert "round limit (1)" in env.state.game_info[0]["reason"]


def test_explosion_on_the_final_move_beats_the_round_limit():
    env = _fresh(max_turns=2, bomb_timer=4)
    gs = _arena(env, (2, 2), (7, 7))
    done = _play(env, "bomb", "stay", "right", "stay")  # move 4 is both the fuse end and the round limit
    assert done
    assert gs["alive"] == [False, True]
    assert env.state.rewards == {0: -1, 1: 1}


def test_round_counter_in_render():
    env = _fresh()
    _arena(env, (3, 3), (6, 6))
    assert env.render(0).startswith("Round 1/100: Player 0 to move.")
    _play(env, "stay")
    assert env.render(1).startswith("Round 1/100: Player 1 to move.")
    _play(env, "stay")
    assert env.render(0).startswith("Round 2/100: Player 0 to move.")


# ------------------------------------------------------------ action parsing
def test_commands_tolerate_case_whitespace_and_brackets():
    env = _fresh()
    gs = _arena(env, (3, 3), (6, 6))
    _play(env, "  Right ", "[stay]", "BOMB")
    assert gs["positions"] == [(4, 3), (6, 6)]
    assert gs["bombs"][0]["owner"] == 0


@pytest.mark.parametrize("action", ["move up", "up down", "upward", "", "<action>up</action>", "[[up]]", "up!"])
def test_non_bare_commands_are_rejected(action):
    env = _fresh()
    gs = _arena(env, (3, 3), (6, 6))
    before = copy.deepcopy(gs)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert gs == before


def test_two_consecutive_invalid_moves_lose():
    env = _fresh()
    env.step("jump")
    done, _ = env.step("fly")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.game_info[0]["invalid_move"]


def test_oversized_action_is_rejected_without_side_effects():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("u" * (env.max_action_chars + 1))
    assert not done and env.state.error_count == 1
    assert env.game_state == before


# --------------------------------------------------------- rendering & prompt
def test_board_string_is_consistent_with_state():
    env = _fresh()
    _arena(env, (3, 3), (6, 6), walls=[(5, 2), (2, 7)], pillars=[(4, 4)])
    _play(env, "bomb")
    board = env.get_board_str()
    assert board in env.render(1)
    rows = board.splitlines()
    assert rows[0].split() == [str(i) for i in range(10)]
    cells = {(x, y): rows[1 + y].split()[1 + x] for y in range(10) for x in range(10)}
    assert cells[(3, 3)] == "0"  # the player is drawn over their own bomb ...
    assert "Bombs: (3, 3) explodes after 5 more moves" in board  # ... which is still listed
    assert "Players: Player 0 at (3, 3); Player 1 at (6, 6)" in board
    assert cells[(6, 6)] == "1"
    assert {cell for cell, glyph in cells.items() if glyph == "+"} == {(5, 2), (2, 7)}
    assert cells[(4, 4)] == cells[(0, 5)] == "#"
    assert sum(glyph == "." for glyph in cells.values()) == 8 * 8 - 5


def test_final_board_hides_eliminated_player():
    env = _fresh()
    gs = _arena(env, (2, 2), (2, 4))
    _play(env, "bomb", "stay", "right", "stay", "down", "stay")
    final = env.render(0)
    assert final.startswith("Final board:")
    assert "Player 1 at (2, 4) (eliminated)" in final
    assert final.splitlines()[2 + 4].split()[1 + 2] == "*"


def test_prompt_teaches_bare_commands_and_exact_fuse():
    env = _fresh()
    prompt = env.prompt(0)
    assert "'left' or 'bomb'" in prompt
    assert "[" not in prompt and "]" not in prompt
    assert "you get 2 more move(s)" in prompt and "your opponent gets 3" in prompt
    assert "100 rounds" in prompt
    assert "6-move fuse" in _fresh(bomb_timer=6).prompt(1)
    assert "you get 3 more move(s)" in _fresh(bomb_timer=7).prompt(1)


def test_initial_observation_contains_prompt_and_board():
    env = _fresh()
    pid, observation = env.get_observation()
    assert pid == 0
    kinds = [kind for _, _, kind in observation]
    assert kinds == [ta.ObservationType.PROMPT, ta.ObservationType.GAME_BOARD]


# ------------------------------------------------------- snapshots & config
def test_snapshot_restore_replays_identically():
    env = _fresh(seed=9)
    snapshot = env.snapshot()
    actions = ["right", "up", "bomb", "left", "left", "stay", "stay", "stay"]

    def run():
        for action in actions:
            if env.state.done:
                break
            env.step(action)
        return copy.deepcopy(env.game_state), env.state.rewards, env.state.turn

    first = run()
    env.restore(snapshot)
    assert run() == first


@pytest.mark.parametrize(
    "kwargs",
    [
        {"grid_size": 4},
        {"grid_size": 10.0},
        {"grid_size": True},
        {"max_turns": 0},
        {"max_turns": 2.5},
        {"bomb_timer": 0},
        {"bomb_radius": 0},
        {"bomb_radius": "2"},
        {"wall_density": -0.1},
        {"wall_density": 1.5},
        {"wall_density": "0.3"},
        {"wall_density": True},
        {"wall_density": float("nan")},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        TwoPlayerBombermanEnv(**kwargs)


def test_registered_variants_use_upstream_defaults():
    for env_id in ("Bomberman-v0", "Bomberman-v0-mdp"):
        env = ta.make(env_id)
        env.reset(num_players=2, seed=1)
        assert (env.grid_size, env.max_turns, env.bomb_timer, env.bomb_radius) == (10, 100, 6, 2)
        done, _ = env.step("right")
        assert not done and env.state.error_count == 0


# ------------------------------------------------------------- random play
def _legal_commands(env):
    pid = env.state.current_player_id
    x, y = env.game_state["positions"][pid]
    legal = ["stay"]
    if not env._bomb_at(x, y):
        legal.append("bomb")
    for command, (dx, dy) in (("up", (0, -1)), ("down", (0, 1)), ("left", (-1, 0)), ("right", (1, 0))):
        if env._blocker(x + dx, y + dy, pid) is None:
            legal.append(command)
    return legal


def _random_game(seed, max_turns=30):
    env = _fresh(seed=seed, max_turns=max_turns)
    policy = random.Random(seed)
    trace = []
    while not env.state.done:
        action = policy.choice(_legal_commands(env))
        env.step(action)
        assert env.state.error_count == 0
        trace.append((env.state.current_player_id, action))
        assert len(trace) <= 2 * max_turns
    return trace, env.state.rewards, copy.deepcopy(env.game_state)


@pytest.mark.parametrize("seed", range(12))
def test_random_legal_play_terminates_deterministically(seed):
    first = _random_game(seed)
    assert first == _random_game(seed)
    trace, rewards, gs = first
    assert set(rewards) == {0, 1} and sorted(rewards.values()) in ([-1, 1], [0, 0])
    if len(trace) < 60:
        assert not all(gs["alive"])  # anything shorter than the round limit ended in an explosion
