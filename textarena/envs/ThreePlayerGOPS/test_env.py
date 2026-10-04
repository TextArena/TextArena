"""Offline, deterministic tests for the Three-Player GOPS environment.

GOPS (Game of Pure Strategy) for exactly 3 players. Each player holds cards A-K
once each; a prize card is auctioned each round and the highest bid wins it
(ties roll the pot over). We drive a fully deterministic game where all three
players bid the same value every round, producing 13 ties, zero scores, and a
triple-tie outcome (all rewards 0).
"""

import textarena as ta
from textarena.envs.ThreePlayerGOPS.env import ThreePlayerGOPSEnv


def _fresh():
    env = ThreePlayerGOPSEnv()
    env.reset(num_players=3, seed=42)
    return env


_FACES = {1: "A", 11: "J", 12: "Q", 13: "K"}


def _face(v):
    return _FACES.get(v, str(v))


def test_reset_requires_three_players():
    import pytest

    env = ThreePlayerGOPSEnv()
    for num_players in (2, 4):
        with pytest.raises(AssertionError):
            env.reset(num_players=num_players, seed=42)


def test_reset_structure():
    env = _fresh()
    gs = env.state.game_state
    assert gs["round"] == 1
    assert len(gs["prize_deck"]) == 13
    assert all(len(gs["player_hands"][p]) == 13 for p in range(3))
    assert gs["player_scores"] == {0: 0, 1: 0, 2: 0}


def test_single_bid_records_and_rotates():
    env = _fresh()
    done, _ = env.step("A")
    assert not done
    assert env.state.game_state["pending_bids"] == {0: 1}
    assert 1 not in env.state.game_state["player_hands"][0]  # card A removed
    assert env.state.current_player_id == 1


def test_bid_is_private_until_every_alive_player_has_acted():
    env = _fresh()
    env.step("A")
    action_events = [event for event in env.state.events if event[2] == ta.ObservationType.PLAYER_ACTION]
    assert action_events == [(0, "A", ta.ObservationType.PLAYER_ACTION, 0)]
    assert not any("Bids »" in message for _, message, _, _ in env.state.events)


def test_malformed_bid_is_atomic():
    env = _fresh()
    before_hand = env.state.game_state["player_hands"][0].copy()
    done, _ = env.step("A K")
    assert not done
    assert env.state.game_state["pending_bids"] == {}
    assert env.state.game_state["player_hands"][0] == before_hand
    assert env.state.current_player_id == 0


def test_all_tie_game_ends_in_triple_draw():
    env = _fresh()
    done = False
    for v in range(1, 14):
        for _ in range(3):
            done, _ = env.step(_face(v))
    assert done
    assert env.state.game_state["player_scores"] == {0: 0, 1: 0, 2: 0}
    assert env.state.rewards == {0: 0, 1: 0, 2: 0}


def test_eliminated_player_cannot_share_final_draw_reward():
    env = _fresh()
    env.step("invalid")
    env.step("invalid")
    assert env.state.eliminated == [0]
    for value in range(1, 14):
        env.step(_face(value))
        done, _ = env.step(_face(value))
    assert done
    assert env.state.rewards == {0: -1, 1: 0, 2: 0}


def test_repeat_reset_and_snapshot_restore_sealed_round_state():
    env = _fresh()
    original_deck = env.state.game_state["prize_deck"].copy()
    env.step("A")
    snap = env.snapshot()
    env.step("2")
    env.restore(snap)
    assert env.state.game_state["pending_bids"] == {0: 1}
    assert env.state.current_player_id == 1
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["prize_deck"] == original_deck
    assert env.state.game_state["pending_bids"] == {}


def test_repeated_invalid_eliminates_player():
    env = _fresh()
    done, _ = env.step("z")  # unparsable card
    assert not done
    assert env.state.error_count == 1
    assert env.state.is_player_alive(0)
    done, _ = env.step("z")  # second consecutive invalid -> elimination
    assert not done  # two players remain, game continues
    assert not env.state.is_player_alive(0)
    assert env.state.current_player_id != 0


def test_eliminating_final_bidder_resolves_survivors_without_rebidding():
    env = _fresh()
    first_prize = env.state.game_state["current_prize"]
    env.step("A")  # P0's sealed bid.
    env.step("2")  # P1's sealed bid.
    env.step("bad")
    done, _ = env.step("still bad")  # P2 forfeits before bidding.

    gs = env.state.game_state
    assert not done
    assert env.state.eliminated == [2]
    assert gs["round"] == 2
    assert gs["pending_bids"] == {}
    assert gs["player_scores"][1] == first_prize
    assert gs["player_hands"][0] == list(range(2, 14))
    assert gs["player_hands"][1] == [1] + list(range(3, 14))
    assert env.state.current_player_id == 0
