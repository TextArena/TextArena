"""Offline deterministic tests for the multiplayer Snake environment."""
import pytest

from textarena.envs.Snake.env import SnakeEnv


def _fresh(num_players=2, **kwargs):
    env = SnakeEnv(**kwargs)
    env.reset(num_players=num_players, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh(num_players=3, num_apples=3)
    gs = env.state.game_state
    assert len(gs["snakes"]) == 3
    assert all(s.alive for s in gs["snakes"].values())
    assert len(gs["apples"]) == 3
    assert gs["scores"] == {0: 0, 1: 0, 2: 0}
    assert env.state.current_player_id == 0


def test_reset_places_unique_apples_and_supports_declared_player_limit():
    env = _fresh(num_players=2, width=5, height=5, num_apples=8)
    gs = env.state.game_state
    assert len(gs["apples"]) == len(set(gs["apples"])) == 8
    assert not (set(gs["apples"]) & {snake.head for snake in gs["snakes"].values()})

    crowded = _fresh(num_players=15, width=5, height=5, num_apples=2)
    heads = [snake.head for snake in crowded.state.game_state["snakes"].values()]
    assert len(heads) == len(set(heads)) == 15


@pytest.mark.parametrize(
    "kwargs",
    [
        {"width": 5.5},
        {"height": True},
        {"num_apples": 1.5},
        {"num_apples": -1},
        {"max_turns": 0},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        SnakeEnv(**kwargs)


def test_valid_moves_keep_game_running():
    env = _fresh(num_players=2)
    done, _ = env.step("up")     # P0 acts; turn passes to P1
    assert not done
    assert env.state.current_player_id == 1
    done, _ = env.step("down")   # both have acted -> simultaneous resolution
    assert not done
    snakes = env.state.game_state["snakes"]
    assert all(s.alive for s in snakes.values())


def test_invalid_move_kills_snake_and_opponent_wins():
    env = _fresh(num_players=2)
    done, _ = env.step("this has no direction token")
    # P0's snake dies; only P1 remains -> game ends immediately.
    assert done
    assert not env.state.game_state["snakes"][0].alive
    assert env.state.game_state["snakes"][1].alive
    # Two-group linear scale: worst -> -1, best -> +1.
    assert env.state.rewards == {0: -1.0, 1: 1.0}


def test_invalid_death_immediately_synchronizes_cached_board():
    env = _fresh(num_players=3, width=5, height=5, num_apples=2)
    dead_head = env.state.game_state["snakes"][0].head

    done, _ = env.step("not a direction")

    assert not done
    assert env.state.game_state["board_state"] == env._get_board_string(
        env.state.game_state["snakes"], env.state.game_state["apples"]
    )
    x, y = dead_head
    rendered_rows = env.state.game_state["board_state"].splitlines()[1:-1]
    assert rendered_rows[env.height - 1 - y].split()[x + 1] != "0"


def test_pending_direction_is_private_until_round_resolution():
    env = _fresh(num_players=3, width=5, height=5, num_apples=2)
    env.get_observation()  # consume player 0's initial messages

    done, _ = env.step("up")

    assert not done
    assert not any(
        from_id == 0 and text == "up" and to_id in (-1, 1)
        for from_id, text, _kind, to_id in env.state.events
    )


def test_snapshot_restore_replays_rng_and_simultaneous_round():
    env = _fresh(num_players=2, width=5, height=5, num_apples=2)
    gs = env.state.game_state
    gs["snakes"][0].positions.clear()
    gs["snakes"][0].positions.append((1, 1))
    gs["snakes"][1].positions.clear()
    gs["snakes"][1].positions.append((3, 3))
    gs["apples"][:] = [(2, 1)]
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])
    snapshot = env.snapshot()

    env.step("right")
    env.step("up")
    first = (
        list(env.state.game_state["snakes"][0].positions),
        list(env.state.game_state["snakes"][1].positions),
        list(env.state.game_state["apples"]),
        dict(env.state.game_state["scores"]),
    )

    env.restore(snapshot)
    env.step("right")
    env.step("up")
    second = (
        list(env.state.game_state["snakes"][0].positions),
        list(env.state.game_state["snakes"][1].positions),
        list(env.state.game_state["apples"]),
        dict(env.state.game_state["scores"]),
    )

    assert second == first
    assert second[3] == {0: 1, 1: 0}
    occupied = {
        position
        for snake in env.state.game_state["snakes"].values()
        for position in snake.positions
    }
    assert not occupied.intersection(second[2])


def test_round_limit_waits_for_every_living_snake_to_move():
    env = _fresh(num_players=3, width=5, height=5, num_apples=0, max_turns=1)
    gs = env.state.game_state
    starts = {0: (1, 1), 1: (2, 3), 2: (3, 1)}
    for pid, position in starts.items():
        gs["snakes"][pid].positions.clear()
        gs["snakes"][pid].positions.append(position)
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])

    done, _ = env.step("up")
    assert not done
    done, _ = env.step("left")
    assert not done
    assert {pid: snake.head for pid, snake in gs["snakes"].items()} == starts

    done, _ = env.step("up")

    assert done
    assert gs["round_count"] == 1
    assert {pid: snake.head for pid, snake in gs["snakes"].items()} == {
        0: (1, 2),
        1: (1, 3),
        2: (3, 2),
    }


