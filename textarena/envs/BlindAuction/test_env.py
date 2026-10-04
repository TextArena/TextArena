"""Deterministic game-logic tests for BlindAuction."""
import copy

import pytest

import textarena as ta
from textarena.envs.BlindAuction.env import BlindAuctionEnv


def make_env(num_players=3, seed=42, **kwargs):
    kwargs.setdefault("num_items", 3)
    kwargs.setdefault("conversation_rounds", 1)
    kwargs.setdefault("base_item_values", [100, 200, 300])
    env = BlindAuctionEnv(**kwargs)
    env.reset(num_players=num_players, seed=seed)
    return env


def run_conversation_phase(env):
    """Play out the conversation phase with plain broadcasts."""
    while env.state.game_state["phase"] == "conversation":
        done, _ = env.step("Broadcast: hello")
        assert done is False
    assert env.state.game_state["phase"] == "bidding"


def test_reset_initializes_game_state():
    env = make_env()
    gs = env.state.game_state
    assert gs["phase"] == "conversation"
    assert gs["remaining_capital"] == {0: 1000, 1: 1000, 2: 1000}
    assert gs["player_bids"] == {0: {}, 1: {}, 2: {}}
    assert len(gs["item_names"]) == 3
    assert env.state.current_player_id == 0
    # Every player has a subjective value within +-20% of the base value
    for pid in range(3):
        for i, base in enumerate([100, 200, 300]):
            assert abs(gs["player_item_values"][pid][i] - base) <= int(0.2 * base)


def test_num_players_bounds_enforced():
    env = BlindAuctionEnv(num_items=3, conversation_rounds=1, base_item_values=[100, 200, 300])
    with pytest.raises(AssertionError):
        env.reset(num_players=2, seed=42)
    with pytest.raises(AssertionError):
        env.reset(num_players=16, seed=42)


def test_broadcast_reaches_all_players_and_turn_rotates():
    env = make_env()
    done, _ = env.step("Broadcast: hello everyone")
    assert done is False
    assert env.state.current_player_id == 1
    for pid in range(3):
        messages = [msg for _, msg, _ in env.state.observations[pid]]
        assert any("(Broadcast) Player 0 says: hello everyone" in m for m in messages)


def test_whisper_only_reaches_target():
    env = make_env()
    done, _ = env.step("Whisper 2: secret deal")
    assert done is False
    assert env.state.current_player_id == 1
    p2_messages = [msg for _, msg, _ in env.state.observations[2]]
    assert any("(Private) Player 0 says: secret deal" in m for m in p2_messages)
    p1_messages = [msg for _, msg, _ in env.state.observations[1]]
    assert not any("(Private)" in m for m in p1_messages)


def test_full_game_highest_net_worth_wins():
    env = make_env(seed=42)
    run_conversation_phase(env)

    done, _ = env.step("Bid Item 0: 100")   # player 0
    assert done is False
    done, _ = env.step("Bid Item 1: 250")   # player 1
    assert done is False
    done, _ = env.step("I will not bid on anything.")  # player 2 passes
    assert done is True
    assert env.state.turn == 6

    results = env.state.game_state["auction_results"]
    assert results["item_winners"] == {0: 0, 1: 1}
    assert results["winning_bids"] == {0: 100, 1: 250}

    # Net worth = remaining capital + subjective value of the items won
    values = env.state.game_state["player_item_values"]
    expected_net_worth = {0: 900 + values[0][0], 1: 750 + values[1][1], 2: 1000}
    assert results["player_net_worth"] == expected_net_worth

    # With seed 42 the subjective values are low enough that passing wins
    assert max(expected_net_worth, key=expected_net_worth.get) == 2
    assert env.state.rewards == {0: -1, 1: -1, 2: 1}


def test_multiple_bare_bids_can_use_separate_lines():
    env = make_env(seed=42)
    run_conversation_phase(env)
    done, _ = env.step("Bid Item 0: 100\nBid Item 1: 200")
    assert done is False
    assert env.state.game_state["player_bids"][0] == {0: 100, 1: 200}
    assert env.state.game_state["remaining_capital"][0] == 1000


