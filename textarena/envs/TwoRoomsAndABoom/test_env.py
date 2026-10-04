"""Offline deterministic tests for the TwoRoomsAndABoom environment.

TwoRoomsAndABoom is rule-driven (no LLM needed); role assignment, room split
and turn order are seeded, so we can read hidden roles from game_state and
script deterministic phase transitions and full games.
"""
import copy

import pytest

import textarena as ta
from textarena.envs.TwoRoomsAndABoom.env import TwoRoomsAndABoomEnv


def _fresh(num_players=6, num_rounds=1, discussion_rounds=1, seed=42):
    env = TwoRoomsAndABoomEnv(num_rounds=num_rounds, discussion_rounds=discussion_rounds)
    env.reset(num_players=num_players, seed=seed)
    return env


def _special_pids(env):
    roles = env.state.game_state["player_roles"]
    president = next(p for p, r in roles.items() if r == "President")
    bomber = next(p for p, r in roles.items() if r == "Bomber")
    return president, bomber


def _messages_since(env, player_id, start):
    return [
        message
        for _, message, _, to_id in env.state.events[start:]
        if to_id in (-1, player_id)
    ]


def _play_discussion(env, max_steps=100):
    """Play innocuous discussion turns until the phase changes."""
    steps = 0
    while env.state.game_state["current_phase"] == "Discussion" and steps < max_steps:
        done, _ = env.step("hello everyone")
        assert not done
        steps += 1
    return steps


def test_too_few_players_raises_error():
    env = TwoRoomsAndABoomEnv()
    with pytest.raises(AssertionError):
        env.reset(num_players=5, seed=42)  # minimum is 6


def test_too_many_players_raises_error():
    env = TwoRoomsAndABoomEnv()
    with pytest.raises(AssertionError):
        env.reset(num_players=21, seed=42)  # maximum is 20


def test_reset_assigns_roles_and_rooms():
    env = _fresh(6)
    gs = env.state.game_state
    roles = list(gs["player_roles"].values())
    assert roles.count("President") == 1
    assert roles.count("Bomber") == 1
    assert len(roles) == 6
    # Every player is in exactly one room.
    assert sorted(gs["rooms"][0] + gs["rooms"][1]) == list(range(6))
    # President and Bomber start in different rooms.
    president, bomber = _special_pids(env)
    assert (president in gs["rooms"][0]) != (bomber in gs["rooms"][0])
    # Each room has a leader who is inside that room.
    for room_idx in range(2):
        assert gs["leaders"][room_idx] in gs["rooms"][room_idx]
    assert gs["current_phase"] == "Discussion"
    assert gs["round"] == 1
    # The first player to act is in a room.
    assert env.state.current_player_id in gs["rooms"][0] + gs["rooms"][1]


def test_cards_per_room_is_enforced_and_controls_room_size():
    with pytest.raises(ValueError, match="requires exactly 6 players"):
        TwoRoomsAndABoomEnv(cards_per_room=3).reset(num_players=8, seed=42)

    env = TwoRoomsAndABoomEnv(cards_per_room=4)
    env.reset(num_players=8, seed=42)
    assert [len(room) for room in env.state.game_state["rooms"]] == [4, 4]

    for cards_per_room in (0, 1, 11, True, 1.5):
        with pytest.raises(ValueError, match="between 3 and 10"):
            TwoRoomsAndABoomEnv(cards_per_room=cards_per_room)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_rounds": 0},
        {"num_rounds": True},
        {"num_rounds": 1.5},
        {"discussion_rounds": -1},
        {"discussion_rounds": True},
        {"discussion_rounds": 1.5},
    ],
)
def test_round_configuration_requires_bounded_integers(kwargs):
    with pytest.raises(ValueError):
        TwoRoomsAndABoomEnv(**kwargs)


def test_zero_discussion_rounds_and_maximum_player_count_are_supported():
    env = TwoRoomsAndABoomEnv(
        num_rounds=1,
        cards_per_room=10,
        discussion_rounds=0,
    )
    env.reset(num_players=20, seed=42)

    gs = env.game_state
    assert [len(room) for room in gs["rooms"]] == [10, 10]
    assert gs["current_phase"] == "Leader_Selection"
    assert env.state.current_player_id in gs["leaders"]


