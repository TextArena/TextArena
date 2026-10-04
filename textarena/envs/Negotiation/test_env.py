"""Offline deterministic tests for the Negotiation environment.

Negotiation is rule-driven (no LLM needed); starting resources and personal
valuations are seeded, so trades and the turn-limit endgame can be scripted
deterministically.
"""
import copy

import pytest

from textarena.envs.Negotiation.env import NegotiationEnv


def _fresh(num_players=3, turn_multiple=3, seed=42):
    env = NegotiationEnv(turn_multiple=turn_multiple)
    env.reset(num_players=num_players, seed=seed)
    return env


def test_invalid_player_count_raises():
    env = NegotiationEnv()
    with pytest.raises(ValueError):
        env.reset(num_players=1, seed=42)
    with pytest.raises(ValueError):
        env.reset(num_players=16, seed=42)


def test_reset_initial_state():
    env = _fresh(num_players=3, turn_multiple=3)
    gs = env.state.game_state
    assert env.state.max_turns == 9  # num_players * turn_multiple
    assert env.state.current_player_id == 0
    assert gs["pending_offers"] == {}
    for pid in range(3):
        for r in env.resource_names:
            assert 5 <= gs["player_resources"][pid][r] <= 25
            assert 5 <= gs["player_values"][pid][r] <= 40


def test_offer_creates_pending_offer_and_rotates():
    env = _fresh()
    done, _ = env.step("Offer to 1: 2 Wheat -> 1 Ore")
    assert not done
    gs = env.state.game_state
    assert gs["pending_offers"] == {
        1: {"from": 0, "to": 1, "offered_resources": {"Wheat": 2}, "requested_resources": {"Ore": 1}}
    }
    p1_messages = [message for _, message, _ in env.state.observations[1]]
    p2_messages = [message for _, message, _ in env.state.observations[2]]
    assert any("2 Wheat -> 1 Ore" in message for message in p1_messages)
    assert not any("2 Wheat -> 1 Ore" in message for message in p2_messages)
    assert env.state.current_player_id == 1


def test_bare_commands_can_be_combined_on_separate_lines():
    env = _fresh()
    done, _ = env.step("Broadcast: I can trade Wheat\nOffer to 1: 2 Wheat -> 1 Ore")
    assert not done
    assert env.state.game_state["pending_offers"][1]["to"] == 1


def test_unrecognized_text_rejects_the_entire_action_atomically():
    env = _fresh()
    resources_before = {
        pid: dict(resources)
        for pid, resources in env.game_state["player_resources"].items()
    }

    done, _ = env.step("Broadcast: valid message\nthis is not a command")

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.game_state["player_resources"] == resources_before
    assert env.game_state["pending_offers"] == {}


def test_multiple_bare_offers_can_be_semicolon_separated():
    env = _fresh()
    done, _ = env.step(
        "Offer to 1: 1 Wheat -> 1 Ore; Offer to 2: 1 Wood -> 1 Brick"
    )
    assert not done
    assert set(env.state.game_state["pending_offers"]) == {1, 2}


def test_accept_executes_trade():
    env = _fresh()
    gs = env.state.game_state
    before = {pid: dict(gs["player_resources"][pid]) for pid in range(3)}

    env.step("Offer to 1: 2 Wheat -> 1 Ore")
    done, _ = env.step("Accept #1")
    assert not done

    res = gs["player_resources"]
    assert res[0]["Wheat"] == before[0]["Wheat"] - 2
    assert res[0]["Ore"] == before[0]["Ore"] + 1
    assert res[1]["Wheat"] == before[1]["Wheat"] + 2
    assert res[1]["Ore"] == before[1]["Ore"] - 1
    # Player 2 untouched, offer consumed.
    assert res[2] == before[2]
    assert gs["pending_offers"] == {}