def test_body_of_wall_collision_still_causes_same_round_collision():
    env = _fresh(num_players=2, width=5, height=5, num_apples=0)
    gs = env.state.game_state
    gs["snakes"][0].positions.clear()
    gs["snakes"][0].positions.append((3, 0))
    gs["snakes"][1].positions.clear()
    gs["snakes"][1].positions.extend([(4, 1), (3, 1), (2, 1)])
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])

    env.step("up")
    done, _ = env.step("right")

    assert done
    assert not gs["snakes"][0].alive
    assert gs["snakes"][0].death_reason == "body collision"
    assert not gs["snakes"][1].alive
    assert gs["snakes"][1].death_reason == "wall"


def test_tail_of_doomed_snake_does_not_vacate():
    env = _fresh(num_players=2, width=5, height=5, num_apples=0)
    gs = env.state.game_state
    gs["snakes"][0].positions.clear()
    gs["snakes"][0].positions.append((3, 1))
    gs["snakes"][1].positions.clear()
    gs["snakes"][1].positions.extend([(4, 2), (4, 1)])
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])

    env.step("right")
    done, _ = env.step("right")

    assert done
    assert not gs["snakes"][0].alive
    assert gs["snakes"][0].death_reason == "body collision"
    assert not gs["snakes"][1].alive
    assert gs["snakes"][1].death_reason == "wall"


def test_vacating_tail_is_not_a_body_collision():
    env = _fresh(num_players=2, width=5, height=5, num_apples=0)
    gs = env.state.game_state
    gs["snakes"][0].positions.clear()
    gs["snakes"][0].positions.append((1, 0))
    gs["snakes"][1].positions.clear()
    gs["snakes"][1].positions.extend([(3, 1), (2, 1), (1, 1)])
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])

    env.step("up")
    done, _ = env.step("right")

    assert not done
    assert all(snake.alive for snake in gs["snakes"].values())
    assert gs["snakes"][0].head == (1, 1)
    assert list(gs["snakes"][1].positions) == [(4, 1), (3, 1), (2, 1)]


def test_alias_direction_tokens_accepted():
    env = _fresh(num_players=2)
    done, _ = env.step("w")  # alias for up
    assert not done
    assert env.state.game_state["snakes"][0].alive
    # A recognised token is stored as a pending action for P0.
    assert env.pending_actions[0] is not None


