"""Offline deterministic tests for the SimpleNegotiation environment."""
import copy

import pytest

import textarena as ta
from textarena.envs.SimpleNegotiation.env import SimpleNegotiationEnv


def _fresh(max_turns=10):
    env = SimpleNegotiationEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["current_offer"] is None
    for pid in (0, 1):
        assert set(gs["player_resources"][pid].keys()) == set(env.resource_names)
        inv = gs["inventory_value"][pid]
        assert inv["initial"] == inv["current"]
        assert inv["change"] == 0


def test_successful_trade_mutates_resources():
    env = _fresh()
    gs = env.state.game_state
    ore_p0 = gs["player_resources"][0]["Ore"]
    wheat_p1 = gs["player_resources"][1]["Wheat"]
    # P0 offers 1 Wheat for 1 Ore; P1 accepts.
    env.step("Here is my proposal:\nOffer: 1 Wheat -> 1 Ore")
    done = env.step("That works for me.\nAccept")
    assert not done
    assert gs["player_resources"][0]["Ore"] == ore_p0 + 1
    assert gs["player_resources"][1]["Wheat"] == wheat_p1 + 1
    # Inventory change is tracked for both players.
    assert gs["inventory_value"][0]["change"] != 0
    assert gs["inventory_value"][1]["change"] != 0


def test_favorable_trade_lets_player0_win_at_turn_limit():
    # Wheat is worth far less than Ore, so trading Wheat for Ore is great for P0
    # and bad for P1 -> P0 has the larger inventory-value change.
    env = _fresh(max_turns=3)
    vals0 = env.state.game_state["player_values"][0]
    assert vals0["Ore"] > vals0["Wheat"]
    env.step("Offer: 1 Wheat -> 1 Ore")  # turn 0
    env.step("Accept")                    # turn 1, trade executes
    done = env.step("No further offers.")  # turn 2 == max_turns -> resolve
    assert done
    assert env.state.turn == 3
    assert env.state.rewards == {0: 1, 1: -1}


def test_no_trades_results_in_draw():
    env = _fresh(max_turns=2)
    done = False
    for _ in range(2):  # engine resolves the turn limit after exactly max_turns valid moves
        assert not done
        done = env.step("just chatting, no offers")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_offer_without_resources_is_invalid():
    env = _fresh()
    # No player holds 100 Ore (resources are sampled in [5, 25]).
    done = env.step("Offer: 100 Ore -> 1 Wheat")
    assert not done
    assert env.state.error_count == 1


def test_malformed_offer_is_invalid():
    env = _fresh()
    done = env.step("Offer: total nonsense with no arrow")
    assert not done
    assert env.state.error_count == 1


def test_accept_in_ordinary_prose_does_not_accept_offer():
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    done = env.step("I accept that this is an interesting proposal.")
    assert not done
    assert env.state.game_state["current_offer"] is None
    assert env.state.game_state["trade_history"][-1]["outcome"] == "Rejected"


def test_accept_and_deny_require_an_incoming_offer():
    env = _fresh()
    done = env.step("Accept")
    assert not done and env.state.error_count == 1
    done = env.step("Deny")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_mixed_or_duplicate_commands_are_invalid_and_atomic():
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    before = copy.deepcopy(env.game_state)
    done = env.step("Accept\nOffer: 1 Wood -> 1 Brick")
    assert not done
    assert env.game_state == before
    assert env.state.current_player_id == 1

    done = env.step("Accept\nAccept")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_resource_parser_rejects_unconsumed_text():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done = env.step("Offer: 1 Wheat plus unlimited Ore -> 1 Brick")
    assert not done
    assert env.game_state == before


def test_accept_revalidates_both_sides_atomically():
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    env.game_state["player_resources"][0]["Wheat"] = 0
    before = copy.deepcopy(env.game_state)
    done = env.step("Accept")
    assert not done
    assert env.game_state == before


