"""Offline deterministic tests for IteratedStagHunt.

Same conversation/decision cadence as IteratedPrisonersDilemma. Decision
submissions must be an exact ``stag`` or ``hare`` token.

Default payoffs (randomize_payoff=False):
- both stag  -> 10 each
- both hare  -> 5 each
- mixed      -> stag hunter 1, hare hunter 8

"""
import pytest
import textarena as ta

from textarena.envs.IteratedStagHunt.env import IteratedStagHuntEnv


def _fresh(num_rounds=1, conversation_rounds=1, **kwargs):
    env = IteratedStagHuntEnv(
        num_rounds=num_rounds,
        conversation_rounds=conversation_rounds,
        **kwargs,
    )
    env.reset(num_players=2, seed=42)
    return env


def _play_conversation(env, turns=1):
    for _ in range(turns):
        env.step("hello")   # player 0
        env.step("hi")      # player 1


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["phase"] == "conversation"
    assert gs["total_payoff"] == {0: 0, 1: 0}
    assert gs["round"] == 1
    assert env.state.current_player_id == 0


def test_conversation_then_decision_phase_switch():
    env = _fresh(num_rounds=1, conversation_rounds=1)
    _play_conversation(env, turns=1)
    assert env.state.game_state["phase"] == "decision"


def test_hare_hunter_beats_stag_hunter():
    env = _fresh(num_rounds=1, conversation_rounds=1)
    _play_conversation(env, turns=1)
    env.step("hare")          # player 0 -> hare (single_hare=8)
    done, _ = env.step("stag")  # player 1 -> stag (single_stag=1)
    assert done
    assert env.state.game_state["total_payoff"] == {0: 8, 1: 1}
    assert env.state.rewards == {0: 1, 1: -1}


def test_mutual_stag_is_draw():
    env = _fresh(num_rounds=1, conversation_rounds=1)
    _play_conversation(env, turns=1)
    env.step("stag")
    done, _ = env.step("stag")
    assert done
    assert env.state.game_state["total_payoff"] == {0: 10, 1: 10}
    assert env.state.rewards == {0: 0, 1: 0}
    assert env.state.game_state["phase"] == "complete"
    assert "Phase: complete" in env.get_board_str()


def test_malformed_decision_is_atomic_and_recoverable():
    env = _fresh(num_rounds=1, conversation_rounds=1)
    _play_conversation(env, turns=1)
    env.step("stag")
    done, _ = env.step("whatever")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1
    assert env.state.game_state["decisions"] == {0: "stag", 1: None}

    done, _ = env.step("hare")
    assert done
    assert env.state.game_state["total_payoff"] == {0: 1, 1: 8}
    assert env.state.rewards == {0: -1, 1: 1}


def test_reward_accumulation_across_rounds():
    env = _fresh(num_rounds=2, conversation_rounds=1)
    # Round 1: P0 hare (8), P1 stag (1)
    _play_conversation(env, turns=1)
    env.step("hare")
    env.step("stag")
    assert env.state.game_state["total_payoff"] == {0: 8, 1: 1}
    # Round 2: both hare -> +5 each
    _play_conversation(env, turns=1)
    env.step("hare")
    done, _ = env.step("hare")
    assert done
    assert env.state.game_state["total_payoff"] == {0: 13, 1: 6}
    assert env.state.rewards == {0: 1, 1: -1}


def test_zero_conversation_rounds_starts_in_decision_phase():
    env = _fresh(conversation_rounds=0)
    assert env.state.game_state["phase"] == "decision"
    env.step("stag")
    done, _ = env.step("hare")
    assert done


def test_pending_decision_is_not_revealed_to_opponent_or_renderer():
    env = _fresh(conversation_rounds=0)
    env.step("stag")
    leaked_events = [
        event
        for event in env.state.events
        if event[0] == 0
        and event[2] == ta.ObservationType.PLAYER_ACTION
        and event[3] in (-1, 1)
    ]
    assert leaked_events == []
    board = env.get_board_str()
    assert "Decisions submitted: Player 0" in board
    assert "P0 stag" not in board


def test_terminal_round_does_not_generate_phantom_payoffs():
    env = _fresh(conversation_rounds=0, randomize_payoff=True)
    initial_payoffs = env.state.game_state["payoffs"].copy()
    env.step("stag")
    done, _ = env.step("hare")
    assert done
    assert env.state.game_state["round"] == 1
    assert env.state.game_state["payoffs"] == initial_payoffs
    assert len(env.state.game_state["history"]) == 1
    assert not any("Starting Round 2" in event[1] for event in env.state.events)


def test_randomized_payoffs_replay_after_snapshot_restore():
    env = _fresh(num_rounds=2, conversation_rounds=0, randomize_payoff=True)
    snapshot = env.snapshot()
    env.step("stag")
    env.step("hare")
    second_matrix = env.state.game_state["payoffs"].copy()

    env.restore(snapshot)
    env.step("stag")
    env.step("hare")
    assert env.state.game_state["payoffs"] == second_matrix


def test_signed_randomized_payoffs_stay_ordered_across_rounds_and_reset():
    kwargs = {
        "num_rounds": 3,
        "conversation_rounds": 0,
        "randomize_payoff": True,
        "single_stag_reward": -10,
        "mutual_hare_reward": -5,
        "single_hare_reward": 0,
        "mutual_stag_reward": 5,
    }
    env = _fresh(**kwargs)
    first_matrix = env.state.game_state["payoffs"].copy()

    for _ in range(3):
        matrix = env.state.game_state["payoffs"]
        assert -10 < matrix["mutual_hare"] <= matrix["single_hare"]
        assert matrix["single_hare"] < matrix["mutual_stag"]
        env.step("stag")
        done, _ = env.step("hare")
    assert done
    assert len(env.state.game_state["history"]) == 3

    env.reset(num_players=2, seed=42)
    assert env.state.game_state["payoffs"] == first_matrix
    assert env.state.game_state["history"] == []


def test_duplicate_decision_is_rejected_without_overwrite():
    env = _fresh(conversation_rounds=0)
    env.step("stag")
    result = env.apply(0, "hare")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state["decisions"][0] == "stag"


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_decision_is_rejected_atomically(player_id):
    env = _fresh(conversation_rounds=0)
    before = env.state.game_state.copy()
    result = env.apply(player_id, "stag")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_rounds": 0},
        {"conversation_rounds": -1},
        {"randomize_payoff": 1},
        {
            "randomize_payoff": True,
            "single_stag_reward": 5,
            "mutual_hare_reward": 5,
        },
        {"num_rounds": 10**5000},
        {"mutual_stag_reward": 10**5000},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        IteratedStagHuntEnv(**kwargs)