def test_turn_limit_finalises_rewards():
    # Very short game: both snakes survive; turn limit ends it with a draw
    # (equal survival, equal score => single tie-group => all zeros).
    env = _fresh(num_players=2, max_turns=2)
    done = False
    moves = ["up", "[up]", "left", "right"]  # brackets tolerated
    for m in moves:
        if done:
            break
        done, _ = env.step(m)
    assert done
    assert env.state.rewards is not None
    assert set(env.state.rewards.keys()) == {0, 1}


def _place(env, positions, apples=()):
    gs = env.state.game_state
    for pid, cells in positions.items():
        gs["snakes"][pid].positions.clear()
        gs["snakes"][pid].positions.extend(cells)
    gs["apples"][:] = list(apples)
    gs["board_state"] = env._get_board_string(gs["snakes"], gs["apples"])


def test_engine_rejected_action_kills_snake_and_rounds_keep_resolving():
    env = _fresh(num_players=3, width=10, height=10, num_apples=0)

    done, _ = env.step("x" * (env.max_action_chars + 1))

    assert not done
    assert env.state.eliminated == [0]
    assert not env.state.game_state["snakes"][0].alive
    assert env.state.current_player_id == 1
    env.step("up")
    env.step("up")
    assert env.state.game_state["round_count"] == 1


def test_invalid_move_uses_engine_escalation_bookkeeping():
    env = _fresh(num_players=3, width=5, height=5, num_apples=0)

    done, _ = env.step("north")

    assert not done
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.state.game_info[0]["turn_count"] == 0
    death = [m for _, m, _, to in env.state.events if m.startswith("Snake 0 died")]
    assert death and "up, down, left or right" in death[0]


def test_fatal_action_by_last_submitter_resolves_the_pending_round():
    env = _fresh(num_players=3, width=7, height=7, num_apples=0)
    _place(env, {0: [(1, 1)], 1: [(3, 3)], 2: [(5, 5)]})
    env.step("up")
    env.step("up")

    done, _ = env.step(None)

    assert not done
    gs = env.state.game_state
    assert gs["round_count"] == 1
    assert gs["snakes"][0].head == (1, 2) and gs["snakes"][1].head == (3, 4)
    assert env.state.current_player_id == 0


def test_apples_are_distinguishable_from_two_digit_player_heads():
    env = _fresh(num_players=11, width=10, height=10, num_apples=3)
    board = env.state.game_state["board_state"]

    assert board.count("A") == 1  # snake 10's head
    assert board.count("*") == 3
    assert "'A'" in env.prompt(10)


def test_round_results_reveal_moves_and_deaths_only_after_resolution():
    env = _fresh(num_players=3, width=5, height=5, num_apples=0)
    _place(env, {0: [(0, 0)], 1: [(2, 2)], 2: [(4, 4)]}, apples=[(2, 3)])
    env.step("left")
    env.step("up")
    assert not any("Snake 0 moved" in m for _, m, _, _ in env.state.events)

    env.step("down")

    summary = [m for _, m, _, to in env.state.events if m.startswith("Round 1 results") and to == -1]
    assert len(summary) == 1
    assert "Snake 0 moved left and died (hit the wall)" in summary[0]
    assert "Snake 1 moved up and ate an apple" in summary[0]
    assert "Snake 2 moved down." in summary[0]


def test_render_reports_round_scores_and_dead_snakes():
    env = _fresh(num_players=3, width=5, height=5, num_apples=0)
    env.step("nonsense")

    board = env.render(1)

    assert "Rounds played: 0/100" in board
    assert "Snake 1 (you) [1]: length 1, score 0" in board
    assert "Snake 0: died in round 1 (invalid move), score 0" in board


def test_last_survivor_wins_without_resolving_its_pending_move():
    env = _fresh(num_players=2, width=5, height=5, num_apples=0)
    _place(env, {0: [(0, 0)], 1: [(3, 3)]})
    env.step("left")  # would hit the wall if the round were resolved

    done, _ = env.step("sideways")

    assert done
    assert env.state.rewards == {0: 1.0, 1: -1.0}
    assert env.state.game_state["snakes"][0].alive