def test_incidental_bid_in_prose_is_treated_as_no_bid():
    env = make_env(seed=42)
    run_conversation_phase(env)
    done, _ = env.step("I may bid on Item 0 later, but not now.")
    assert done is False
    assert env.state.game_state["player_bids"][0] == {}
    assert env.state.current_player_id == 1


def test_all_players_passing_is_a_draw():
    env = make_env(seed=42)
    run_conversation_phase(env)
    done = False
    for _ in range(3):
        assert done is False
        done, _ = env.step("no bids from me")
    assert done is True
    assert env.state.game_state["auction_results"]["item_winners"] == {}
    assert env.state.rewards == {0: 0, 1: 0, 2: 0}


def test_whisper_to_nonexistent_player_is_rejected():
    env = make_env()
    done, _ = env.step("Whisper 99: hi")
    assert done is False
    assert env.state.current_player_id == 0  # same player retries
    # a valid action afterwards moves the game along
    done, _ = env.step("Broadcast: sorry, my mistake")
    assert done is False
    assert env.state.current_player_id == 1


def test_self_whisper_rejects_entire_mixed_action_atomically():
    env = make_env()
    events_before = len(env.state.events)
    done, _ = env.step("Broadcast: public; Whisper 0: private")
    assert not done
    assert env.state.error_count == 1
    assert env.game_state["conversations_completed"] == 0
    assert not any(
        "(Broadcast)" in message
        for _, message, _, _ in env.state.events[events_before:]
    )


def test_bid_exceeding_capital_is_rejected():
    env = make_env(seed=42)
    run_conversation_phase(env)
    done, _ = env.step("Bid Item 0: 5000")
    assert done is False
    assert env.state.current_player_id == 0  # same player retries
    assert env.state.game_state["player_bids"][0] == {}
    assert env.state.game_state["remaining_capital"][0] == 1000
    # a valid bid afterwards is accepted
    done, _ = env.step("Bid Item 0: 500")
    assert done is False
    assert env.state.game_state["player_bids"][0] == {0: 500}
    assert env.state.game_state["remaining_capital"][0] == 1000  # sealed bid is reserved, not paid yet
    assert env.state.current_player_id == 1


def test_bid_on_nonexistent_item_is_rejected():
    env = make_env(seed=42)
    run_conversation_phase(env)
    done, _ = env.step("Bid Item 7: 100")
    assert done is False
    assert env.state.current_player_id == 0
    assert env.state.game_state["player_bids"][0] == {}
    assert env.state.game_state["remaining_capital"][0] == 1000


def test_duplicate_item_bids_are_rejected_atomically():
    env = make_env(conversation_rounds=0, num_items=1, base_item_values=[100])
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Bid Item 0: 10\nBid Item 0: 20")
    assert not done
    assert env.game_state == before
    assert env.state.current_player_id == 0


def test_pathologically_large_bid_is_invalid_not_an_exception():
    env = make_env(conversation_rounds=0, num_items=1, base_item_values=[100])
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Bid Item 0: " + "9" * 5000)
    assert not done
    assert env.game_state == before


def test_phase_inappropriate_and_mixed_commands_are_rejected():
    env = make_env()
    done, _ = env.step("Broadcast: hello; Bid Item 0: 10")
    assert not done
    assert env.game_state["conversations_completed"] == 0
    assert not any(
        "(Broadcast)" in message
        for _, message, _, _ in env.state.events
    )

    done, _ = env.step("Broadcast: hello; Whisper 99: secret")
    assert not done
    assert env.game_state["conversations_completed"] == 1  # second invalid forfeits the phase turn
    assert not any(
        "(Broadcast)" in message
        for _, message, _, _ in env.state.events
    )


def test_repeated_invalid_move_forfeits_exactly_one_conversation_turn():
    env = make_env()
    env.step("Whisper 99: bad")
    done, _ = env.step("Whisper 99: still bad")
    assert not done
    assert env.state.current_player_id == 1
    assert env.game_state["conversations_completed"] == 1
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1

    env.step("Broadcast: p1")
    env.step("Broadcast: p2")
    assert env.game_state["phase"] == "bidding"


