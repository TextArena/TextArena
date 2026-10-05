"""Offline deterministic tests for the single-player Sokoban environment.

The room is generated deterministically from the seed, so we read the layout
straight from the env and run a small BFS push-solver to script a guaranteed win.
"""
from collections import deque
import random

import pytest

from textarena.envs.Sokoban.env import SokobanEnv
from textarena.envs.Sokoban import env as sokoban_env
from textarena.envs.Sokoban import utils as sokoban_utils

_DIRS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}


def _fresh(dim_room=(6, 6), num_boxes=2, max_turns=100):
    env = SokobanEnv(dim_room=dim_room, num_boxes=num_boxes, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _solve(env, max_states=300000):
    """BFS over (player, boxes) states; returns a list of move names or None."""
    room_fixed = env.room_fixed
    H, W = len(room_fixed), len(room_fixed[0])
    walls = {(r, c) for r in range(H) for c in range(W) if room_fixed[r][c] == 0}
    targets = frozenset(
        (r, c) for r in range(H) for c in range(W) if room_fixed[r][c] == 2
    )
    boxes0 = frozenset(
        (r, c) for r in range(H) for c in range(W) if env.room_state[r][c] in (3, 4)
    )
    player0 = env.player_position
    if boxes0 == targets:
        return []

    start = (player0, boxes0)
    seen = {start}
    queue = deque([(start, [])])
    while queue and len(seen) < max_states:
        (player, boxes), path = queue.popleft()
        for name, (dr, dc) in _DIRS.items():
            nr, nc = player[0] + dr, player[1] + dc
            if (nr, nc) in walls:
                continue
            nboxes = boxes
            if (nr, nc) in boxes:
                br, bc = nr + dr, nc + dc
                if (br, bc) in walls or (br, bc) in boxes:
                    continue
                nboxes = frozenset((boxes - {(nr, nc)}) | {(br, bc)})
            nstate = ((nr, nc), nboxes)
            if nstate in seen:
                continue
            npath = path + [name]
            if nboxes == targets:
                return npath
            seen.add(nstate)
            queue.append((nstate, npath))
    return None


def test_reset_initial_state():
    env = _fresh()
    assert env.state.num_players == 1
    assert not env.state.done
    assert env.player_position is not None
    # Exactly num_boxes boxes present (value 3=on target, 4=off target).
    box_count = sum(cell in (3, 4) for row in env.room_state for cell in row)
    assert box_count == 2


def test_invalid_format_increments_error():
    env = _fresh()
    done = env.step("do a barrel roll")
    assert not done
    assert env.state.error_count == 1


def test_two_invalid_moves_end_game_with_completion_reward():
    env = _fresh()
    expected = env._get_percentage_completion()
    env.step("nonsense one")            # first invalid -> error_count 1
    done = env.step("nonsense two")  # second consecutive invalid ends game
    assert done
    assert env.state.rewards == {0: expected}


def test_wall_collision_is_rejected():
    env = _fresh()
    colliding = [a for a in env.action_space if env._would_collide_with_wall(a)]
    if not colliding:
        return  # No wall-adjacent direction for this layout; nothing to assert.
    done = env.step(colliding[0])
    assert not done
    assert env.state.error_count == 1


def test_valid_move_updates_board():
    env = _fresh()
    legal = [a for a in env.action_space if not env._would_collide_with_wall(a)]
    assert legal, "player should have at least one legal move"
    before = env.player_position
    done = env.step(legal[0])
    assert not done
    # Either the player moved or pushed a box (position changes on a plain move).
    assert env.player_position != before or env.state.turn >= 1


def test_solving_puzzle_wins():
    env = _fresh()
    solution = _solve(env)
    assert solution is not None, "generated room should be solvable"
    done = False
    for move in solution:
        assert not done
        done = env.step(move)
    assert done
    assert env.state.rewards == {0: 1.0}


def _board_signature(env):
    return (
        tuple(map(tuple, env.room_fixed)),
        tuple(map(tuple, env.room_state)),
        env.player_position,
    )


@pytest.mark.parametrize("seed", range(8))
def test_generated_instances_are_solvable_and_seeded(seed):
    first = SokobanEnv(dim_room=(6, 6), num_boxes=1, max_turns=100)
    second = SokobanEnv(dim_room=(6, 6), num_boxes=1, max_turns=100)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert _board_signature(first) == _board_signature(second)
    solution = _solve(first)
    assert solution is not None
    assert len(solution) <= first.max_turns


@pytest.mark.parametrize(
    "dim_room,num_boxes,max_turns,seed,max_states",
    [
        ((6, 6), 3, 30, 0, 500_000),
        ((6, 6), 3, 30, 4, 500_000),
        ((8, 8), 5, 50, 1, 2_000_000),
        ((8, 8), 5, 50, 11, 2_000_000),
    ],
)
def test_registered_sokoban_sizes_have_solutions_within_turn_budget(
    dim_room,
    num_boxes,
    max_turns,
    seed,
    max_states,
):
    env = SokobanEnv(
        dim_room=dim_room,
        num_boxes=num_boxes,
        max_turns=max_turns,
    )
    env.reset(num_players=1, seed=seed)
    solution = _solve(env, max_states=max_states)
    assert solution is not None
    assert len(solution) <= max_turns


@pytest.mark.parametrize("seed", [-3, 2**70])
def test_any_integer_seed_generates_a_reproducible_room(seed):
    first = SokobanEnv(dim_room=(6, 6), num_boxes=1)
    second = SokobanEnv(dim_room=(6, 6), num_boxes=1)
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert _board_signature(first) == _board_signature(second)


def test_different_seeds_generate_different_rooms():
    signatures = set()
    for seed in range(8):
        env = SokobanEnv(dim_room=(6, 6), num_boxes=1)
        env.reset(num_players=1, seed=seed)
        signatures.add(_board_signature(env))
    assert len(signatures) > 1


@pytest.mark.parametrize("max_turns", [1, 2, 3, 5])
def test_small_turn_limits_only_generate_rooms_solvable_within_the_limit(max_turns):
    for seed in range(15):
        env = SokobanEnv(dim_room=(6, 6), num_boxes=1, max_turns=max_turns)
        env.reset(num_players=1, seed=seed)
        solution = _solve(env)
        assert solution is not None and len(solution) <= max_turns


def test_generation_does_not_consume_the_global_random_generator():
    random.seed(1234)
    python_state = random.getstate()
    env = SokobanEnv(dim_room=(6, 6), num_boxes=1)
    env.reset(num_players=1, seed=9)
    assert random.getstate() == python_state


def test_reverse_generation_honors_search_depth_budget(monkeypatch):
    captured = {}

    def fake_search(*args, **kwargs):
        captured["ttl"] = kwargs["ttl"]

    monkeypatch.setattr(sokoban_utils, "depth_first_search", fake_search)
    room_structure = [[1] * 4 for _ in range(4)]
    room_structure[1][1] = 2
    room_state = [row[:] for row in room_structure]
    room_state[1][1] = 4
    room_state[2][1] = 5
    sokoban_utils.reverse_playing(room_state, room_structure, search_depth=7)
    assert captured["ttl"] == 7


@pytest.mark.parametrize(
    "action",
    ["up now", "[up", "up]", "up,down", "north", ""],
)
def test_exact_parser_rejects_malformed_actions_atomically(action):
    env = _fresh()
    before = _board_signature(env)
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert _board_signature(env) == before


def test_oversized_action_is_invalid_without_board_mutation():
    env = _fresh()
    before = _board_signature(env)
    done = env.step("x" * (env.max_action_chars + 1))
    assert not done
    assert env.state.error_count == 1
    assert _board_signature(env) == before


def _install_scripted_room(env):
    room_fixed = [
        [0, 0, 0, 0, 0],
        [0, 1, 2, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 1, 1, 1, 0],
        [0, 0, 0, 0, 0],
    ]
    room_state = [row[:] for row in room_fixed]
    room_state[2][2] = 4
    room_state[3][2] = 5
    env.game_state["room_fixed"] = room_fixed
    env.game_state["board"] = room_state
    env.game_state["player_position"] = (3, 2)


def test_push_box_onto_target_wins_and_terminal_render_updates():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    assert "X" in env.render(0) and "O" in env.render(0)
    done = env.step("up")
    assert done
    assert env.state.rewards == {0: 1}
    assert env.room_state[1][2] == 3
    assert "√" in env.render(0)


def _last_game_messages(env, count):
    return [message for _, message, kind, _ in env.state.events if kind.name == "GAME_MESSAGE"][-count:]


def test_player_standing_on_a_goal_keeps_the_goal_visible():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    for move in ("left", "up", "up", "right"):
        done = env.step(move)
        assert not done
    assert env.player_position == (1, 2) and env.room_fixed[1][2] == 2
    assert env.create_board_str(env.room_state).splitlines()[1] == "# _ + _ #"
    assert "+" in env.render(0) and "+" in env.get_board_str()
    assert "'+' while standing on an empty goal" in env.prompt(0)
    assert "'_'" in env.prompt(0)


def test_move_messages_describe_walks_and_pushes():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    env.step("left")
    env.step("right")
    env.step("up")
    assert _last_game_messages(env, 3) == ["You moved left.", "You moved right.", "You moved up and pushed a box."]


def test_blocked_push_is_invalid_and_atomic():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    env.room_state[1][2] = 0
    before = _board_signature(env)
    done = env.step("up")
    assert not done
    assert env.state.error_count == 1
    assert _board_signature(env) == before


@pytest.mark.parametrize(
    "blocker,reason",
    [(0, "You cannot push a box into a wall!"), (3, "You cannot push a box into another box!")],
)
def test_blocked_push_reason_names_what_blocks_the_box(blocker, reason):
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    env.room_state[1][2] = blocker
    before = len(env.state.events)
    env.step("up")
    messages = [message for _, message, _, _ in env.state.events[before:]]
    assert any(f"Reason: {reason}" in message for message in messages)


def test_turn_limit_returns_box_completion_reward():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1, max_turns=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    done = env.step("left")
    assert done
    assert env.state.rewards == {0: 0.0}
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


def test_snapshot_restore_recovers_board_aliases():
    env = SokobanEnv(dim_room=(5, 5), num_boxes=1)
    env.reset(num_players=1, seed=42)
    _install_scripted_room(env)
    snapshot = env.snapshot()
    env.step("left")
    assert env.player_position == (3, 1)
    env.restore(snapshot)
    assert env.player_position == (3, 2)
    assert env.room_state is env.game_state["board"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dim_room": (3, 6)},
        {"dim_room": (6, 6, 6)},
        {"num_boxes": 0},
        {"dim_room": (4, 4), "num_boxes": 3},
        {"max_turns": 0},
        {"dim_room": (21, 20)},
        {"max_retries": 0},
        {"max_retries": 101},
        {"max_retries": True},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SokobanEnv(**kwargs)


def test_generation_gives_up_after_max_retries(monkeypatch):
    attempts = []

    def failing_generate_room(*args, **kwargs):
        attempts.append(kwargs)
        return None

    monkeypatch.setattr(sokoban_env, "generate_room", failing_generate_room)
    env = SokobanEnv(dim_room=(6, 6), num_boxes=1, max_retries=3)
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        env.reset(num_players=1, seed=1)
    assert len(attempts) == 3


@pytest.mark.parametrize(
    "env_id,seed",
    [("Sokoban-v1", 34051), ("Sokoban-v1-medium", 9879), ("Sokoban-v1-medium", 12198), ("Sokoban-v1-medium", 94006)],
)
def test_registered_variants_reset_on_seeds_that_need_more_than_50_attempts(env_id, seed):
    import textarena as ta

    env = ta.make(env_id)
    env.reset(num_players=1, seed=seed)
    inner = env
    while hasattr(inner, "env"):
        inner = inner.env
    assert inner.max_retries == 100
    solution = _solve(inner, max_states=2_000_000)
    assert solution is not None and len(solution) <= inner.max_turns


def test_prompt_states_that_invalid_moves_are_free_but_limited():
    env = _fresh()
    prompt = env.prompt(0)
    assert "does not count as a move" in prompt
    assert "two invalid moves in a row end the game" in prompt
    turn = env.state.turn
    env.step("nonsense")
    assert env.state.turn == turn and not env.state.done
    assert env.step("nonsense")
