"""Deterministic tests for Retro Space Duel.

Players alternate turns (Player 0 first). A turn is a bare direction key
(w/s/a/d/q/e/z/c) to move or 'f <key>' to shoot. Positions are (x, y) with y
growing downward; the outer ring of the arena is the boundary. Most rule tests
clear the random objects and place ships and objects explicitly.
"""
import copy
import random

import pytest

import textarena as ta
from textarena.envs.RetroSpaceDuel.env import DIRECTIONS, RetroSpaceDuelEnv


class _FixedChoice(random.Random):
    """RNG whose choice() always returns the given power-up type."""

    def __init__(self, value):
        super().__init__(0)
        self.value = value

    def choice(self, seq):
        assert self.value in seq
        return self.value


def _fresh(seed=42, **kwargs):
    env = RetroSpaceDuelEnv(**kwargs)
    env.reset(num_players=2, seed=seed)
    return env


def _arena(env, p0=(3, 3), p1=(11, 11), objects=None, **ship_overrides):
    """Clear all objects, place both ships, and optionally override ship stats (e.g. p0_speed=2)."""
    gs = env.game_state
    gs["objects"] = dict(objects or {})
    gs["ships"][0]["pos"], gs["ships"][1]["pos"] = p0, p1
    for key, value in ship_overrides.items():
        pid, stat = key.split("_", 1)
        gs["ships"][int(pid[1:])][stat] = value
    return gs


def _play(env, *actions):
    """Play valid actions in order and return whether the game is done."""
    done = False
    for action in actions:
        assert not done, f"game ended before {action!r}"
        done, _ = env.step(action)
        assert env.state.error_count == 0, f"{action!r} was rejected"
    return done


def _ship(env, pid):
    return env.game_state["ships"][pid]


# ---------------------------------------------------------------- arena setup
def test_reset_initial_state():
    env = _fresh()
    ships = env.game_state["ships"]
    assert [ship["pos"] for ship in ships] == [(1, 1), (13, 13)]
    for ship in ships:
        assert (ship["health"], ship["shields"], ship["speed"], ship["spread"]) == (100, 0, 1, False)
    assert env.state.current_player_id == 0
    assert env.state.max_turns == 100


@pytest.mark.parametrize("seed", range(6))
def test_objects_are_placed_exactly_and_away_from_spawns(seed):
    env = _fresh(seed=seed)
    objects = env.game_state["objects"]
    kinds = [kind for kind in objects.values()]
    assert {kind: kinds.count(kind) for kind in set(kinds)} == {"asteroid": 5, "debris": 8, "nebula": 3, "mine": 4, "powerup": 3}
    for x, y in objects:
        assert 1 <= x <= 13 and 1 <= y <= 13
        assert max(abs(x - 1), abs(y - 1)) > 1 and max(abs(x - 13), abs(y - 13)) > 1


def test_small_arena_fits_requested_objects():
    env = _fresh(grid_size=(5, 5), num_asteroids=1, num_debris=1, num_nebulas=0, num_mines=0, num_powerups=0)
    assert sorted(env.game_state["objects"]) == [(1, 3), (3, 1)]


# --------------------------------------------------------------------- moves
@pytest.mark.parametrize("key", sorted(DIRECTIONS))
def test_moves_in_all_eight_directions(key):
    env = _fresh()
    gs = _arena(env, p0=(7, 7))
    _, dx, dy = DIRECTIONS[key]
    assert not _play(env, key)
    assert gs["ships"][0]["pos"] == (7 + dx, 7 + dy)
    assert env.state.current_player_id == 1


@pytest.mark.parametrize(
    "p0, objects, p1, key",
    [
        ((3, 3), {(4, 3): "asteroid"}, (11, 11), "d"),
        ((3, 3), {(4, 3): "debris"}, (11, 11), "d"),
        ((3, 3), {}, (4, 4), "c"),
        ((1, 3), {}, (11, 11), "a"),
        ((1, 1), {}, (11, 11), "q"),
    ],
)
def test_blocked_moves_are_invalid_and_atomic(p0, objects, p1, key):
    env = _fresh()
    gs = _arena(env, p0=p0, p1=p1, objects=objects, p0_speed=2)
    before = copy.deepcopy(gs)
    done, _ = env.step(key)
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert gs == before


def test_speed_power_up_moves_two_cells():
    env = _fresh()
    gs = _arena(env, p0_speed=2)
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (5, 3)


def test_boosted_move_stops_in_front_of_a_blocked_second_cell():
    env = _fresh()
    gs = _arena(env, objects={(5, 3): "debris"}, p0_speed=2)
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (4, 3)


def test_boosted_move_stops_in_front_of_the_enemy_ship():
    env = _fresh()
    gs = _arena(env, p1=(5, 5), p0_speed=2)
    _play(env, "c")
    assert gs["ships"][0]["pos"] == (4, 4)