def test_deny_removes_offer_without_trade():
    env = _fresh()
    gs = env.state.game_state
    before = {pid: dict(gs["player_resources"][pid]) for pid in range(3)}

    env.step("Offer to 1: 2 Wheat -> 1 Ore")
    done, _ = env.step("Deny #1")
    assert not done
    assert gs["pending_offers"] == {}
    assert gs["player_resources"] == before


def test_malformed_offer_rejected():
    env = _fresh()
    done, _ = env.step("Offer to 1: some nonsense")  # missing '->'
    assert not done
    assert env.state.error_count == 1
    # No rotation off the player after a single invalid move.
    assert env.state.current_player_id == 0


def test_offer_exceeding_resources_rejected():
    env = _fresh()
    done, _ = env.step("Offer to 1: 999 Ore -> 1 Wheat")  # holdings are 5..25
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state["pending_offers"] == {}


def test_self_offer_is_rejected():
    env = _fresh()
    done, _ = env.step("Offer to 0: 1 Wheat -> 1 Wood")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.game_state["pending_offers"] == {}


def test_self_whisper_rejects_all_mixed_effects_atomically():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    events_before = len(env.state.events)
    done, _ = env.step("Broadcast: hello\nWhisper 0: private")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before
    assert not any(
        "(Broadcast)" in message
        for _, message, _, _ in env.state.events[events_before:]
    )


@pytest.mark.parametrize(
    "action",
    ["[Whisper 1 missing colon]", "[Accept nope]", "[Broadcast:]"],
)
def test_malformed_legacy_commands_are_rejected(action):
    env = _fresh()
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_accepting_unaddressed_offer_rejected():
    env = _fresh()
    env.step("Offer to 2: 1 Wheat -> 1 Wood")  # offer #1, addressed to player 2
    done, _ = env.step("Accept #1")  # player 1 tries to accept it
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1
    assert 1 in env.state.game_state["pending_offers"]  # offer still pending

    # Player 1 recovers with a valid action, then player 2 can accept.
    done, _ = env.step("Broadcast: sorry, my bad")
    assert env.state.current_player_id == 2
    done, _ = env.step("Accept #1")
    assert not done
    assert env.state.game_state["pending_offers"] == {}


def test_incidental_accept_in_prose_does_not_accept_offer():
    env = _fresh()
    env.step("Offer to 1: 1 Wheat -> 1 Wood")
    done, _ = env.step("I cannot accept that trade right now.")
    assert not done
    assert 1 in env.state.game_state["pending_offers"]
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1


def _expected_rewards(env):
    gs = env.state.game_state
    values = {pid: env._calculate_inventory_value(pid, gs) for pid in range(env.state.num_players)}
    best = max(values.values())
    winners = [p for p, v in values.items() if v == best]
    if len(winners) == 1:
        return {p: (1 if p in winners else -1) for p in range(env.state.num_players)}
    return {p: 0 for p in range(env.state.num_players)}


def test_turn_limit_ends_game_with_portfolio_winner():
    env = _fresh(num_players=2, turn_multiple=3)  # 6 total turns
    done = False
    for turn in range(6):
        assert not done
        done, _ = env.step("Broadcast: just chatting")
    assert done
    assert env.state.rewards == _expected_rewards(env)


def test_trade_then_turn_limit_winner():
    env = _fresh(num_players=2, turn_multiple=3)  # 6 total turns
    gs = env.state.game_state
    before = dict(gs["player_resources"][0])
    done, _ = env.step("Offer to 1: 1 Wheat -> 1 Brick")
    done, _ = env.step("Accept #1")
    assert gs["player_resources"][0]["Brick"] == before["Brick"] + 1
    for _ in range(4):
        assert not done
        done, _ = env.step("Broadcast: hold your positions")
    assert done
    assert env.state.rewards == _expected_rewards(env)


@pytest.mark.parametrize("turn_multiple", [0, -1, True, 1.5])
def test_invalid_turn_multiple_is_rejected(turn_multiple):
    with pytest.raises(ValueError):
        NegotiationEnv(turn_multiple=turn_multiple)