def test_only_winning_bid_is_paid():
    env = make_env(
        conversation_rounds=0,
        num_items=1,
        starting_capital=100,
        base_item_values=[100],
    )
    env.step("Bid Item 0: 10")
    env.step("Bid Item 0: 20")
    done, _ = env.step("no bid")
    assert done
    assert env.game_state["remaining_capital"] == {0: 100, 1: 80, 2: 100}
    assert env.game_state["auction_results"]["player_spent"] == {1: 20, 0: 0, 2: 0}


def test_partial_top_tie_rewards_all_top_players():
    env = make_env()
    env.game_state["auction_results"] = {
        "player_net_worth": {0: 1100, 1: 1100, 2: 900},
        "player_profit": {0: 100, 1: 100, 2: -100},
        "player_value": {0: 100, 1: 100, 2: 0},
    }
    outcome = env._determine_winner()
    assert outcome.rewards == {0: 1, 1: 1, 2: -1}


def test_zero_conversation_rounds_and_maximum_player_count_full_game():
    env = make_env(
        num_players=15,
        conversation_rounds=0,
        num_items=1,
        base_item_values=[100],
    )
    assert env.game_state["phase"] == "bidding"
    done = False
    for _ in range(15):
        assert not done
        done, _ = env.step("no bids")
    assert done
    assert env.state.turn == 15
    assert env.state.rewards == {pid: 0 for pid in range(15)}


def test_sealed_board_is_pure_silent_and_hides_other_players(capsys):
    env = make_env(conversation_rounds=0, num_items=1, base_item_values=[100])
    p0_value = env.game_state["player_item_values"][0][0]
    env.step("Bid Item 0: 17")
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert capsys.readouterr().out == ""
    assert env.game_state == before
    assert "(private)" in board
    assert "(sealed)" in board
    p0_row = next(line for line in board.splitlines() if "│   0" in line and ("private" in line or str(p0_value) in line))
    assert "(private)" in p0_row


def test_sealed_bid_amount_is_not_routed_to_other_players():
    env = make_env(conversation_rounds=0, num_items=1, base_item_values=[100])
    env.step("Bid Item 0: 987")
    for pid in (1, 2):
        messages = [message for _, message, _ in env.state.observations[pid]]
        assert not any("987" in message for message in messages)


def test_seeded_resets_do_not_pin_generated_base_values_and_snapshot_restores():
    env = BlindAuctionEnv(num_items=3, conversation_rounds=0)
    env.reset(num_players=3, seed=7)
    first = copy.deepcopy(env.game_state)
    snapshot = env.snapshot()
    env.step("Bid Item 0: 1")
    env.restore(snapshot)
    assert env.game_state["player_bids"] == {0: {}, 1: {}, 2: {}}

    env.reset(num_players=3, seed=8)
    assert env.game_state["base_item_values"] != first["base_item_values"]
    env.reset(num_players=3, seed=7)
    assert env.game_state["base_item_values"] == first["base_item_values"]
    assert env.game_state["player_item_values"] == first["player_item_values"]


def test_short_base_value_list_is_filled_for_every_item():
    env = BlindAuctionEnv(num_items=3, conversation_rounds=0, base_item_values=[100])
    env.reset(num_players=3, seed=42)
    assert len(env.game_state["base_item_values"]) == 3
    assert all(len(values) == 3 for values in env.game_state["player_item_values"].values())


def test_extremely_large_integer_base_value_does_not_overflow():
    base_value = 10 ** 1000
    env = make_env(
        conversation_rounds=0,
        num_items=1,
        base_item_values=[base_value],
    )
    variation = base_value // 5
    for values in env.game_state["player_item_values"].values():
        assert base_value - variation <= values[0] <= base_value + variation


@pytest.mark.parametrize(
    "kwargs",
    [
        {"starting_capital": 0},
        {"num_items": 0},
        {"conversation_rounds": -1},
        {"base_item_values": [0]},
        {"base_item_values": 100},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        BlindAuctionEnv(**kwargs)