def test_starting_inside_a_nebula_limits_the_move_to_one_cell():
    env = _fresh()
    gs = _arena(env, objects={(3, 3): "nebula"}, p0_speed=2)
    assert "inside a nebula: moves 1 cell this turn" in env.get_board_str()
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (4, 3)


def test_entering_a_nebula_ends_the_move():
    env = _fresh()
    gs = _arena(env, objects={(4, 3): "nebula"}, p0_speed=2)
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (4, 3)
    assert gs["objects"][(4, 3)] == "nebula"  # nebulas are permanent
    assert env.get_board_str().splitlines()[1 + 3].split()[1 + 4] == "0"  # the ship is drawn inside it


# ------------------------------------------------------- mines and power-ups
def test_entering_a_mine_ends_the_move_and_damages_the_ship():
    env = _fresh()
    gs = _arena(env, objects={(4, 3): "mine"}, p0_speed=2)
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (4, 3)
    assert gs["ships"][0]["health"] == 80
    assert (4, 3) not in gs["objects"]


def test_shield_halves_mine_damage_and_uses_a_charge():
    env = _fresh()
    gs = _arena(env, objects={(4, 3): "mine"}, p0_shields=2)
    _play(env, "d")
    assert (gs["ships"][0]["health"], gs["ships"][0]["shields"]) == (90, 1)


def test_mine_can_destroy_a_ship():
    env = _fresh()
    _arena(env, objects={(4, 3): "mine"}, p0_health=20)
    assert _play(env, "d")
    assert env.state.rewards == {0: -1, 1: 1}
    assert "Player 0's ship was destroyed" in env.state.game_info[1]["reason"]


@pytest.mark.parametrize(
    "kind, stat, value",
    [("shield", "shields", 3), ("speed", "speed", 2), ("weapon", "spread", True)],
)
def test_power_up_effects(kind, stat, value):
    env = _fresh()
    gs = _arena(env, objects={(4, 3): "powerup"}, p0_shields=1)
    env.rng = _FixedChoice(kind)
    _play(env, "d")
    assert gs["ships"][0][stat] == value
    assert (4, 3) not in gs["objects"]
    assert any(f"Player 0 collected a {kind} power-up" in message for _, message, _, _ in env.state.events)


def test_boosted_move_stops_on_a_power_up():
    env = _fresh()
    gs = _arena(env, objects={(4, 3): "powerup"}, p0_speed=2)
    env.rng = _FixedChoice("shield")
    _play(env, "d")
    assert gs["ships"][0]["pos"] == (4, 3)
    assert gs["ships"][0]["shields"] == 3


def test_power_up_type_is_seeded():
    def collected(seed):
        env = _fresh(seed=seed)
        gs = _arena(env, objects={(4, 3): "powerup"})
        _play(env, "d")
        ship = gs["ships"][0]
        return ship["shields"], ship["speed"], ship["spread"]

    assert all(collected(seed) == collected(seed) for seed in range(5))
    assert len({collected(seed) for seed in range(12)}) == 3  # all three types occur


# ------------------------------------------------------------------ shooting
def test_shot_hits_the_enemy():
    env = _fresh()
    gs = _arena(env, p1=(8, 3))
    assert not _play(env, "f d")
    assert gs["ships"][1]["health"] == 90
    assert gs["ships"][0]["health"] == 100
    assert gs["ships"][0]["pos"] == (3, 3)


def test_shield_halves_shot_damage_and_uses_a_charge():
    env = _fresh()
    gs = _arena(env, p1=(8, 8), p1_shields=2)
    _play(env, "f c")
    assert (gs["ships"][1]["health"], gs["ships"][1]["shields"]) == (95, 1)


@pytest.mark.parametrize("kind", ["debris", "mine", "powerup"])
def test_shot_destroys_the_first_destructible_object(kind):
    env = _fresh()
    gs = _arena(env, p1=(8, 3), objects={(5, 3): kind, (6, 3): "debris"})
    assert not _play(env, "f d")
    assert gs["objects"] == {(6, 3): "debris"}
    assert gs["ships"][1]["health"] == 100


def test_shot_passes_through_nebulas_and_hits_a_ship_inside_one():
    env = _fresh()
    gs = _arena(env, p1=(8, 3), objects={(5, 3): "nebula", (8, 3): "nebula"})
    _play(env, "f d")
    assert gs["ships"][1]["health"] == 90
    assert gs["objects"] == {(5, 3): "nebula", (8, 3): "nebula"}


def test_ricochet_off_the_boundary_destroys_the_shooter():
    env = _fresh()
    gs = _arena(env)
    assert _play(env, "f w")
    assert gs["ships"][0]["health"] == 0
    assert env.state.rewards == {0: -1, 1: 1}
    assert "Final arena:" in env.render(0) and "Player 0 ('0'): destroyed at (3, 3)" in env.render(0)


