"""Deterministic offline tests for Liar's Dice.

FFA multiplayer game driven with two players and ``num_dice=1`` for short games.
Dice are rolled randomly; we read ``game_state['dice_rolls']`` to build bids
whose truth value is known, guaranteeing the caller/bidder outcome.

Final rewards use ``set_game_outcome`` with rank-scaled values; for 2 players the
loser gets -1.0 and the winner +1.0.
"""
import pytest

from textarena.envs.LiarsDice.env import LiarsDiceEnv


def _fresh(num_dice=1):
    env = LiarsDiceEnv(num_dice=num_dice)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    gs = env.state.game_state
    assert gs["current_bid"] == {"quantity": 0, "face_value": 0}
    assert set(gs["dice_rolls"].keys()) == {0, 1}


def test_true_bid_makes_caller_lose():
    env = _fresh()
    dice = env.state.game_state["dice_rolls"]
    face = dice[0][0]  # P0 owns this face, so quantity-1 bid is always true
    env.step(f"Bid: 1, {face}")   # P0 bids
    done, _ = env.step("Call")     # P1 calls a true bid -> P1 loses die
    assert done is True
    assert env.state.rewards == {0: 1.0, 1: -1.0}


def test_false_bid_makes_bidder_lose():
    env = _fresh()
    # Only 2 dice total, so quantity 3 is impossible -> a bluff.
    env.step("Bid: 3, 6")          # P0 bluffs
    done, _ = env.step("call")      # P1 calls the bluff -> P0 loses die
    assert done is True
    assert env.state.rewards == {0: -1.0, 1: 1.0}


def test_call_with_no_bid_invalid():
    env = _fresh()
    done, _ = env.step("Call")
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # not rotated on invalid


def test_bidder_cannot_call_own_bid_if_turn_state_is_tampered():
    env = _fresh(num_dice=2)
    env.step("Bid: 1, 2")
    env.state.current_player_id = 0
    remaining_before = dict(env.state.game_state["remaining_dice"])
    done, _ = env.step("Call")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["remaining_dice"] == remaining_before


def test_bid_not_higher_rejected():
    env = _fresh()
    env.step("Bid: 2, 6")          # P0 bids
    assert env.state.current_player_id == 1
    done, _ = env.step("Bid: 1, 1")  # lower quantity & face -> invalid
    assert done is False
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("let me think")
    assert done is False
    assert env.state.error_count == 1


def test_huge_bid_numbers_are_rejected_without_integer_parse_failure():
    env = _fresh()
    done, _ = env.step(f"Bid: {'9' * 5000}, 6")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_bid"] == {"quantity": 0, "face_value": 0}


def test_two_consecutive_invalids_eliminate():
    env = _fresh()
    env.step("Call")               # invalid #1 (no prior bid)
    done, _ = env.step("[Call]")      # invalid #2 (brackets tolerated) -> P0 eliminated, game ends
    assert done is True
    assert env.state.rewards == {0: -1.0, 1: 1.0}


def test_valid_bid_rotates_player():
    env = _fresh()
    done, _ = env.step("Bid: 1, 2")
    assert done is False
    assert env.state.game_state["current_bid"] == {"quantity": 1, "face_value": 2}
    assert env.state.game_state["last_bidder_id"] == 0
    assert env.state.current_player_id == 1


def test_zero_quantity_bid_is_rejected():
    env = _fresh()
    done, _ = env.step("Bid: 0, 1")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_bid"] == {"quantity": 0, "face_value": 0}


def test_higher_quantity_may_use_lower_face():
    env = _fresh(num_dice=2)
    env.step("Bid: 1, 6")
    done, _ = env.step("Bid: 2, 1")
    assert not done
    assert env.state.game_state["current_bid"] == {"quantity": 2, "face_value": 1}


def test_round_loser_starts_next_round():
    env = LiarsDiceEnv(num_dice=2)
    env.reset(num_players=3, seed=42)
    face = env.state.game_state["dice_rolls"][0][0]
    env.step(f"Bid: 1, {face}")
    done, _ = env.step("Call")
    assert not done
    assert env.state.game_state["remaining_dice"][1] == 1
    assert env.state.current_player_id == 1


def test_eliminated_player_is_not_rolled_or_rendered_next_round():
    env = LiarsDiceEnv(num_dice=1)
    env.reset(num_players=3, seed=42)
    env.step("Bid: 4, 6")
    done, _ = env.step("Call")
    assert not done
    assert 0 in env.state.eliminated
    assert set(env.state.game_state["dice_rolls"]) == {1, 2}
    assert env.state.current_player_id == 1


def test_renderer_hides_opponents_dice():
    env = _fresh()
    env.state.game_state["dice_rolls"] = {0: [1], 1: [6]}
    board = env.render(0)
    assert "│ 1 │" in board
    assert "│ 6 │" not in board
    assert "Player 1: 1 hidden die/dice" in board


def test_dice_count_is_conserved_each_round():
    env = LiarsDiceEnv(num_dice=3)
    env.reset(num_players=4, seed=42)
    gs = env.state.game_state
    assert sum(len(roll) for roll in gs["dice_rolls"].values()) == sum(gs["remaining_dice"].values()) == 12
    env.step("Bid: 13, 6")
    env.step("Call")
    assert sum(len(roll) for roll in gs["dice_rolls"].values()) == sum(gs["remaining_dice"].values()) == 11


def test_scripted_three_player_game_has_rank_scaled_rewards():
    env = LiarsDiceEnv(num_dice=1)
    env.reset(num_players=3, seed=42)
    env.step("Bid: 4, 6")
    done, _ = env.step("Call")
    assert not done and env.state.current_player_id == 1
    env.step("Bid: 3, 6")
    done, _ = env.step("Call")
    assert done
    assert env.state.eliminated == [0, 1]
    assert env.state.rewards == {0: -1.0, 1: 0.0, 2: 1.0}


def test_repeat_reset_replays_private_rolls():
    env = LiarsDiceEnv(num_dice=3)
    env.reset(num_players=3, seed=42)
    first_rolls = {pid: list(roll) for pid, roll in env.state.game_state["dice_rolls"].items()}
    env.step("Bid: 20, 6")
    env.step("Call")
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["dice_rolls"] == first_rolls


def test_snapshot_restore_replays_call_and_reroll():
    env = LiarsDiceEnv(num_dice=2)
    env.reset(num_players=3, seed=42)
    env.step("Bid: 7, 6")
    before = env.snapshot()
    env.step("Call")
    expected = env.snapshot()
    env.restore(before)
    env.step("Call")
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


@pytest.mark.parametrize("num_dice", [0, -1, True, 1.5])
def test_invalid_dice_configuration_is_rejected(num_dice):
    with pytest.raises(ValueError, match="num_dice"):
        LiarsDiceEnv(num_dice=num_dice)


@pytest.mark.parametrize(
    "action",
    ["Bid: 1, 2 Call", "Call Bid: 2, 3", "Bid: 1, 2\nBid: 2, 3"],
)
def test_mixed_or_duplicate_actions_are_rejected_atomically(action):
    env = _fresh()
    before = dict(env.state.game_state["current_bid"])
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_bid"] == before