def test_role_assignment_is_balanced_randomized_and_seeded():
    team_by_seed = []
    for seed in range(64):
        env = _fresh(seed=seed)
        roles = env.state.game_state["player_roles"]
        teams = tuple(env.ROLES[roles[pid]]["team"] for pid in range(6))
        assert teams.count("Red Team") == 3
        assert teams.count("Blue Team") == 3
        assert list(roles.values()).count("President") == 1
        assert list(roles.values()).count("Bomber") == 1
        team_by_seed.append(teams)

    # No player ID is permanently tied to either team across seeds.
    for pid in range(6):
        assert {teams[pid] for teams in team_by_seed} == {"Red Team", "Blue Team"}

    env_a = _fresh(seed=777)
    env_b = _fresh(seed=777)
    assert env_a.state.game_state["player_roles"] == env_b.state.game_state["player_roles"]
    assert env_a.state.game_state["rooms"] == env_b.state.game_state["rooms"]
    assert env_a.state.game_state["leaders"] == env_b.state.game_state["leaders"]


def test_secret_roles_are_recorded_in_game_info():
    env = _fresh(seed=9)
    roles = env.state.game_state["player_roles"]
    assert {pid: info["role"] for pid, info in env.state.game_info.items()} == roles


def test_discussion_progresses_to_leader_selection():
    env = _fresh(6, discussion_rounds=1)
    # With 1 discussion round each of the 6 players speaks exactly once.
    steps = _play_discussion(env)
    assert steps == 6
    gs = env.state.game_state
    assert gs["current_phase"] == "Leader_Selection"
    # The player to act now is one of the room leaders.
    assert env.state.current_player_id in gs["leaders"]


def test_role_reveal_flow():
    env = _fresh(6)
    gs = env.state.game_state
    revealer = env.state.current_player_id
    room_idx = 0 if revealer in gs["rooms"][0] else 1
    target = next(p for p in gs["rooms"][room_idx] if p != revealer)

    done, _ = env.step("I want to reveal card")
    assert not done
    assert gs["current_phase"] == "Role_Reveal"
    # The revealing player selects the target themselves.
    assert env.state.current_player_id == revealer

    done, _ = env.step(f"Player {target}")
    assert not done
    assert revealer in gs["revealed_roles"][target]
    assert gs["reveal_counts"][revealer] == 1
    # Back to discussion after the reveal.
    assert gs["current_phase"] == "Discussion"


def test_huge_nonmatching_reveal_message_is_processed_without_backtracking():
    env = _fresh(seed=7, discussion_rounds=1)
    gs = env.game_state
    speaker = env.state.current_player_id
    room_idx = 0 if speaker in gs["rooms"][0] else 1
    action = ("reveal " * 4_000) + "nothing"

    done, _ = env.step(action)

    assert not done
    assert gs["current_phase"] == "Discussion"
    assert gs["revealing_player"] is None
    assert gs["message_history"][str(room_idx)][-1]["message"] == action


def test_ordinary_discussion_does_not_disclose_hidden_roles():
    env = _fresh(seed=11)
    gs = env.state.game_state
    speaker = env.state.current_player_id
    room_idx = 0 if speaker in gs["rooms"][0] else 1
    start = len(env.state.events)

    assert env._handle_discussion(speaker, "The weather is calm.") is None

    true_role = gs["player_roles"][speaker]
    for listener in gs["rooms"][room_idx]:
        messages = "\n".join(_messages_since(env, listener, start))
        assert "[TEAM INFO]" not in messages
        assert f"Player {speaker} ({true_role})" not in messages
        assert f"Player {speaker}: {true_role}" not in messages
        assert f"Their true role is: {true_role}" not in messages