def test_ricochet_off_an_asteroid_ignores_shields():
    env = _fresh()
    gs = _arena(env, p1=(8, 3), objects={(6, 3): "asteroid"}, p0_shields=3)
    assert _play(env, "f d")
    assert gs["ships"][0]["health"] == 0
    assert gs["ships"][1]["health"] == 100  # the asteroid shielded the enemy
    assert env.state.rewards == {0: -1, 1: 1}


def test_spread_shot_side_projectiles_dissipate_harmlessly():
    env = _fresh()
    gs = _arena(env, p1=(8, 3), p0_spread=True)
    assert not _play(env, "f d")  # the main shot hits; both side shots fly into the boundary
    assert gs["ships"][1]["health"] == 90
    assert gs["ships"][0]["health"] == 100
    messages = [message for _, message, _, _ in env.state.events]
    assert "Player 0 fired a spread shot right." in messages
    assert sum("dissipated" in message for message in messages) == 2


def test_spread_shot_side_projectile_can_hit_and_destroy_objects():
    env = _fresh()
    gs = _arena(env, p1=(6, 6), objects={(6, 3): "debris", (5, 1): "mine"}, p0_spread=True)
    _play(env, "f d")  # main: debris at (6, 3); up-right side: mine at (5, 1); down-right side: enemy
    assert gs["objects"] == {}
    assert gs["ships"][1]["health"] == 90
    assert gs["ships"][0]["health"] == 100


def test_spread_shot_side_projectiles_are_45_degrees_off_a_diagonal_shot():
    env = _fresh()
    gs = _arena(env, p1=(11, 11), objects={(3, 5): "debris", (5, 3): "debris", (5, 5): "debris"}, p0_spread=True)
    _play(env, "f c")  # down-right; sides go down and right
    assert gs["objects"] == {}


def test_main_ricochet_and_lethal_side_hit_on_the_same_turn_is_a_draw():
    env = _fresh()
    gs = _arena(env, p1=(6, 6), p0_spread=True, p1_health=10)
    assert _play(env, "f d")
    assert gs["ships"][0]["health"] == gs["ships"][1]["health"] == 0
    assert env.state.rewards == {0: 0, 1: 0}


# --------------------------------------------------------------- turn limits
def test_turn_limit_is_decided_by_health():
    env = _fresh(max_turns=2)
    _arena(env, p1=(8, 3))
    assert not _play(env, "f d")
    assert _play(env, "w")
    assert env.state.rewards == {0: 1, 1: -1}
    assert "more health (100 vs 90)" in env.state.game_info[0]["reason"]


def test_turn_limit_with_equal_health_is_a_draw():
    env = _fresh(max_turns=4)
    _arena(env)
    assert not _play(env, "d", "a", "s")
    assert _play(env, "w")
    assert env.state.rewards == {0: 0, 1: 0}
    assert env.state.turn == 4
    assert all(env.state.game_info[pid]["turn_count"] == 2 for pid in range(2))


def test_turn_counter_in_render():
    env = _fresh()
    _arena(env)
    assert env.render(0).startswith("Turn 1/100: Player 0 to move.")
    _play(env, "d")
    assert env.render(1).startswith("Turn 2/100: Player 1 to move.")


# ------------------------------------------------------------ action parsing
def test_actions_tolerate_case_and_whitespace():
    env = _fresh()
    gs = _arena(env, p1=(11, 3), objects={(5, 3): "debris", (9, 2): "debris"})
    assert not _play(env, "D", "s", " F  D ", "fq")  # the shots hit (5, 3) and (9, 2)
    assert gs["ships"][0]["pos"] == (4, 3)
    assert gs["ships"][1]["pos"] == (11, 4)
    assert gs["objects"] == {}


@pytest.mark.parametrize("action", ["fire a", "x", "f", "f x", "w a", "ww", "<action>w</action>", "", "f a please"])
def test_malformed_actions_are_rejected(action):
    env = _fresh()
    gs = _arena(env)
    before = copy.deepcopy(gs)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert gs == before


def test_two_consecutive_invalid_moves_lose():
    env = _fresh()
    env.step("jump")
    done, _ = env.step("warp")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.game_info[0]["invalid_move"]


def test_oversized_action_is_rejected_without_side_effects():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("w" * (env.max_action_chars + 1))
    assert not done and env.state.error_count == 1
    assert env.game_state == before


