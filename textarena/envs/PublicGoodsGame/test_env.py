"""Deterministic offline tests for the PublicGoodsGame environment."""
import pytest
import textarena as ta

from textarena.envs.PublicGoodsGame.env import PublicGoodsGameEnv


def _fresh(num_players=2, **overrides):
    config = {
        "num_rounds": 1,
        "communication_turns": 1,
        "num_players": num_players,
        "endowment": 10,
        "multiplication_factor": 2.0,
    }
    config.update(overrides)
    env = PublicGoodsGameEnv(**config)
    env.reset(num_players=num_players, seed=42)
    return env


def _advance_to_decision(env):
    """Both players send one conversation message, moving to the decision phase."""
    env.step("{hello}")
    env.step("{hi there}")
    assert env.state.game_state["phase"] == "decision"


def test_reset_starts_in_conversation_phase():
    env = _fresh()
    assert env.state.game_state["phase"] == "conversation"
    assert env.state.game_state["round"] == 1
    assert env.state.num_players == 2


def test_conversation_advances_to_decision():
    env = _fresh()
    assert env.state.game_state["phase"] == "conversation"
    env.step("{let's cooperate}")
    # Not all players have spoken yet -> still conversation.
    assert env.state.game_state["phase"] == "conversation"
    env.step("{agreed}")
    assert env.state.game_state["phase"] == "decision"


def test_free_rider_beats_full_contributor():
    env = _fresh()
    _advance_to_decision(env)
    env.step("0")            # P0 keeps everything
    done, _ = env.step("10")  # P1 contributes fully
    assert done
    # P0 payoff = 10 kept + 10 share = 20; P1 = 0 kept + 10 share = 10.
    assert env.state.rewards == {0: 1, 1: -1}


def test_equal_contributions_tie():
    env = _fresh()
    _advance_to_decision(env)
    env.step("5")
    done, _ = env.step("5")
    assert done
    assert env.state.rewards == {0: 1, 1: 1}
    assert env.state.game_state["phase"] == "complete"
    assert "Game Complete" in env.get_board_str()
    assert "ROUND CALCULATION" in env.get_board_str()


def test_out_of_range_contribution_warns_before_elimination():
    env = _fresh()
    _advance_to_decision(env)
    done, _ = env.step("999")  # exceeds endowment; error_allowance is 2
    assert not done
    assert env.state.error_count == 1


def test_zero_communication_turns_starts_in_decision_phase():
    env = _fresh(communication_turns=0)
    assert env.state.game_state["phase"] == "decision"
    env.step("0")
    done, _ = env.step("10")
    assert done


def test_one_communication_cycle_rotates_three_player_queue_per_round():
    env = _fresh(num_players=3, num_rounds=2, communication_turns=1)
    for message, next_player in [
        ("{p0}", 1),
        ("{p1}", 2),
        ("{p2}", 0),
    ]:
        env.step(message)
        assert env.state.current_player_id == next_player
    assert env.state.game_state["phase"] == "decision"

    for contribution in ("0", "0", "0"):
        env.step(contribution)
    assert env.state.game_state["round"] == 2
    assert env.state.game_state["phase"] == "conversation"
    assert env.state.current_player_id == 0
    assert env.state.game_state["pending_messages"] == {}
    assert env.state.game_state["pending_contributions"] == {}


def test_pending_message_and_contribution_are_hidden_from_renderer():
    env = _fresh()
    env.step("{ultraviolet}")
    board = env.get_board_str()
    assert "ultraviolet" not in board
    assert "Submitted (hidden)" in board

    env = _fresh(communication_turns=0)
    env.step("7")
    board = env.get_board_str()
    assert "7 tokens" not in board
    assert "Submitted (hidden)" in board
    assert not any(
        event[0] == 0
        and event[2] == ta.ObservationType.PLAYER_ACTION
        and event[3] in (-1, 1)
        for event in env.state.events
    )


def test_partial_first_place_tie_penalizes_lower_score():
    env = _fresh(num_players=3, communication_turns=0)
    env.step("0")
    env.step("0")
    done, _ = env.step("10")
    assert done
    assert env.state.rewards == {0: 1, 1: 1, 2: -1}


def test_invalid_limit_eliminates_then_resolves_with_remaining_player():
    env = _fresh(communication_turns=0)
    env.step("999")
    env.step("999")
    done, _ = env.step("999")
    assert not done
    assert env.state.alive_players == [1]
    assert env.state.current_player_id == 1

    done, _ = env.step("0")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_extreme_finite_multiplier_preserves_exact_winner_math():
    env = _fresh(communication_turns=0, multiplication_factor=1e308)
    env.step("0")
    done, _ = env.step("10")
    assert done
    assert env.state.game_state["total_scores"][0] > env.state.game_state["total_scores"][1]
    assert env.state.rewards == {0: 1, 1: -1}
    assert "inf" not in env.get_board_str().lower()


def test_prompt_example_uses_configured_endowment():
    env = _fresh(endowment=5, multiplication_factor=2)
    prompt = env.prompt(0)
    assert "If everyone contributes 5 tokens:" in prompt
    assert "- Plus 0 tokens kept = 10.0 total" in prompt
    assert "contributes 10 tokens" not in prompt


def test_terminal_round_and_payoff_history_are_exact():
    env = _fresh(communication_turns=0)
    env.step("0")
    done, _ = env.step("10")
    assert done
    gs = env.state.game_state
    assert gs["round"] == 1
    assert gs["history"][0]["total_contribution"] == 10
    assert gs["history"][0]["public_good"] == 20.0
    assert gs["history"][0]["payoffs"] == {0: 20.0, 1: 10.0}
    assert env.state.turn == 2


def test_duplicate_contribution_is_rejected_without_overwrite():
    env = _fresh(communication_turns=0)
    env.step("3")
    result = env.apply(0, "9")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state["pending_contributions"][0] == 3


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_contribution_is_rejected_atomically(player_id):
    env = _fresh(communication_turns=0)
    before = env.state.game_state.copy()
    result = env.apply(player_id, "3")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_reset_clears_completed_game_state():
    env = _fresh(communication_turns=0)
    env.step("0")
    env.step("10")
    env.reset(num_players=2, seed=42)
    assert env.state.game_state["round"] == 1
    assert env.state.game_state["total_scores"] == {0: 0, 1: 0}
    assert env.state.game_state["history"] == []


def test_snapshot_restores_pending_message_and_queue_position():
    env = _fresh()
    env.step("private thought {public proposal}")
    snapshot = env.snapshot()
    env.step("{reply}")
    assert env.state.game_state["phase"] == "decision"

    env.restore(snapshot)
    assert env.state.current_player_id == 1
    assert env.state.game_state["phase"] == "conversation"
    assert env.state.game_state["pending_messages"] == {0: "public proposal"}
    assert "public proposal" not in env.get_board_str()
    env.step("{new reply}")
    assert env.state.game_state["phase"] == "decision"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_rounds": 0},
        {"communication_turns": -1},
        {"endowment": -1},
        {"multiplication_factor": float("inf")},
        {"multiplication_factor": -0.1},
        {"num_players": 1},
        {"num_rounds": 10**5000},
        {"endowment": 10**5000},
        {"multiplication_factor": 10**5000},
    ],
)
def test_invalid_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        PublicGoodsGameEnv(**kwargs)
