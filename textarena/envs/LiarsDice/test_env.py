"""Deterministic offline tests for Liar's Dice.

FFA multiplayer game driven with two players and ``num_dice=1`` for short games.
Dice are rolled randomly; we read ``game_state['dice_rolls']`` to build bids
whose truth value is known, guaranteeing the caller/bidder outcome.

Final rewards are rank-scaled; for 2 players the loser gets -1.0 and the winner
+1.0.
"""

import pytest

from textarena.envs.LiarsDice.env import LiarsDiceEnv


def _fresh(num_dice=1):
    env = LiarsDiceEnv(num_dice=num_dice)
    env.reset(num_players=2, seed=42)
    return env


def _false_bid(env):
    """A legal opening bid that is guaranteed to be a bluff (fewer dice show the face)."""
    rolls = env.state.game_state["dice_rolls"].values()
    counts = {face: sum(dice.count(face) for dice in rolls) for face in range(1, 7)}
    face = min(counts, key=counts.get)
    return f"Bid: {counts[face] + 1}, {face}"


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
    env.step(_false_bid(env))       # P0 bluffs
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
    done, _ = env.step("Call")        # invalid #2 -> P0 eliminated, game ends
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
    env.step(_false_bid(env))
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
    env.step(_false_bid(env))
    env.step("Call")
    assert sum(len(roll) for roll in gs["dice_rolls"].values()) == sum(gs["remaining_dice"].values()) == 11


def test_scripted_three_player_game_has_rank_scaled_rewards():
    env = LiarsDiceEnv(num_dice=1)
    env.reset(num_players=3, seed=42)
    env.step(_false_bid(env))
    done, _ = env.step("Call")
    assert not done and env.state.current_player_id == 1
    env.step(_false_bid(env))
    done, _ = env.step("Call")
    assert done
    assert env.state.eliminated == [0, 1]
    assert env.state.rewards == {0: -1.0, 1: 0.0, 2: 1.0}


def test_repeat_reset_replays_private_rolls():
    env = LiarsDiceEnv(num_dice=3)
    env.reset(num_players=3, seed=42)
    first_rolls = {pid: list(roll) for pid, roll in env.state.game_state["dice_rolls"].items()}
    env.step(_false_bid(env))
    env.step("Call")
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["dice_rolls"] == first_rolls


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


def test_bid_quantity_cannot_exceed_dice_in_play():
    env = _fresh()  # two players with one die each
    done, _ = env.step("Bid: 3, 6")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_bid"] == {"quantity": 0, "face_value": 0}
    env.step("Bid: 2, 6")
    assert env.state.game_state["current_bid"] == {"quantity": 2, "face_value": 6}


def test_players_who_keep_raising_must_eventually_call():
    env = LiarsDiceEnv(num_dice=2)
    env.reset(num_players=3, seed=0)
    done = False
    for _ in range(500):
        quantity = env.state.game_state["current_bid"]["quantity"]
        done, _ = env.step(f"Bid: {quantity + 1}, 6")
        if not done and env.state.error_count:
            done, _ = env.step("Call")
        if done:
            break
    assert done


def test_call_reveals_every_players_dice():
    env = LiarsDiceEnv(num_dice=2)
    env.reset(num_players=3, seed=42)
    rolls = {pid: list(dice) for pid, dice in env.state.game_state["dice_rolls"].items()}
    env.step(_false_bid(env))
    start = len(env.state.events)
    env.step("Call")
    public = [m for _, m, _, to in env.state.events[start:] if to == -1]
    reveal = next(m for m in public if "Revealed dice" in m)
    for pid, dice in rolls.items():
        assert f"Player {pid}: {', '.join(map(str, dice))}" in reveal


def test_board_shows_dice_in_play_and_current_bid():
    env = LiarsDiceEnv(num_dice=3)
    env.reset(num_players=3, seed=42)
    assert "Dice in play: 9" in env.render(0)
    assert "Current bid: none" in env.render(0)
    env.step("Bid: 2, 5")
    assert "Current bid: 2 × face 5" in env.render(1)


def test_prompt_states_the_bid_rules_actually_enforced():
    prompt = _fresh().prompt(0)
    assert "raise the quantity (with any face)" in prompt
    assert "keep the quantity and raise the face" in prompt
    assert "cannot exceed the number of dice in play" in prompt


def test_padded_valid_commands_are_still_accepted():
    env = _fresh(num_dice=2)
    env.step("  Bid : 1 , 2  ")
    assert env.state.game_state["current_bid"] == {"quantity": 1, "face_value": 2}
    done, _ = env.step("\n call \n")
    assert env.state.game_state["current_bid"] == {"quantity": 0, "face_value": 0}