def test_reveal_is_private_and_preserves_discussion_schedule():
    env = _fresh(seed=17, discussion_rounds=2)
    gs = env.state.game_state
    revealer = env.state.current_player_id
    room_idx = 0 if revealer in gs["rooms"][0] else 1
    target = next(pid for pid in gs["rooms"][room_idx] if pid != revealer)
    non_target = next(pid for pid in gs["rooms"][room_idx] if pid not in (revealer, target))
    expected_remaining = list(gs["next_player_ids"])
    start = len(env.state.events)

    done, _ = env.step("show role")
    assert not done
    assert gs["current_phase"] == "Role_Reveal"
    assert gs["paused_discussion_player_ids"] == expected_remaining

    done, _ = env.step(str(target))
    assert not done
    assert gs["current_phase"] == "Discussion"
    assert gs["paused_discussion_player_ids"] is None
    assert env.state.current_player_id == expected_remaining[0]
    assert gs["next_player_ids"] == expected_remaining[1:]

    true_role = gs["player_roles"][revealer]
    assert f"Their true role is: {true_role}" in "\n".join(
        _messages_since(env, target, start)
    )
    assert f"Their true role is: {true_role}" not in "\n".join(
        _messages_since(env, non_target, start)
    )


def test_self_reveal_is_invalid_and_atomic():
    env = _fresh(seed=23)
    gs = env.state.game_state
    revealer = env.state.current_player_id
    done, _ = env.step("reveal card")
    assert not done
    before = copy.deepcopy(gs)

    done, _ = env.step(str(revealer))

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == revealer
    assert gs == before


def test_repeated_invalid_reveal_resumes_exact_paused_discussion_queue():
    env = _fresh(seed=29, discussion_rounds=2)
    gs = env.game_state
    revealer = env.state.current_player_id
    expected_remaining = list(gs["next_player_ids"])
    env.step("reveal card")

    env.step("not a player")
    done, _ = env.step("still not a player")

    assert not done
    assert gs["current_phase"] == "Discussion"
    assert gs["revealing_player"] is None
    assert gs["paused_discussion_player_ids"] is None
    assert env.state.current_player_id == expected_remaining[0]
    assert gs["next_player_ids"] == expected_remaining[1:]
    assert gs["reveal_counts"][revealer] == 0


def test_incoming_hostage_cannot_see_prior_room_history():
    env = _fresh(seed=31, num_rounds=2)
    gs = env.state.game_state
    outgoing = next(pid for pid in gs["rooms"][0] if pid != gs["leaders"][0])
    incoming = next(pid for pid in gs["rooms"][1] if pid != gs["leaders"][1])
    witness = gs["leaders"][0]
    secret = "ROOM-ZERO-ONLY-7391"

    assert env._handle_discussion(outgoing, secret) is None
    gs["rooms"][0].remove(outgoing)
    gs["rooms"][1].remove(incoming)
    gs["rooms"][0].append(incoming)
    gs["rooms"][1].append(outgoing)
    gs["round"] = 2
    start = len(env.state.events)

    env._phase_transition_player_prompts(new_phase="Discussion")

    assert secret not in "\n".join(_messages_since(env, incoming, start))
    assert secret in "\n".join(_messages_since(env, witness, start))


def test_corrupted_state_ends_safely_without_mutating_game_state():
    env = _fresh(seed=37)
    gs = env.state.game_state
    player_id = env.state.current_player_id
    room_idx = 0 if player_id in gs["rooms"][0] else 1
    gs["rooms"][room_idx].remove(player_id)
    corrupted_state = copy.deepcopy(gs)

    result = env.apply(player_id, "hello")

    assert isinstance(result, ta.Outcome)
    assert set(result.rewards.values()) == {0}
    assert "invalid state" in result.reason
    assert gs == corrupted_state


def test_invalid_reveal_selection_is_atomic():
    env = _fresh(seed=41)
    revealer = env.state.current_player_id
    done, _ = env.step("reveal role")
    assert not done
    before = copy.deepcopy(env.state.game_state)

    result = env.apply(revealer, "not a player")

    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_leader_invalid_format_rejected_then_valid_selection():
    env = _fresh(6, discussion_rounds=1)
    _play_discussion(env)
    gs = env.state.game_state
    leader = env.state.current_player_id
    room_idx = gs["leaders"].index(leader)

    done, _ = env.step("I refuse to pick anyone")  # not a player-number selection
    assert not done
    assert env.state.error_count == 1
    # No rotation off the player after a single invalid move.
    assert env.state.current_player_id == leader

    choice = next(p for p in gs["rooms"][room_idx] if p != leader)
    done, _ = env.step(str(choice))
    assert not done
    assert gs["hostages_to_trade"][room_idx] == choice
    # Play moved on to the other leader.
    assert env.state.current_player_id != leader