# --------------------------------------------------------- rendering & prompt
def test_board_string_is_consistent_with_state():
    env = _fresh()
    _arena(env, p0=(2, 5), p1=(12, 9), objects={(4, 4): "asteroid", (5, 6): "debris", (7, 7): "nebula", (9, 2): "mine", (10, 10): "powerup"},
           p1_shields=2, p1_speed=2, p1_spread=True)
    board = env.get_board_str()
    assert board in env.render(0)
    rows = [row.split() for row in board.splitlines()]
    assert rows[0] == [str(x) for x in range(15)]
    grid = {(x, y): rows[1 + y][1 + x] for y in range(15) for x in range(15)}
    assert grid[(0, 0)] == grid[(14, 7)] == "#"
    assert (grid[(2, 5)], grid[(12, 9)]) == ("0", "1")
    assert [grid[cell] for cell in [(4, 4), (5, 6), (7, 7), (9, 2), (10, 10)]] == ["A", "D", "~", "M", "+"]
    assert sum(cell == "." for cell in grid.values()) == 13 * 13 - 7
    assert "Player 0 ('0'): position (2, 5), health 100, shields 0, speed 1, weapon normal" in board
    assert "Player 1 ('1'): position (12, 9), health 100, shields 2, speed 2, weapon spread shot" in board


def test_prompt_is_ascii_and_teaches_bare_actions():
    env = _fresh()
    prompt = env.prompt(1)
    assert all(ord(ch) < 128 for ch in prompt)
    assert all(ord(ch) < 128 for ch in env.render(0))
    assert "'f a' (shoot left)" in prompt and "'w' (move up)" in prompt
    assert "[" not in prompt and "]" not in prompt
    assert "After 100 turns in total (50 each)" in prompt
    assert "Your ship is shown as '1'" in prompt


def test_initial_observation_contains_prompt_and_board():
    env = _fresh()
    pid, observation = env.get_observation()
    assert pid == 0
    assert [kind for _, _, kind in observation] == [ta.ObservationType.PROMPT, ta.ObservationType.GAME_BOARD]


# ------------------------------------------------------- snapshots & config
@pytest.mark.parametrize(
    "kwargs",
    [
        {"grid_size": (4, 15)},
        {"grid_size": (15,)},
        {"grid_size": "15x15"},
        {"grid_size": (15.0, 15)},
        {"max_turns": 0},
        {"max_turns": 3},
        {"max_turns": True},
        {"max_turns": 10.0},
        {"grid_size": (5, 5), "num_asteroids": 3},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        RetroSpaceDuelEnv(**kwargs)


def test_registered_variants_use_upstream_defaults():
    for env_id in ("RetroSpaceDuel-v1", "RetroSpaceDuel-v1-mdp"):
        env = ta.make(env_id)
        env.reset(num_players=2, seed=1)
        assert (env.grid_size, env.max_turns) == ((15, 15), 100)
        done, _ = env.step("d")
        assert not done and env.state.error_count == 0


# ------------------------------------------------------------- random play
def _legal_actions(env):
    pid = env.state.current_player_id
    gs = env.game_state
    x, y = gs["ships"][pid]["pos"]
    moves = [key for key, (_, dx, dy) in DIRECTIONS.items() if env._movement_blocker(x + dx, y + dy, pid) is None]
    safe_shots = []
    for key, (_, dx, dy) in DIRECTIONS.items():
        sx, sy = x, y
        while True:
            sx, sy = sx + dx, sy + dy
            kind = gs["objects"].get((sx, sy))
            if env._is_boundary(sx, sy) or kind == "asteroid":
                break
            if gs["ships"][1 - pid]["pos"] == (sx, sy) or kind in ("debris", "mine", "powerup"):
                safe_shots.append(f"f {key}")
                break
    return moves, safe_shots


def _random_game(seed, reckless):
    env = _fresh(seed=seed, max_turns=60)
    policy = random.Random(seed)
    trace = []
    while not env.state.done:
        moves, safe_shots = _legal_actions(env)
        if (reckless and policy.random() < 0.2) or not (moves or safe_shots):
            action = f"f {policy.choice(sorted(DIRECTIONS))}"
        elif safe_shots and (not moves or policy.random() < 0.5):
            action = policy.choice(safe_shots)
        else:
            action = policy.choice(moves)
        env.step(action)
        assert env.state.error_count == 0
        trace.append(action)
        assert len(trace) <= 60
    return trace, env.state.rewards, copy.deepcopy(env.game_state)


@pytest.mark.parametrize("reckless", [False, True])
@pytest.mark.parametrize("seed", range(8))
def test_random_legal_play_terminates_deterministically(seed, reckless):
    first = _random_game(seed, reckless)
    assert first == _random_game(seed, reckless)
    trace, rewards, gs = first
    assert set(rewards) == {0, 1} and sorted(rewards.values()) in ([-1, 1], [0, 0])
    if len(trace) < 60:
        assert any(ship["health"] == 0 for ship in gs["ships"])