def test_private_board_is_pure_and_offer_labels_are_dynamic():
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert "Player 0 offers" in board
    assert "Player 1's turn to respond" in board
    assert "Inventory and values are private" in board
    p1_ore_value = env.game_state["player_values"][1]["Ore"]
    p0_ore_value = env.game_state["player_values"][0]["Ore"]
    assert str(p1_ore_value) in board
    if p0_ore_value != p1_ore_value:
        hidden_section = board.split("Player 1 Inventory", 1)[0]
        assert str(p0_ore_value) not in hidden_section


def _latest_board(env):
    _, observation = env.get_observation()
    return [message for _, message, kind in observation if kind == ta.ObservationType.GAME_BOARD][-1]


def test_acting_player_sees_their_current_inventory_and_the_pending_offer():
    env = _fresh()
    gs = env.state.game_state
    ore_before = gs["player_resources"][0]["Ore"]
    env.get_observation()
    env.step("Offer: 1 Ore -> 1 Wheat")
    board = _latest_board(env)  # Player 1, who must respond
    assert "Player 0 offers" in board and "Turn 2 of 10" in board
    env.step("Accept")
    board = _latest_board(env)  # Player 0, after the trade executed
    assert gs["player_resources"][0]["Ore"] == ore_before - 1
    assert f"Ore        {ore_before - 1:<5}" in board
    assert "Inventory and values are private" in board


def test_prompt_states_the_relative_scoring_rule_and_default_deny():
    prompt = _fresh().prompt(0)
    assert "increased more wins" in prompt
    assert "rejected automatically unless you Accept" in prompt


def test_offer_may_start_with_i_give():
    env = _fresh()
    env.step("Offer: I give 1 Wheat -> 1 Ore")
    offer = env.state.game_state["current_offer"]
    assert offer["offered_resources"] == {"Wheat": 1}
    assert offer["requested_resources"] == {"Ore": 1}


@pytest.mark.parametrize("action", ["Offer 1 Wheat -> 1 Ore", "[Offer 1 Wheat -> 1 Ore]"])
def test_offer_without_a_colon_is_malformed(action):
    env = _fresh()
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_offer"] is None


@pytest.mark.parametrize("reply", ["Accept.", "accept!", "ACCEPT !"])
def test_accept_may_end_with_punctuation(reply):
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    done = env.step(f"Deal.\n{reply}")
    assert not done
    assert env.state.error_count == 0
    assert env.state.game_state["trade_history"][-1]["outcome"] == "Accepted"


@pytest.mark.parametrize("reply", ["Deny.", "deny!"])
def test_deny_may_end_with_punctuation(reply):
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    env.step(reply)
    assert env.state.error_count == 0
    assert env.state.game_state["trade_history"][-1]["outcome"] == "Rejected"


@pytest.mark.parametrize("reply", ["Accept it", "Accept?", "Accept.."])
def test_decision_lines_with_other_text_stay_malformed(reply):
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    before = copy.deepcopy(env.game_state)
    env.step(reply)
    assert env.state.error_count == 1
    assert env.game_state == before


def test_prompt_states_that_decisions_may_end_with_punctuation():
    assert "Accept and Deny may end with '.' or '!'" in _fresh().prompt(0)


def test_offer_box_keeps_its_width_for_multi_digit_quantities():
    env = _fresh()
    env.step("Offer: 12 Wheat, 3 Sheep -> 100 Brick")
    board = env.get_board_str()
    box_lines = [line for line in board.splitlines() if line and line[0] in "┌│└"]
    assert {len(line) for line in box_lines} == {79}
    assert "│   - 12 Wheat " in board and "│   - 100 Brick " in board


def test_mdp_variant_shows_the_opponents_chat():
    env = ta.make("SimpleNegotiation-v1-mdp")
    env.reset(num_players=2, seed=42)
    env.get_observation()
    env.step("Plenty of wheat here.\nOffer: 1 Wheat -> 1 Ore")
    player_id, observation = env.get_observation()
    assert player_id == 1
    assert "Plenty of wheat here." in observation


def test_chat_lines_that_merely_mention_commands_are_chat():
    env = _fresh()
    env.step("Offer: 1 Wheat -> 1 Ore")
    done = env.step("Offering more later. I accepted your last idea.\nAccept")
    assert not done
    assert env.state.error_count == 0
    assert env.state.game_state["trade_history"][-1]["outcome"] == "Accepted"
