"""Offline, deterministic tests for the Three-Player Iterated Prisoner's Dilemma.

Each round has a free-chat phase followed by a decision phase where every player
submits one token per opponent (``<id> cooperate`` / ``<id> defect``, brackets
tolerated; the default is cooperate). We shrink the game to a single round with one chat turn to
reach terminal quickly. Rewards are rank-based across players in [-1, +1].
"""

import pytest
import textarena as ta
from textarena.envs.ThreePlayerIPD.env import ThreePlayerIPDEnv


def _fresh(num_rounds=1, communication_turns=1):
    env = ThreePlayerIPDEnv(num_rounds=num_rounds, communication_turns=communication_turns)
    env.reset(num_players=3, seed=42)
    return env


def test_reset_requires_three_players():
    env = ThreePlayerIPDEnv()
    for num_players in (2, 4):
        with pytest.raises(AssertionError):
            env.reset(num_players=num_players, seed=42)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_rounds": 0},
        {"num_rounds": True},
        {"communication_turns": -1},
        {"communication_turns": 1.5},
    ],
)
def test_constructor_rejects_invalid_round_counts(kwargs):
    with pytest.raises(ValueError):
        ThreePlayerIPDEnv(**kwargs)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"cooperate_reward": "3"},
        {"defect_reward": True},
        {"sucker_reward": float("nan")},
        {"mutual_defect_reward": float("inf")},
    ],
)
def test_constructor_rejects_non_numeric_or_non_finite_payoffs(kwargs):
    with pytest.raises(ValueError, match="finite numbers"):
        ThreePlayerIPDEnv(**kwargs)


def test_conversation_then_decision_phase_transition():
    env = _fresh()
    assert env.state.game_state["phase"] == "conversation"
    for _ in range(3):  # one chat round = 3 speaker turns
        env.step("hello")
    assert env.state.game_state["phase"] == "decision"
    assert env.state.current_player_id == 0


def test_zero_communication_turns_starts_in_decision_phase():
    env = _fresh(communication_turns=0)
    assert env.state.game_state["phase"] == "decision"
    assert env.state.current_player_id == 0


def test_all_cooperate_is_full_draw():
    env = _fresh()
    for _ in range(3):
        env.step("let's cooperate")
    done = False
    for msg in ["1 cooperate 2 cooperate", "0 cooperate 2 cooperate", "0 cooperate 1 cooperate"]:
        done, _ = env.step(msg)
    assert done
    assert env.state.game_state["scores"] == {0: 6, 1: 6, 2: 6}
    assert env.state.rewards == {0: 0.0, 1: 0.0, 2: 0.0}


def test_unspecified_opponent_defaults_to_cooperate():
    env = _fresh(communication_turns=0)
    env.step("1 defect")  # P0 defaults to cooperate against P2.
    env.step("")          # P1 cooperates with both by default.
    done, _ = env.step("")
    assert done
    assert env.state.game_state["scores"] == {0: 8, 1: 3, 2: 6}
    assert env.state.rewards == {0: 1.0, 1: -1.0, 2: 0.0}


def test_balanced_bracketed_decision_tokens_are_accepted():
    env = _fresh(communication_turns=0)

    done, _ = env.step("[1 defect] [2 cooperate]")

    assert not done
    assert env.state.game_state["decisions"][0] == {1: "defect", 2: "cooperate"}
    assert env.state.current_player_id == 1


@pytest.mark.parametrize(
    "action",
    [
        "1 defect 1 cooperate",
        "0 defect",
        "9 defect",
        f"{'9' * 10_000} defect",
        "1 defect and 2 cooperate",
        "1 defect2 cooperate",
        "[1 defect][2 cooperate]",
        "1 defect 2 cooperate;",
        "[1 defect",
        "1 defect]",
    ],
)
def test_malformed_compound_decision_is_invalid_and_atomic(action):
    env = _fresh(communication_turns=0)
    before = env.state.game_state["decisions"][0].copy()
    done, _ = env.step(action)
    assert not done
    assert env.state.game_state["decisions"][0] == before
    assert env.state.game_state["acted"][0] is False
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_repeated_invalid_decision_forfeits_instead_of_breaking_pair_queue():
    env = _fresh(communication_turns=0)
    env.step("malformed")
    done, _ = env.step("still malformed")
    assert done
    assert env.state.rewards == {0: -1, 1: 1, 2: 1}
    assert env.state.eliminated == []


def test_decision_remains_private_until_round_resolution():
    env = _fresh(communication_turns=0)
    before_events = len(env.state.events)
    env.step("1 defect 2 cooperate")
    new_events = env.state.events[before_events:]
    assert [event for event in new_events if event[2] == ta.ObservationType.PLAYER_ACTION] == [
        (0, "1 defect 2 cooperate", ta.ObservationType.PLAYER_ACTION, 0)
    ]
    assert not any("Results:" in message for _, message, _, _ in new_events)


def test_lone_defector_wins():
    env = _fresh()
    for _ in range(3):
        env.step("chatter")
    done, _ = env.step("1 defect 2 defect")   # P0 defects on both
    assert not done
    done, _ = env.step("0 cooperate 2 cooperate")  # P1 cooperates
    assert not done
    done, _ = env.step("0 cooperate 1 cooperate")  # P2 cooperates
    assert done
    # P0: 5+5=10, P1: 0+3=3, P2: 0+3=3.
    assert env.state.game_state["scores"] == {0: 10, 1: 3, 2: 3}
    assert env.state.rewards == {0: 1.0, 1: -1.0, 2: -1.0}


def test_snapshot_restore_rewinds_pending_private_decisions():
    env = _fresh(communication_turns=0)
    env.step("1 defect 2 cooperate")
    snap = env.snapshot()
    env.step("0 cooperate 2 cooperate")
    env.restore(snap)
    assert env.state.current_player_id == 1
    assert env.state.game_state["acted"] == {0: True, 1: False, 2: False}
    assert env.state.game_state["decisions"][1] == {0: None, 2: None}
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["round"] == 1
    assert env.state.game_state["phase"] == "decision"