def test_leader_cannot_select_self():
    env = _fresh(6, discussion_rounds=1)
    _play_discussion(env)
    leader = env.state.current_player_id
    done, _ = env.step(str(leader))  # illegal: self-selection
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == leader


def test_red_team_wins_when_president_traded_to_bomber_room():
    env = _fresh(6, num_rounds=1, discussion_rounds=1)
    gs = env.state.game_state
    president, bomber = _special_pids(env)
    _play_discussion(env)

    done = False
    while not done and gs["current_phase"] == "Leader_Selection":
        leader = env.state.current_player_id
        room_idx = gs["leaders"].index(leader)
        if president in gs["rooms"][room_idx]:
            choice = president  # ship the President to the Bomber's room
        else:
            choice = next(p for p in gs["rooms"][room_idx] if p not in (leader, bomber))
        done, _ = env.step(str(choice))

    assert done
    # President and Bomber ended in the same room -> Red team wins.
    roles = gs["player_roles"]
    expected = {p: (1 if roles[p] in ("Red", "Bomber") else -1) for p in range(6)}
    assert env.state.rewards == expected


def test_blue_team_wins_when_specials_stay_separated():
    env = _fresh(6, num_rounds=1, discussion_rounds=1)
    gs = env.state.game_state
    president, bomber = _special_pids(env)
    _play_discussion(env)

    done = False
    while not done and gs["current_phase"] == "Leader_Selection":
        leader = env.state.current_player_id
        room_idx = gs["leaders"].index(leader)
        # Trade only regular players so President and Bomber stay put.
        choice = next(p for p in gs["rooms"][room_idx] if p not in (leader, president, bomber))
        done, _ = env.step(str(choice))

    assert done
    roles = gs["player_roles"]
    expected = {p: (1 if roles[p] in ("Blue", "President") else -1) for p in range(6)}
    assert env.state.rewards == expected


def test_trade_starts_next_round_with_fresh_room_valid_queue():
    env = _fresh(6, num_rounds=2, discussion_rounds=1, seed=53)
    gs = env.game_state
    _play_discussion(env)

    for _ in range(2):
        leader = env.state.current_player_id
        room_idx = gs["leaders"].index(leader)
        choice = next(pid for pid in gs["rooms"][room_idx] if pid != leader)
        done, _ = env.step(str(choice))
        assert not done

    assert gs["round"] == 2
    assert gs["current_phase"] == "Discussion"
    assert gs["hostages_to_trade"] == {}
    assert sorted(gs["rooms"][0] + gs["rooms"][1]) == list(range(6))
    assert env.state.current_player_id in gs["rooms"][0] + gs["rooms"][1]
    assert all(pid in gs["rooms"][0] + gs["rooms"][1] for pid in gs["next_player_ids"])


def test_snapshot_and_repeat_reset_restore_private_assignments_and_queue():
    env = _fresh(seed=61, num_rounds=2, discussion_rounds=2)
    initial_roles = env.game_state["player_roles"].copy()
    initial_rooms = copy.deepcopy(env.game_state["rooms"])
    initial_leaders = env.game_state["leaders"].copy()
    initial_actor = env.state.current_player_id
    initial_queue = env.game_state["next_player_ids"].copy()
    snap = env.snapshot()

    env.step("temporary discussion")
    env.restore(snap)

    assert env.game_state["player_roles"] == initial_roles
    assert env.game_state["rooms"] == initial_rooms
    assert env.game_state["leaders"] == initial_leaders
    assert env.state.current_player_id == initial_actor
    assert env.game_state["next_player_ids"] == initial_queue
    env.reset(num_players=6, seed=61)
    assert env.game_state["player_roles"] == initial_roles
    assert env.game_state["rooms"] == initial_rooms
    assert env.game_state["leaders"] == initial_leaders
