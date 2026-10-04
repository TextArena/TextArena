"""Offline deterministic tests for the SimpleBlindAuction environment."""
import copy

import pytest

from textarena.envs.SimpleBlindAuction.env import SimpleBlindAuctionEnv


def _fresh(conversation_rounds=1, num_items=5, starting_capital=1000):
    env = SimpleBlindAuctionEnv(
        conversation_rounds=conversation_rounds,
        num_items=num_items,
        starting_capital=starting_capital,
    )
    env.reset(num_players=2, seed=42)
    return env


def _advance_to_bidding(env):
    """Exhaust the conversation phase (conversation_rounds * 2 messages)."""
    while env.state.game_state["phase"] == "conversation":
        env.step("let's talk")


def test_reset_initial_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["phase"] == "conversation"
    assert gs["round"] == 1
    assert gs["remaining_capital"] == {0: 1000, 1: 1000}
    assert len(gs["item_names"]) == 5


def test_conversation_transitions_to_bidding():
    env = _fresh(conversation_rounds=1)
    env.step("hello")            # P0
    assert env.state.game_state["phase"] == "conversation"
    env.step("hi back")          # P1 -> 2 messages done -> bidding
    assert env.state.game_state["phase"] == "bidding"


def test_player0_wins_with_a_cheap_winning_bid():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    # P0 grabs item 0 for a single coin (guaranteed worth >1 to them),
    # P1 abstains. P0 net worth = 999 + value(item0) > 1000 = P1 net worth.
    assert env.state.game_state["player_item_values"][0][0] > 1
    assert env.state.current_player_id == 0
    done, _ = env.step("Bid on Item 0: 1")
    assert not done
    done, _ = env.step("I pass, no bids")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.turn == 4


def test_no_bids_from_either_player_is_a_draw():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    env.step("no bids from me")
    done, _ = env.step("no bids from me either")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_bid_on_nonexistent_item_is_invalid():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    done, _ = env.step("Bid on Item 99: 50")
    assert not done
    assert env.state.error_count == 1


def test_bid_exceeding_capital_is_invalid():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    done, _ = env.step("Bid on Item 0: 5000")
    assert not done
    assert env.state.error_count == 1


def test_multiple_bids_use_one_bare_command_per_line():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    done, _ = env.step("Bid on Item 0: 10\nBid on Item 1: 20")
    assert not done
    assert env.state.game_state["player_bids"][0] == {0: 10, 1: 20}


def test_bids_may_also_be_separated_by_semicolons():
    env = _fresh(conversation_rounds=1)
    _advance_to_bidding(env)
    done, _ = env.step("Bid on Item 0: 10; Bid on Item 1: 20;")
    assert not done
    assert env.state.error_count == 0
    assert env.state.game_state["player_bids"][0] == {0: 10, 1: 20}
    done, _ = env.step("[Bid Item 0: 15]; [Bid Item 2: 5]\n[Bid Item 3: 1]")
    assert done
    assert env.state.game_state["player_bids"][1] == {0: 15, 2: 5, 3: 1}


def test_semicolon_separated_bid_mixed_with_prose_is_invalid_but_plain_prose_passes():
    env = _fresh(conversation_rounds=0, num_items=2)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Bid on Item 0: 10; I hope that is enough")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state == before

    done, _ = env.step("No bids from me; good luck")
    assert not done
    assert env.state.error_count == 0
    assert env.game_state["bidding_done"][0] is True
    assert env.game_state["player_bids"][0] == {}


def test_prompt_and_announcement_teach_both_bid_separators():
    env = _fresh(conversation_rounds=1)
    assert "one per line or separated by semicolons" in env.prompt(0)
    _advance_to_bidding(env)
    assert any("separate bids with semicolons" in message for _, message, _, _ in env.state.events)


def test_duplicate_item_bids_are_rejected_atomically():
    env = _fresh(conversation_rounds=0, num_items=1)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Bid Item 0: 10\nBid Item 0: 20")
    assert not done
    assert env.game_state == before
    assert env.state.current_player_id == 0


def test_pathologically_large_bid_is_invalid_not_an_exception():
    env = _fresh(conversation_rounds=0, num_items=1)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Bid Item 0: " + "9" * 5000)
    assert not done
    assert env.game_state == before


def test_command_like_malformed_or_mixed_bid_is_invalid():
    env = _fresh(conversation_rounds=0, num_items=2)
    done, _ = env.step("Bid Item zero: 10")
    assert not done and env.state.error_count == 1
    done, _ = env.step("Bid Item 0: 10\n[Bid Item 1: 20]")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_only_winning_bids_are_paid_and_ties_are_refunded():
    env = _fresh(conversation_rounds=0, num_items=1, starting_capital=100)
    env.step("Bid Item 0: 10")
    done, _ = env.step("Bid Item 0: 20")
    assert done
    assert env.game_state["remaining_capital"] == {0: 100, 1: 80}
    assert env.game_state["auction_results"]["player_spent"] == {0: 0, 1: 20}

    tied = _fresh(conversation_rounds=0, num_items=1, starting_capital=100)
    tied.step("Bid Item 0: 10")
    done, _ = tied.step("Bid Item 0: 10")
    assert done
    assert tied.game_state["remaining_capital"] == {0: 100, 1: 100}
    assert tied.state.rewards == {0: 0, 1: 0}


def test_zero_conversation_rounds_starts_in_bidding_and_counts_terminal_action():
    env = _fresh(conversation_rounds=0, num_items=1)
    assert env.game_state["phase"] == "bidding"
    env.step("no bids")
    done, _ = env.step("no bids")
    assert done
    assert env.state.turn == 2


def test_sealed_board_is_pure_and_hides_other_player_values_and_bids():
    env = _fresh(conversation_rounds=0, num_items=1)
    own_value = env.game_state["player_item_values"][0][0]
    other_value = env.game_state["player_item_values"][1][0]
    env.step("Bid Item 0: 17")
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert "(sealed)" in board
    assert "(private)" in board
    assert str(other_value) in board
    if own_value != other_value:
        assert str(own_value) not in board


def test_sealed_bid_amount_is_not_routed_to_opponent():
    env = _fresh(conversation_rounds=0, num_items=1)
    env.step("Bid Item 0: 777")
    opponent_messages = [message for _, message, _ in env.state.observations[1]]
    assert not any("777" in message for message in opponent_messages)


def test_seeded_reset_snapshot_and_configuration_bounds():
    env = SimpleBlindAuctionEnv(conversation_rounds=0, num_items=2)
    env.reset(num_players=2, seed=7)
    first_values = copy.deepcopy(env.game_state["base_item_values"])
    snapshot = env.snapshot()
    env.step("Bid Item 0: 1")
    env.restore(snapshot)
    assert env.game_state["player_bids"] == {0: {}, 1: {}}
    env.reset(num_players=2, seed=7)
    assert env.game_state["base_item_values"] == first_values

    for kwargs in (
        {"starting_capital": 0},
        {"num_items": 0},
        {"conversation_rounds": -1},
        {"base_item_values": [0]},
        {"base_item_values": 100},
    ):
        with pytest.raises(ValueError):
            SimpleBlindAuctionEnv(**kwargs)


def test_extremely_large_integer_base_value_does_not_overflow():
    base_value = 10 ** 1000
    env = SimpleBlindAuctionEnv(
        conversation_rounds=0,
        num_items=1,
        base_item_values=[base_value],
    )
    env.reset(num_players=2, seed=42)
    variation = base_value // 5
    for values in env.game_state["player_item_values"].values():
        assert base_value - variation <= values[0] <= base_value + variation
