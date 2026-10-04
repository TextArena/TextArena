"""Deterministic tests for the Bohnanza environment.

Hands, fields, piles and face-up cards are set explicitly where a test depends
on them; everything else is seeded.
"""
import copy
import random
from collections import Counter

import pytest

import textarena as ta
from textarena.envs.Bohnanza.env import (
    BEAN_TYPES,
    DECK_SIZE,
    BohnanzaEnv,
    canonical_bean,
    normalize_command,
    parse_bean_list,
    parse_command,
)
from textarena.envs.Bohnanza.renderer import harvest_coins, render_board


# ----------------------------------------------------------------- helpers
def make_env(num_players=3, seed=42, **kwargs):
    kwargs.setdefault("max_turns", 200)
    kwargs.setdefault("error_allowance", 3)
    env = BohnanzaEnv(**kwargs)
    env.reset(num_players=num_players, seed=seed)
    return env


def gs(env):
    return env.state.game_state


def total_cards(game_state):
    """Every card is in exactly one place; coins are bean cards turned over."""
    total = len(game_state["deck"]) + len(game_state["discard_pile"]) + len(game_state["face_up_cards"])
    for pid, player in game_state["players"].items():
        total += len(player["hand"]) + player["coins"] + len(game_state["mandatory_plants"][pid])
        total += sum(field[1] for field in player["fields"] if field is not None)
    return total


def fitting_field(player, bean):
    for number, field in enumerate(player["fields"], start=1):
        if field is None or field[0] == bean:
            return number
    return None


def harvestable_field(player):
    fields = player["fields"]
    for number, field in enumerate(fields, start=1):
        if field is None:
            continue
        if field[1] == 1 and any(other is not None and other[1] > 1 for other in fields):
            continue
        return number
    raise AssertionError("no harvestable field")


def plant_front(env):
    """Phase 1: plant the front card into a fitting field, harvesting first if needed."""
    player = gs(env)["players"][env.state.current_player_id]
    field = fitting_field(player, player["hand"][0])
    if field is None:
        env.step(f"harvest {harvestable_field(player)}")
        field = fitting_field(player, player["hand"][0])
    return env.step(f"plant {field}")


def to_trading(env):
    plant_front(env)
    if gs(env)["current_phase"] == "plant":
        env.step("pass")
    assert gs(env)["current_phase"] == "draw_trade"


def finish_planting(env):
    """Phase 3: plant every set-aside bean for whoever has the move."""
    done = False
    while not done and gs(env)["current_phase"] == "plant_mandatory":
        pid = env.state.current_player_id
        player = gs(env)["players"][pid]
        bean = gs(env)["mandatory_plants"][pid][0]
        field = fitting_field(player, bean)
        if field is None:
            done, _ = env.step(f"harvest {harvestable_field(player)}")
            continue
        done, _ = env.step(f"plant {bean} {field}")
    return done


def play_turn(env):
    to_trading(env)
    env.step("end trading")
    return finish_planting(env)


def play_simple_game(env, step_cap=5000):
    """Valid, trade-free play: plant one card, end trading at once, plant the face-up cards."""
    done, steps = False, 0
    while not done and steps < step_cap:
        g = gs(env)
        pid = env.state.current_player_id
        player = g["players"][pid]
        phase = g["current_phase"]
        if phase == "plant":
            if g["planted_from_hand"] >= 1 or not player["hand"]:
                action = "pass"
            else:
                field = fitting_field(player, player["hand"][0])
                action = f"plant {field}" if field else f"harvest {harvestable_field(player)}"
        elif phase == "draw_trade":
            action = "end trading" if pid == g["active_player"] else "pass"
        else:
            bean = g["mandatory_plants"][pid][0]
            field = fitting_field(player, bean)
            action = f"plant {bean} {field}" if field else f"harvest {harvestable_field(player)}"
        done, _ = env.step(action)
        assert env.state.error_count == 0, (action, env.state.events[-2][1])
        steps += 1
    return done, steps


def events_for(env, player_id, start=0):
    return [(sender, message, kind) for sender, message, kind, to in env.state.events[start:] if to in (-1, player_id)]


# ===== BASIC ENVIRONMENT TESTS =====

def test_init_defaults_and_custom_values():
    env = BohnanzaEnv()
    assert (env.max_turns, env.error_allowance, env.deck_cycles, env.max_trade_rounds) == (3000, 3, 3, None)
    env = BohnanzaEnv(max_turns=100, error_allowance=5, deck_cycles=1, max_trade_rounds=2)
    assert (env.max_turns, env.error_allowance, env.deck_cycles, env.max_trade_rounds) == (100, 5, 1, 2)
    assert len(env.BEAN_TYPES) == 8
    assert "Blue" in env.BEAN_TYPES and "Garden" in env.BEAN_TYPES


def test_reset_valid_player_counts():
    env = BohnanzaEnv(max_turns=200, error_allowance=3)
    for num_players in (3, 4, 5):
        env.reset(num_players=num_players, seed=42)
        g = gs(env)
        assert env.state.num_players == num_players
        assert env.state.max_turns == 200
        assert env.state.error_allowance == 3
        assert len(g["players"]) == num_players
        assert g["current_phase"] == "plant"
        assert g["deck_cycles_completed"] == 0
        assert g["face_up_cards"] == [] and g["active_trades"] == {}
        assert env.state.current_player_id == 0 and g["active_player"] == 0 and g["turn_number"] == 1


@pytest.mark.parametrize("num_players", [0, 1, 2, 6])
def test_reset_invalid_player_count(num_players):
    with pytest.raises(ValueError, match="Bohnanza needs 3 to 5 players"):
        BohnanzaEnv().reset(num_players=num_players)


# ===== GAME STATE INITIALIZATION TESTS =====

def test_deck_creation():
    g = gs(make_env(num_players=4))
    cards = list(g["deck"]) + [card for player in g["players"].values() for card in player["hand"]]
    assert len(cards) == DECK_SIZE == 104
    assert Counter(cards) == {bean: config["count"] for bean, config in BEAN_TYPES.items()}


def test_initial_hand_dealing():
    g = gs(make_env(num_players=4))
    for player in g["players"].values():
        assert len(player["hand"]) == 5
        assert all(card in BEAN_TYPES for card in player["hand"])


def test_field_initialization():
    env = BohnanzaEnv()
    env.reset(num_players=3, seed=42)
    assert all(player["fields"] == [None, None, None] for player in gs(env)["players"].values())
    for num_players in (4, 5):
        env.reset(num_players=num_players, seed=42)
        assert all(player["fields"] == [None, None] for player in gs(env)["players"].values())


def test_initial_game_state():
    g = gs(make_env(num_players=4))
    assert len(g["deck"]) == 104 - 4 * 5
    assert g["discard_pile"] == []
    assert g["current_phase"] == "plant" and g["deck_cycles_completed"] == 0 and not g["game_ending"]
    assert g["trade_counter"] == 0 and g["face_up_cards"] == [] and g["active_trades"] == {}
    assert g["mandatory_plants"] == {0: [], 1: [], 2: [], 3: []}
    for player in g["players"].values():
        assert player["coins"] == 0
        assert len(player["hand"]) == 5
        assert player["fields"] == [None, None]


# ===== PHASE MANAGEMENT TESTS =====

def test_phase_transitions():
    env = make_env()
    assert gs(env)["current_phase"] == "plant"
    env.step("plant 1")
    env.step("pass")
    assert gs(env)["current_phase"] == "draw_trade"
    env.step("end trading")
    assert gs(env)["current_phase"] == "plant_mandatory"  # the two face-up cards must be planted
    assert env.state.current_player_id == 0
    finish_planting(env)
    assert gs(env)["current_phase"] == "plant"
    assert gs(env)["active_player"] == 1 and env.state.current_player_id == 1
    assert gs(env)["turn_number"] == 2


def test_phase_specific_actions():
    env = make_env()
    for action in ("trade 1 Blue for 1 Red", "accept 1", "end trading"):
        env.step(action)
        assert env.state.error_count == 1
        env.state.error_count = 0
    assert gs(env)["current_phase"] == "plant"
    to_trading(env)
    env.step("plant 2")
    assert env.state.error_count == 1
    env.step("end trading")
    assert gs(env)["current_phase"] == "plant_mandatory"
    for action in ("pass", "trade 1 Blue for 1 Red", "end trading"):
        env.step(action)
        assert env.state.error_count == 1
        env.state.error_count = 0


def test_turn_advancement():
    env = make_env()
    hand_before = len(gs(env)["players"][0]["hand"])
    play_turn(env)
    assert env.state.current_player_id == 1 and gs(env)["active_player"] == 1
    assert gs(env)["turn_number"] == 2
    assert len(gs(env)["players"][0]["hand"]) == hand_before - 1 + 3


# ===== PLANT PHASE TESTS =====

def test_plant_from_hand_valid():
    env = make_env()
    player = gs(env)["players"][0]
    player["hand"] = ["Blue", "Blue", "Red", "Soy", "Green"]
    env.step("plant 1")
    assert player["fields"][0] == ("Blue", 1)
    assert player["hand"] == ["Blue", "Red", "Soy", "Green"]
    env.step("plant 1")
    assert player["fields"][0] == ("Blue", 2)
    assert gs(env)["current_phase"] == "draw_trade"  # two cards planted ends phase 1


def test_plant_from_hand_invalid():
    env = make_env()
    hand = list(gs(env)["players"][0]["hand"])
    env.step("plant 0")
    assert env.state.error_count == 1
    env.step("plant 10")
    assert env.state.error_count == 2
    assert gs(env)["players"][0]["hand"] == hand
    assert gs(env)["players"][0]["fields"] == [None, None, None]


def test_plant_hand_order_enforcement():
    env = make_env()
    player = gs(env)["players"][0]
    player["hand"] = ["Red", "Blue", "Soy", "Green", "Chili"]
    env.step("plant Blue 1")  # only the front card may be planted
    assert env.state.error_count == 1 and player["fields"][0] is None
    env.step("plant 1")
    assert player["fields"][0] == ("Red", 1)
    env.step("plant 2")
    assert player["fields"][1] == ("Blue", 1)
    assert player["hand"] == ["Soy", "Green", "Chili"]


def test_plant_maximum_cards():
    env = make_env()
    env.step("plant 1")
    env.step("plant 2")
    assert gs(env)["current_phase"] == "draw_trade"
    fields = list(gs(env)["players"][0]["fields"])
    env.step("plant 3")
    assert env.state.error_count == 1
    assert gs(env)["players"][0]["fields"] == fields


def test_plant_mandatory_first_card():
    env = make_env()
    hand = list(gs(env)["players"][0]["hand"])
    env.step("pass")
    assert env.state.error_count == 1
    assert gs(env)["players"][0]["hand"] == hand
    assert gs(env)["current_phase"] == "plant"


def test_bean_that_fits_no_field_requires_a_harvest_first():
    env = make_env()
    player = gs(env)["players"][0]
    player["hand"] = ["Green", "Soy", "Soy", "Soy", "Soy"]
    player["fields"] = [("Blue", 2), ("Red", 1), ("Soy", 1)]
    env.step("plant 1")
    assert env.state.error_count == 1
    env.step("harvest 2")  # bean protection: single Red while Blue has two
    assert env.state.error_count == 2
    env.step("harvest 1")
    assert env.state.error_count == 0 and player["fields"][0] is None
    env.step("plant 1")
    assert player["fields"][0] == ("Green", 1)


def test_empty_hand_skips_phase_one():
    env = make_env()
    gs(env)["players"][1]["hand"] = []
    play_turn(env)
    g = gs(env)
    assert g["active_player"] == 1 and env.state.current_player_id == 1
    assert g["current_phase"] == "draw_trade" and len(g["face_up_cards"]) == 2
    assert any("no cards in hand, so phase 1 is skipped" in message for _, message, _, _ in env.state.events)


# ===== TRADING PHASE TESTS =====

def test_propose_open_trade():
    env = make_env(num_players=4)
    to_trading(env)
    bean = gs(env)["players"][0]["hand"][0]
    env.step(f"trade {bean} for Blue")
    trade = gs(env)["active_trades"][1]
    assert trade == {"proposer": 0, "target": None, "offer": [bean], "want": ["Blue"], "status": "pending"}
    assert env.state.current_player_id == 1  # the floor passes on


def test_propose_targeted_trade():
    env = make_env(num_players=4)
    to_trading(env)
    env.step("pass")
    assert env.state.current_player_id == 1
    bean = gs(env)["players"][1]["hand"][0]
    env.step(f"trade {bean} for Blue")
    trade = gs(env)["active_trades"][1]
    assert trade["proposer"] == 1 and trade["target"] == 0  # offers go to the active player


def test_accept_trade():
    env = make_env(num_players=4)
    g = gs(env)
    g["players"][0]["hand"] = ["Soy", "Blue", "Green"]
    g["players"][1]["hand"] = ["Red", "Chili"]
    env.step("plant 1")
    env.step("pass")
    env.step("trade 1 Blue for 1 Red")
    env.step("accept 1")
    assert g["active_trades"][1]["status"] == "accepted"
    assert g["players"][0]["hand"] == ["Green"] and g["players"][1]["hand"] == ["Chili"]
    assert g["mandatory_plants"][0] == ["Red"] and g["mandatory_plants"][1] == ["Blue"]
    assert env.state.current_player_id == 2


def test_trade_validation():
    env = make_env(num_players=4)
    to_trading(env)
    gs(env)["players"][0]["hand"] = ["Blue"]
    gs(env)["face_up_cards"] = ["Red", "Soy"]
    env.step("trade Garden for Blue")
    assert env.state.error_count == 1
    assert gs(env)["active_trades"] == {}
    env.step("trade 2 Red for Blue")  # only one Red available
    assert env.state.error_count == 2
    assert gs(env)["active_trades"] == {}


def test_gift_trades():
    env = make_env(num_players=4)
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Soy", "Garden"]
    env.step("trade Soy for nothing")
    assert g["active_trades"][1]["offer"] == ["Soy"] and g["active_trades"][1]["want"] == []
    g["players"][1]["hand"] = ["Red", "Blue"]
    env.step("accept 1")
    assert g["mandatory_plants"][1] == ["Soy"] and g["mandatory_plants"][0] == []
    assert g["face_up_cards"] == ["Garden"]
    g["players"][2]["hand"] = ["Blue"]
    env.step("trade Red for nothing")  # Player 2 has no Red: invalid
    assert env.state.error_count == 1
    g["players"][2]["hand"] = ["Red"]
    env.step("trade Red for nothing")
    env.step("pass")  # Player 3
    env.step("accept 2")  # the active player accepts the gift
    assert g["mandatory_plants"][0] == ["Red"] and g["players"][2]["hand"] == []


def test_asking_for_a_gift():
    env = make_env()
    to_trading(env)
    g = gs(env)
    env.step("trade nothing for 1 Blue")
    g["players"][1]["hand"] = ["Blue", "Red"]
    env.step("accept 1")
    assert g["mandatory_plants"][0] == ["Blue"] and g["players"][1]["hand"] == ["Red"]


def test_invalid_trades():
    env = make_env(num_players=4)
    to_trading(env)
    for action in ("trade for Blue", "trade Blue for", "trade Nothing for Nothing"):
        env.step(action)
        assert env.state.error_count >= 1
        assert gs(env)["active_trades"] == {}
    env.step("trade 0 Blue for Red")
    assert gs(env)["active_trades"] == {}


def test_face_up_cards_trading():
    env = make_env(num_players=4)
    to_trading(env)
    g = gs(env)
    assert len(g["face_up_cards"]) == 2
    g["players"][0]["hand"] = ["Chili"]
    g["face_up_cards"] = ["Garden", "Soy"]
    env.step("trade Garden for Blue")
    assert env.state.error_count == 0
    assert g["active_trades"][1]["offer"] == ["Garden"]


def test_face_up_card_is_traded_before_matching_hand_card():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["players"][0]["hand"] = ["Soy", "Red"]
    g["face_up_cards"] = ["Soy", "Blue"]
    g["players"][1]["hand"] = ["Green"]
    env.step("trade 1 Soy for 1 Green")
    env.step("accept 1")
    assert g["face_up_cards"] == ["Blue"]
    assert g["players"][0]["hand"] == ["Soy", "Red"]  # the hand card stays
    assert g["mandatory_plants"][1] == ["Soy"]


def test_hand_cards_are_traded_front_most_first():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["players"][1]["hand"] = ["Blue", "Red", "Blue"]
    env.step("trade nothing for 1 Blue")
    env.step("accept 1")
    assert g["players"][1]["hand"] == ["Red", "Blue"]


def test_received_beans_cannot_be_traded_again():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Garden", "Soy"]
    g["players"][1]["hand"] = ["Red"]
    env.step("trade Garden for nothing")
    env.step("accept 1")  # Player 1 receives the Garden bean, set aside
    env.step("pass")  # Player 2
    env.step("pass")  # Player 0
    env.step("trade Garden for Soy")  # Player 1 offers the received Garden bean
    assert env.state.error_count == 1
    assert g["mandatory_plants"][1] == ["Garden"]


def test_only_trades_with_the_active_player_are_allowed():
    env = make_env()
    to_trading(env)
    g = gs(env)
    env.step("pass")
    g["players"][1]["hand"] = ["Red"]
    env.step("trade Red for Blue with Player 2")
    assert env.state.error_count == 1
    env.step("trade Red for Blue")
    assert g["active_trades"][1]["target"] == 0
    g["players"][2]["hand"] = ["Blue"]
    env.step("accept 1")  # Player 2 cannot accept an offer made to the active player
    assert env.state.error_count == 1
    assert g["active_trades"][1]["status"] == "pending"


def test_targeted_offer_can_only_be_accepted_by_its_target():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Garden", "Soy"]
    env.step("trade Garden for nothing with Player 2")
    assert g["active_trades"][1]["target"] == 2
    env.step("accept 1")
    assert env.state.error_count == 1
    env.step("pass")
    env.step("accept 1")
    assert g["mandatory_plants"][2] == ["Garden"]
    env.step("trade Soy for nothing with Player 0")  # the active player cannot address themselves
    assert env.state.error_count == 1


def test_cancel_own_offer_keeps_the_floor():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Garden", "Soy"]
    env.step("trade Garden for Red")
    env.step("pass")
    env.step("cancel 1")  # Player 2 cannot withdraw Player 0's offer
    assert env.state.error_count == 1
    env.step("pass")
    env.step("cancel 1")
    assert env.state.error_count == 0
    assert g["active_trades"][1]["status"] == "withdrawn"
    assert env.state.current_player_id == 0
    g["players"][1]["hand"] = ["Red"]
    env.step("pass")
    env.step("accept 1")
    assert env.state.error_count == 1


def test_offer_is_withdrawn_when_the_proposer_can_no_longer_pay():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["players"][0]["hand"] = ["Red"]
    g["face_up_cards"] = ["Garden", "Soy"]
    env.step("trade Garden for nothing")
    env.step("pass")
    env.step("pass")
    env.step("trade Garden, Soy for Blue")
    g["players"][1]["hand"] = ["Blue"]
    env.step("accept 1")
    assert g["active_trades"][1]["status"] == "accepted"
    assert g["active_trades"][2]["status"] == "withdrawn"
    assert any("Trade #2 is no longer possible" in message for _, message, _, _ in env.state.events)


def test_harvest_during_trading_keeps_the_floor():
    env = make_env()
    to_trading(env)
    env.step("pass")
    gs(env)["players"][1]["fields"][0] = ("Blue", 4)
    env.step("harvest 1")
    assert env.state.current_player_id == 1
    assert gs(env)["players"][1]["coins"] == 1
    env.step("pass")
    assert env.state.current_player_id == 2


def test_end_trading():
    env = make_env(num_players=4)
    to_trading(env)
    env.step("pass")
    env.step("end trading")  # only the active player may end trading
    assert env.state.error_count == 1
    env.step("pass")
    env.step("pass")
    env.step("pass")
    env.step("end trading")
    assert gs(env)["current_phase"] == "plant_mandatory"


def test_max_trade_rounds_ends_trading_automatically():
    env = make_env(max_trade_rounds=1)
    to_trading(env)
    env.step("pass")
    env.step("pass")
    assert gs(env)["current_phase"] == "draw_trade"
    env.step("Anyone need Soy?")
    assert gs(env)["current_phase"] == "plant_mandatory"
    assert any("Trading ends automatically after 1 round" in message for _, message, _, _ in env.state.events)


def test_trading_rounds_are_unlimited_by_default():
    env = make_env()
    to_trading(env)
    for _ in range(30):
        env.step("pass")
    assert gs(env)["current_phase"] == "draw_trade"
    assert gs(env)["trade_round"] == 11


# ===== MANDATORY PLANTING TESTS =====

def test_plant_mandatory_beans():
    env = make_env(num_players=4)
    g = gs(env)
    g["mandatory_plants"][0] = ["Blue", "Red"]
    g["current_phase"] = "plant_mandatory"
    env.step("plant Blue 1")
    assert g["mandatory_plants"][0] == ["Red"]
    assert g["players"][0]["fields"][0] == ("Blue", 1)


def test_plant_mandatory_with_choice():
    env = make_env(num_players=4)
    g = gs(env)
    g["mandatory_plants"][0] = ["Blue", "Red", "Blue"]
    g["current_phase"] = "plant_mandatory"
    env.step("plant Red 1")
    assert g["mandatory_plants"][0] == ["Blue", "Blue"]


def test_mandatory_plant_validation():
    env = make_env(num_players=4)
    g = gs(env)
    g["players"][0]["fields"][0] = ("Blue", 2)
    g["mandatory_plants"][0] = ["Red"]
    g["current_phase"] = "plant_mandatory"
    env.step("plant Red 1")
    assert env.state.error_count == 1
    assert g["players"][0]["fields"][0] == ("Blue", 2)
    env.step("plant Green 2")  # not one of the set-aside beans
    assert env.state.error_count == 2
    assert g["mandatory_plants"][0] == ["Red"]


def test_face_up_cards_to_mandatory():
    env = make_env(num_players=4)
    to_trading(env)
    face_up = list(gs(env)["face_up_cards"])
    env.step("end trading")
    assert gs(env)["mandatory_plants"][0] == face_up
    assert gs(env)["face_up_cards"] == []


def test_plant_without_bean_name():
    env = make_env()
    g = gs(env)
    g["mandatory_plants"][0] = ["Soy", "Red"]
    g["current_phase"] = "plant_mandatory"
    env.step("plant 2")  # ambiguous: two kinds are waiting
    assert env.state.error_count == 1
    env.step("plant Red 1")
    env.step("plant 2")
    assert g["players"][0]["fields"][1] == ("Soy", 1)


def test_phase_three_order_is_active_player_first_then_clockwise():
    env = make_env(num_players=4)
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Garden", "Soy"]
    g["players"][2]["hand"] = ["Red", "Blue"]
    g["players"][3]["hand"] = ["Chili"]
    env.step("trade Garden for nothing with Player 3")  # Player 0
    env.step("pass")  # Player 1
    env.step("trade Red for nothing")  # Player 2 offers to Player 0
    env.step("accept 1")  # Player 3
    env.step("accept 2")  # Player 0
    env.step("pass")
    env.step("pass")
    env.step("pass")
    env.step("end trading")
    assert g["mandatory_plants"] == {0: ["Red", "Soy"], 1: [], 2: [], 3: ["Garden"]}
    g["players"][0]["fields"] = [None, None]
    g["players"][3]["fields"] = [None, None]
    movers = []
    while g["current_phase"] == "plant_mandatory":
        pid = env.state.current_player_id
        movers.append(pid)
        player = g["players"][pid]
        bean = g["mandatory_plants"][pid][0]
        env.step(f"plant {bean} {fitting_field(player, bean)}")
        assert env.state.error_count == 0
    assert movers == [0, 0, 3]
    assert g["active_player"] == 1 and env.state.current_player_id == 1


def test_nobody_planting_skips_phase_three():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = []  # e.g. nothing could be turned over
    env.step("end trading")
    assert any("nobody has beans to plant" in message for _, message, _, _ in env.state.events)
    assert g["active_player"] == 1 and g["current_phase"] == "plant"
    assert env.state.current_player_id == 1


# ===== HARVESTING TESTS =====

def test_harvest_field_valid():
    env = make_env()
    player = gs(env)["players"][0]
    player["fields"][0] = ("Blue", 4)
    env.step("harvest 1")
    assert player["fields"][0] is None
    assert player["coins"] == 1


def test_harvest_coin_calculation():
    env = make_env()
    player = gs(env)["players"][0]
    for count, expected in ((4, 1), (6, 2), (8, 3), (10, 4)):
        player["fields"][0] = ("Blue", count)
        coins_before = player["coins"]
        env.step("harvest 1")
        assert player["coins"] - coins_before == expected


def test_harvest_priority_rule():
    env = make_env()
    player = gs(env)["players"][0]
    player["fields"][0] = ("Blue", 1)
    player["fields"][1] = ("Red", 2)
    env.step("harvest 1")
    assert env.state.error_count == 1
    assert player["fields"][0] == ("Blue", 1) and player["coins"] == 0
    env.step("harvest 2")
    assert env.state.error_count == 0
    assert player["coins"] == 1 and player["fields"][1] is None
    env.step("harvest 1")  # now no field holds more than one bean
    assert env.state.error_count == 0 and player["fields"][0] is None


def test_harvest_field_clearing():
    env = make_env()
    player = gs(env)["players"][0]
    player["fields"][0] = ("Blue", 5)
    env.step("harvest 1")
    assert player["fields"][0] is None


def test_harvest_discard_pile():
    env = make_env()
    g = gs(env)
    g["players"][0]["fields"][0] = ("Blue", 5)
    env.step("harvest 1")
    # One card becomes the coin and leaves the game; the other four are discarded.
    assert g["players"][0]["coins"] == 1
    assert g["discard_pile"] == ["Blue"] * 4


def test_coin_cards_leave_the_game():
    env = make_env()
    g = gs(env)
    g["players"][0]["fields"] = [("Garden", 3), ("Red", 5), None]
    total_before = total_cards(g)
    env.step("harvest 1")  # three Garden beans pay three coins: every card becomes a coin
    assert g["players"][0]["coins"] == 3 and g["discard_pile"] == []
    env.step("harvest 2")  # five Red beans pay four coins: one card is discarded
    assert g["players"][0]["coins"] == 7 and g["discard_pile"] == ["Red"]
    assert total_cards(g) == total_before


def test_harvest_does_not_use_up_the_move():
    env = make_env()
    g = gs(env)
    g["players"][0]["fields"][0] = ("Red", 3)
    env.step("harvest 1")
    assert env.state.current_player_id == 0
    assert g["current_phase"] == "plant" and g["planted_from_hand"] == 0


# ===== DRAW PHASE TESTS =====

def test_draw_cards():
    env = make_env()
    g = gs(env)
    to_trading(env)
    hand_before = list(g["players"][0]["hand"])
    upcoming = g["deck"][-3:][::-1]
    env.step("end trading")
    finish_planting(env)
    assert g["players"][0]["hand"] == hand_before + upcoming
    draws = [(to, message) for _, message, _, to in env.state.events if message.startswith("You drew")]
    assert draws == [(0, f"You drew {', '.join(upcoming)}; they were added to the back of your hand.")]


def test_draw_action_is_not_needed():
    env = make_env()
    env.step("draw")
    assert env.state.error_count == 1
    env.step("Draw")
    assert env.state.error_count == 2


def test_deck_reshuffling():
    env = make_env()
    g = gs(env)
    g["deck"] = ["Blue"]
    g["discard_pile"] = ["Red", "Green", "Soy"]
    assert env._draw_card() == "Blue"
    # The discard pile is shuffled into a new draw pile as soon as the last card is drawn.
    assert sorted(g["deck"]) == ["Green", "Red", "Soy"]
    assert g["discard_pile"] == []
    assert g["deck_cycles_completed"] == 1


def test_deck_cycle_tracking():
    env = make_env()
    g = gs(env)
    g["deck"] = ["Blue"]
    g["discard_pile"] = ["Red", "Green"]
    env._draw_cards(3)
    assert g["deck_cycles_completed"] == 2
    assert not g["game_ending"]


def test_deck_exhaustion_scenarios():
    env = make_env()
    g = gs(env)
    g["deck"] = ["Blue", "Red"]
    g["discard_pile"] = ["Green", "Chili", "Stink"]
    drawn = env._draw_cards(5)
    assert drawn[:2] == ["Red", "Blue"]
    assert sorted(drawn[2:]) == ["Chili", "Green", "Stink"]
    assert g["deck_cycles_completed"] == 2


def test_empty_draw_and_discard_piles_count_as_running_out():
    env = make_env()
    g = gs(env)
    g["deck"], g["discard_pile"] = [], []
    assert env._draw_cards(3) == []
    assert g["deck_cycles_completed"] == 1


def test_lazy_reshuffle_when_discard_pile_was_empty_at_the_run_out():
    env = make_env()
    g = gs(env)
    g["deck"], g["discard_pile"] = ["Blue"], []
    env._draw_card()
    assert g["deck"] == [] and g["deck_cycles_completed"] == 1
    g["discard_pile"] = ["Red", "Soy"]
    assert env._draw_card() in ("Red", "Soy")
    assert g["deck_cycles_completed"] == 1  # the run-out was already counted


# ===== BEAN TYPE AND PAYOUT TESTS =====

def test_bean_types_configuration():
    assert BEAN_TYPES == {
        "Blue": {"count": 20, "payouts": {1: 4, 2: 6, 3: 8, 4: 10}},
        "Chili": {"count": 18, "payouts": {1: 3, 2: 6, 3: 8, 4: 9}},
        "Stink": {"count": 16, "payouts": {1: 3, 2: 5, 3: 7, 4: 8}},
        "Green": {"count": 14, "payouts": {1: 3, 2: 5, 3: 6, 4: 7}},
        "Soy": {"count": 12, "payouts": {1: 2, 2: 4, 3: 6, 4: 7}},
        "BlackEyed": {"count": 10, "payouts": {1: 2, 2: 4, 3: 5, 4: 6}},
        "Red": {"count": 8, "payouts": {1: 2, 2: 3, 3: 4, 4: 5}},
        "Garden": {"count": 6, "payouts": {2: 2, 3: 3}},
    }


@pytest.mark.parametrize(
    "bean,count,coins",
    [
        ("Blue", 3, 0), ("Blue", 4, 1), ("Blue", 6, 2), ("Blue", 8, 3), ("Blue", 10, 4), ("Blue", 15, 4),
        ("Garden", 1, 0), ("Garden", 2, 2), ("Garden", 3, 3), ("Garden", 5, 3),
        ("Red", 1, 0), ("Red", 2, 1), ("Red", 3, 2), ("Red", 4, 3), ("Red", 5, 4),
        ("Stink", 2, 0), ("Stink", 4, 1), ("Stink", 6, 2), ("Stink", 7, 3), ("Stink", 8, 4),
    ],
)
def test_payout_calculations(bean, count, coins):
    assert BohnanzaEnv._calculate_harvest_coins(bean, count) == coins
    assert harvest_coins(BEAN_TYPES[bean]["payouts"], count) == coins


def test_bean_validation():
    for name in ("Blue", "Chili", "Stink", "Green", "Soy", "BlackEyed", "Red", "Garden"):
        assert canonical_bean(name) == name
    assert canonical_bean("blue") == "Blue"
    assert canonical_bean("Black-eyed beans") == "BlackEyed"
    assert canonical_bean("chilis") == "Chili"
    for name in ("Purple", "Yellow", "Orange", "NotABean", "", "2Blue"):
        assert canonical_bean(name) is None


def test_bean_list_parsing():
    assert parse_bean_list("nothing") == ([], None)
    assert parse_bean_list("2 Blue, Red") == (["Blue", "Blue", "Red"], None)
    assert parse_bean_list("blue and 2x soy") == (["Blue", "Soy", "Soy"], None)
    assert parse_bean_list("a Garden") == (["Garden"], None)
    for text in ("", "Purple", "0 Blue", "21 Blue", "7 Garden", "4 Garden, 3 Garden", "2 Blue,, Red", "999999999 Red"):
        beans, error = parse_bean_list(text)
        assert beans is None and error


# ===== GAME END CONDITION TESTS =====

def test_game_end_after_three_cycles():
    env = make_env()
    g = gs(env)
    g["deck_cycles_completed"] = 2
    to_trading(env)
    g["deck"] = g["deck"][-2:]  # phase 4 draws the last two cards
    env.step("end trading")
    done = finish_planting(env)
    assert done
    assert g["deck_cycles_completed"] == 3 and g["deck"] == []
    assert len(g["players"][0]["hand"]) == 4 + 2
    assert "run out for the last time" in env.state.game_info[0]["reason"]


def test_run_out_while_turning_over_finishes_phases_two_and_three():
    env = make_env()
    g = gs(env)
    g["deck_cycles_completed"] = 2
    g["deck"] = ["Garden"]
    g["discard_pile"] = ["Red"] * 4
    env.step("plant 1")
    env.step("pass")
    assert g["face_up_cards"] == ["Garden"]  # only one card could be turned over
    assert g["game_ending"] and g["discard_pile"] == ["Red"] * 4  # no third reshuffle
    hand = list(g["players"][0]["hand"])
    env.step("trade nothing for Red")  # trading still happens
    env.step("pass")
    env.step("pass")
    done, _ = env.step("end trading")
    assert not done and g["current_phase"] == "plant_mandatory"
    done, _ = env.step("plant Garden 2")
    assert done
    assert g["players"][0]["hand"] == hand  # no phase 4 draw
    assert g["players"][0]["fields"][1] is None  # harvested at the end


def test_deck_cycles_variant_ends_at_first_run_out():
    env = make_env(deck_cycles=1)
    g = gs(env)
    to_trading(env)
    g["deck"] = g["deck"][-1:]
    env.step("end trading")
    done = finish_planting(env)
    assert done and g["deck_cycles_completed"] == 1


def test_final_harvest():
    env = make_env()
    for player in gs(env)["players"].values():
        player["fields"] = [("Blue", 5), ("Red", 3), ("Green", 2)]
    outcome = env._final_outcome("Test end.")
    for player in gs(env)["players"].values():
        assert player["fields"] == [None, None, None]
        assert player["coins"] == 1 + 2 + 0
    assert isinstance(outcome, ta.Outcome)


def test_winner_determination():
    env = make_env()
    for pid, coins in enumerate((10, 15, 8)):
        gs(env)["players"][pid]["coins"] = coins
    outcome = env._final_outcome("Test end.")
    assert outcome.rewards == {0: -1, 1: 1, 2: -1}
    assert "Player 1 wins with 15 coins" in outcome.reason


def test_tie_breaking():
    env = make_env()
    for pid in range(3):
        gs(env)["players"][pid]["coins"] = 10
    outcome = env._final_outcome("Test end.")
    assert outcome.rewards == {0: -1, 1: -1, 2: 1}  # furthest clockwise from the starting player
    env = make_env()
    for pid, coins in enumerate((9, 9, 4)):
        gs(env)["players"][pid]["coins"] = coins
    outcome = env._final_outcome("Test end.")
    assert outcome.rewards == {0: -1, 1: 1, 2: -1}
    assert "tie-break" in outcome.reason


# ===== ACTION PARSING TESTS =====

def test_plant_action_parsing():
    assert parse_command("plant 1") == ("plant", {"bean": None, "field": 1})
    assert parse_command("Plant field 2") == ("plant", {"bean": None, "field": 2})
    assert parse_command("plant Blue 2") == ("plant", {"bean": "Blue", "field": 2})
    assert parse_command("plant black-eyed into field 1") == ("plant", {"bean": "black-eyed", "field": 1})
    assert parse_command("plant") is None
    assert parse_command("plant Blue") is None
    assert parse_command("I will plant 1") is None


def test_trade_action_parsing():
    assert parse_command("trade Blue for Red") == ("trade", {"offer": "Blue", "want": "Red", "target": None})
    assert parse_command("trade 2 Blue for Red") == ("trade", {"offer": "2 Blue", "want": "Red", "target": None})
    assert parse_command("Trade Blue for Nothing") == ("trade", {"offer": "Blue", "want": "Nothing", "target": None})
    assert parse_command("trade 1 Soy for 1 Red with Player 2") == ("trade", {"offer": "1 Soy", "want": "1 Red", "target": 2})
    assert parse_command("offer Soy for Red to 1") == ("trade", {"offer": "Soy", "want": "Red", "target": 1})
    assert parse_command("trade Blue") is None
    assert parse_command("trade for Red") is None


def test_harvest_action_parsing():
    assert parse_command("harvest 1") == ("harvest", {"field": 1})
    assert parse_command("Harvest field 2") == ("harvest", {"field": 2})
    assert parse_command("harvest") is None
    assert parse_command("harvest all") is None


def test_accept_action_parsing():
    for text, trade_id in (("accept 1", 1), ("accept 10", 10), ("accept trade 3", 3), ("accept #4", 4), ("Accept Trade1", 1)):
        assert parse_command(text) == ("accept", {"trade_id": trade_id})
    assert parse_command("accept") is None
    assert parse_command("accept trade") is None


def test_other_command_parsing():
    assert parse_command("pass") == ("pass", {})
    assert parse_command("Pass.") == ("pass", {})
    for text in ("end trading", "End Trading", "EndTrading", "end"):
        assert parse_command(text) == ("end_trading", {})
    assert parse_command("cancel 2") == ("cancel", {"trade_id": 2})
    assert parse_command("withdraw trade 2") == ("cancel", {"trade_id": 2})
    assert parse_command("draw") == ("draw", {})
    assert normalize_command("  `plant   1`  ") == "plant 1"


@pytest.mark.parametrize("action", ["", "   ", "random text", "[InvalidAction]", "plant", "trade", "harvest", "1"])
def test_invalid_action_formats(action):
    env = make_env()
    before = copy.deepcopy(gs(env))
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert gs(env) == before


@pytest.mark.parametrize("action", ["plant 9999999999", "plant " + "9" * 5000, "trade 999999999 Blue for Red", "accept " + "1" * 50])
def test_huge_numbers_are_rejected_without_crashing(action):
    env = make_env()
    if action.startswith(("trade", "accept")):
        to_trading(env)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1


# ===== ERROR HANDLING TESTS =====

def test_invalid_move_handling():
    env = make_env()
    hand = list(gs(env)["players"][0]["hand"])
    env.step("plant 0")
    assert env.state.error_count == 1 and gs(env)["players"][0]["hand"] == hand
    env.step("harvest 1")
    assert env.state.error_count == 2 and gs(env)["players"][0]["fields"][0] is None


def test_error_allowance():
    env = make_env()
    env.step("invalid action")
    assert env.state.error_count == 1
    env.step("plant 1")
    assert env.state.error_count == 0


def test_out_of_bounds_field_numbers():
    env = make_env()
    hand = list(gs(env)["players"][0]["hand"])
    env.step("plant 10")
    assert env.state.error_count == 1 and gs(env)["players"][0]["hand"] == hand
    env.step("harvest 5")
    assert env.state.error_count == 2 and gs(env)["players"][0]["coins"] == 0


def test_empty_field_harvest():
    env = make_env()
    env.step("harvest 1")
    assert env.state.error_count == 1
    assert gs(env)["players"][0]["coins"] == 0


def test_invalid_moves_do_not_change_the_state():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["players"][0]["hand"] = ["Blue"]
    g["face_up_cards"] = ["Red", "Soy"]
    env.step("trade Red for Green")
    g["players"][1]["hand"] = ["Blue", "Chili"]  # Player 1 cannot pay the Green
    for action in ("trade 3 Red for Blue", "accept 1", "accept 7", "cancel 1", "cancel 9", "plant 1", "end trading", "trade Purple for Blue"):
        before = copy.deepcopy(g)
        env.step(action)
        assert env.state.error_count == 1, action
        assert g == before, action
        env.state.error_count = 0


# ===== COMPLEX SCENARIO TESTS =====

def test_complete_game_flow():
    env = make_env()
    for turn in range(20):
        assert gs(env)["active_player"] == turn % 3
        assert not play_turn(env)
    assert gs(env)["turn_number"] == 21


def test_multiple_trades_in_turn():
    env = make_env(num_players=4)
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["Garden", "Soy"]
    env.step("trade Garden for Blue")
    env.step("pass")
    env.step("pass")
    env.step("pass")
    env.step("trade Soy for Red")
    assert [trade["status"] for trade in g["active_trades"].values()] == ["pending", "pending"]


def test_complex_mandatory_planting():
    env = make_env(num_players=4)
    g = gs(env)
    g["mandatory_plants"][0] = ["Blue", "Red", "Blue", "Green"]
    g["current_phase"] = "plant_mandatory"
    env.step("plant Blue 1")
    env.step("plant Red 2")
    env.step("plant Blue 1")
    assert g["players"][0]["fields"] == [("Blue", 2), ("Red", 1)]
    assert g["mandatory_plants"][0] == ["Green"]
    env.step("plant Green 1")
    assert env.state.error_count == 1


# ===== OBSERVATION AND RENDERING TESTS =====

def test_player_observation_content():
    env = make_env()
    player_id, observation = env.get_observation()
    text = "\n".join(message for _, message, _ in observation)
    assert player_id == 0
    assert "You are Player 0" in text and "BOHNANZA" in text
    hand = gs(env)["players"][0]["hand"]
    assert f"Your hand, front to back: {', '.join(hand)}" in text


def test_private_information_hiding():
    env = make_env(num_players=4)
    g = gs(env)
    hands = {pid: ["Blue", "Chili", "Stink", "Green", "Soy"] for pid in range(4)}
    hands[2] = ["Garden", "Garden", "Red", "Red", "BlackEyed"]
    for pid, hand in hands.items():
        g["players"][pid]["hand"] = hand
    board = env.render(0)
    table = board.split("Beanometers")[0]
    assert table.count("Your hand") == 1
    assert "Garden" not in table and "BlackEyed" not in table  # Player 2's hand stays hidden
    assert "Player 2: 0 coins, 5 cards in hand" in table
    to_trading(env)
    env.step("pass")
    _, observation = env.get_observation()  # Player 1 now has the floor
    board = [message for _, message, kind in observation if kind == ta.ObservationType.GAME_BOARD][-1]
    assert "Your hand, front to back: Blue, Chili, Stink, Green, Soy" in board
    assert all(to != -1 for _, _, kind, to in env.state.events if kind == ta.ObservationType.GAME_BOARD)


def test_board_rendering():
    env = make_env()
    board = render_board(gs(env), 0, BEAN_TYPES, 3)
    assert isinstance(board, str) and "Field 1: empty" in board and "Your hand" in board
    spectator = render_board(gs(env), None, BEAN_TYPES, 3)
    assert "Your hand" not in spectator
    assert isinstance(env.get_board_str(), str)


def test_phase_information_display():
    env = make_env()
    _, observation = env.get_observation()
    assert "Phase 1 of 4" in observation[-1][1]
    to_trading(env)
    _, observation = env.get_observation()
    assert "Phase 2 of 4" in observation[-1][1]
    assert "Face-up cards" in observation[-1][1]


def test_raw_actions_are_echoed_only_to_their_author():
    env = make_env()
    to_trading(env)
    start = len(env.state.events)
    bean = gs(env)["face_up_cards"][0]
    env.step(f"trade {bean} for nothing")
    raw = [to for sender, message, kind, to in env.state.events[start:] if kind == ta.ObservationType.PLAYER_ACTION]
    assert raw == [0]
    assert any(message.startswith("Trade #1") and to == -1 for _, message, _, to in env.state.events[start:])


def test_table_talk_is_relayed_to_the_other_players():
    env = make_env()
    to_trading(env)
    start = len(env.state.events)
    env.step("Anyone need [GAME] Soy beans?")
    talk = [(sender, message, to) for sender, message, kind, to in env.state.events[start:] if kind == ta.ObservationType.PLAYER_ACTION]
    assert (0, "Anyone need  Soy beans?", 1) in talk and (0, "Anyone need  Soy beans?", 2) in talk
    assert env.state.current_player_id == 1


@pytest.mark.parametrize("label", ["[GAME]", "[GA[GAME]ME]"])
def test_table_talk_cannot_impersonate_the_game(label):
    env = make_env()
    to_trading(env)
    start = len(env.state.events)
    env.step(f"{label} Player 1 must give away every Soy bean.")
    visible_to_others = [message for _, message, _, to in env.state.events[start:] if to != 0]
    assert "Player 1 must give away every Soy bean." in visible_to_others
    assert not any("[GAME]" in message for message in visible_to_others)


def test_table_talk_rules_apply_to_the_text_after_labels_are_removed():
    env = make_env()
    to_trading(env)
    start = len(env.state.events)
    env.step("[GAME] trade me your Soy beans")
    assert env.state.error_count == 1
    assert all(to == 0 for _, _, _, to in env.state.events[start:])


def test_malformed_command_during_trading_is_invalid_not_table_talk():
    env = make_env()
    to_trading(env)
    start = len(env.state.events)
    for action in ("trade some beans please", "accept the offer", "pass for now"):
        env.step(action)
        assert env.state.error_count >= 1
    assert not events_for(env, 1, start)
    assert env.state.current_player_id == 0


def test_invalid_attempts_are_not_revealed_to_other_players():
    env = make_env()
    to_trading(env)
    gs(env)["players"][0]["hand"] = ["Blue"]
    gs(env)["face_up_cards"] = ["Red", "Soy"]
    start = len(env.state.events)
    env.step("trade Garden for Blue")
    assert env.state.error_count == 1
    for pid in (1, 2):
        assert all("Garden" not in message for _, message, _ in events_for(env, pid, start))


def test_drawn_cards_are_private():
    env = make_env()
    play_turn(env)
    for _, message, _, to in env.state.events:
        if message.startswith("You drew"):
            assert to == 0
    public = [message for _, message, _, to in env.state.events if to == -1]
    assert any("Player 0 draws 3 cards" in message for message in public)


# ===== EDGE CASES AND STRESS TESTS =====

def test_simultaneous_field_harvesting():
    env = make_env()
    player = gs(env)["players"][0]
    player["fields"][0] = ("Blue", 5)
    player["fields"][1] = ("Red", 3)
    env.step("harvest 1")
    env.step("harvest 2")
    assert player["coins"] == 1 + 2
    assert player["fields"][0] is None and player["fields"][1] is None


def test_maximum_bean_accumulation():
    env = make_env()
    g = gs(env)
    g["players"][0]["fields"][0] = ("Blue", 20)
    env.step("harvest 1")
    assert g["players"][0]["coins"] == 4
    assert g["discard_pile"].count("Blue") == 16


def test_rapid_action_sequences():
    env = make_env()
    for action in ("plant 1", "pass", "end trading"):
        env.step(action)
        assert env.state.error_count == 0
    finish_planting(env)
    assert env.state.error_count == 0 and gs(env)["active_player"] == 1


def test_long_games_do_not_accumulate_unconsumed_observations():
    env = make_env()
    for _ in range(15):
        env.get_observation()
        assert not play_turn(env)
    for player_id, messages in env.state.observations.items():
        assert len(messages) < 100, player_id
    env.get_observation()
    assert env.state.observations[env.state.current_player_id] == []


def test_bean_names_are_case_insensitive_in_actions():
    env = make_env()
    to_trading(env)
    g = gs(env)
    g["face_up_cards"] = ["BlackEyed", "Soy"]
    env.step("trade 1 black-eyed for 1 RED")
    assert g["active_trades"][1]["offer"] == ["BlackEyed"] and g["active_trades"][1]["want"] == ["Red"]


# ===== INTEGRATION TESTS =====

def test_full_trading_workflow():
    env = make_env(num_players=4)
    to_trading(env)
    g = gs(env)
    g["players"][0]["hand"] = ["Chili", "Blue"]
    g["face_up_cards"] = ["Soy", "Garden"]
    g["players"][1]["hand"] = ["Red", "Green"]
    env.step("pass")
    env.step("trade 1 Red for 1 Soy")  # Player 1 offers to the active player
    env.step("pass")
    env.step("pass")
    env.step("accept 1")  # Player 0
    assert g["mandatory_plants"][0] == ["Red"] and g["mandatory_plants"][1] == ["Soy"]
    assert g["face_up_cards"] == ["Garden"]
    env.step("pass")
    env.step("pass")
    env.step("pass")
    env.step("end trading")
    assert g["mandatory_plants"][0] == ["Red", "Garden"]
    finish_planting(env)
    assert g["active_player"] == 1
    assert g["mandatory_plants"] == {0: [], 1: [], 2: [], 3: []}
    assert any(field is not None and field[0] == "Soy" for field in g["players"][1]["fields"])


def test_game_state_consistency():
    env = make_env()
    for _ in range(10):
        g = gs(env)
        assert len(g["players"]) == 3
        assert 0 <= env.state.current_player_id < 3
        assert g["current_phase"] in ("plant", "draw_trade", "plant_mandatory")
        assert 0 <= g["deck_cycles_completed"] <= 3
        play_turn(env)


def test_bean_conservation():
    env = make_env()
    g = gs(env)
    assert total_cards(g) == DECK_SIZE
    for _ in range(15):
        to_trading(env)
        active = g["active_player"]
        env.step(f"trade {g['face_up_cards'][0]} for nothing")  # gift a face-up card to the next player
        env.step(f"accept {g['trade_counter']}")
        assert g["mandatory_plants"][(active + 1) % 3]
        env.step("pass")
        env.step("end trading")
        assert total_cards(g) == DECK_SIZE
        finish_planting(env)
        assert total_cards(g) == DECK_SIZE
        assert env.state.error_count == 0


def test_snapshot_restore_replays_reshuffle():
    env = make_env()
    g = gs(env)
    g["deck"] = g["deck"][-3:]  # the reshuffle happens during this turn's draw
    g["discard_pile"] = ["Blue", "Red", "Soy", "Green", "Chili", "Stink"]
    snapshot = env.snapshot()
    play_turn(env)
    first = copy.deepcopy(gs(env))
    env.restore(snapshot)
    play_turn(env)
    assert gs(env) == first
    assert gs(env)["deck_cycles_completed"] == 1


@pytest.mark.parametrize("env_id,deck_cycles,max_trade_rounds", [("Bohnanza-v1", 3, None), ("Bohnanza-v1-short", 1, 3)])
def test_registered_variants(env_id, deck_cycles, max_trade_rounds):
    for num_players in (3, 4, 5):
        for suffix in ("", "-mdp"):
            env = ta.make(env_id + suffix)
            env.reset(num_players=num_players, seed=3)
            player_id, observation = env.get_observation()
            assert player_id == 0 and "You are Player 0" in observation
            assert env.deck_cycles == deck_cycles and env.max_trade_rounds == max_trade_rounds


# ===== TERMINATION =====

def test_exhausting_error_allowance_forfeits():
    env = make_env()
    done = False
    for _ in range(env.error_allowance + 1):
        assert not done
        done, _ = env.step("not a valid action")
    assert done
    rewards, info = env.close()
    assert rewards == {0: -1, 1: 0, 2: 0}
    assert "forfeits" in info[0]["reason"]


def test_turn_limit_scores_game():
    env = make_env(max_turns=30)
    to_trading(env)
    done = False
    while not done:
        done, _ = env.step("Let us keep talking about beans.")  # trading never ends on its own
    assert env.state.turn == 30
    rewards, info = env.close()
    assert sorted(rewards.values()) == [-1, -1, 1]
    assert "turn limit" in info[0]["reason"]


@pytest.mark.parametrize("num_players", [3, 4, 5])
def test_full_game_terminates_with_valid_play(num_players):
    env = make_env(num_players=num_players, seed=1, max_turns=3000)
    done, steps = play_simple_game(env)
    g = gs(env)
    assert done and steps < env.max_turns
    assert g["deck_cycles_completed"] == 3
    assert total_cards(g) == DECK_SIZE
    assert all(field is None for player in g["players"].values() for field in player["fields"])
    rewards, info = env.close()
    assert sorted(rewards.values()) == [-1] * (num_players - 1) + [1]
    best = max(player["coins"] for player in g["players"].values())
    winner = max(pid for pid, player in g["players"].items() if player["coins"] == best)
    assert rewards[winner] == 1


def _random_action(env, rng):
    """A random, mostly legal action for whoever has the move."""
    g = gs(env)
    pid = env.state.current_player_id
    player = g["players"][pid]
    phase = g["current_phase"]
    if rng.random() < 0.03:
        return rng.choice(["nonsense", "plant 9", "harvest 7", "trade Purple for Red", "accept 999", "draw"])
    if phase == "plant":
        if g["planted_from_hand"] and rng.random() < 0.5:
            return "pass"
        field = fitting_field(player, player["hand"][0])
        return f"plant {field}" if field else f"harvest {harvestable_field(player)}"
    if phase == "plant_mandatory":
        bean = rng.choice(g["mandatory_plants"][pid])
        field = fitting_field(player, bean)
        return f"plant {bean} {field}" if field else f"harvest {harvestable_field(player)}"
    pending = {tid: trade for tid, trade in g["active_trades"].items() if trade["status"] == "pending"}
    mine = Counter(player["hand"] + (g["face_up_cards"] if pid == g["active_player"] else []))
    acceptable = [
        tid for tid, trade in pending.items()
        if trade["proposer"] != pid and trade["target"] in (None, pid) and not Counter(trade["want"]) - mine
    ]
    roll = rng.random()
    if pid == g["active_player"] and roll < 0.3:
        return "end trading"
    if acceptable and roll < 0.55:
        return f"accept {rng.choice(acceptable)}"
    if roll < 0.8 and mine:
        offer = rng.choice(sorted(mine.elements()))
        want = rng.choice(["nothing", rng.choice(list(BEAN_TYPES))])
        return f"trade {offer} for {want}"
    return rng.choice(["pass", "Who wants beans?"])


@pytest.mark.parametrize("num_players", [3, 4, 5])
@pytest.mark.parametrize("seed", [0, 1])
def test_random_play_conserves_cards_keeps_hands_private_and_terminates(num_players, seed):
    env = make_env(num_players=num_players, seed=seed, max_turns=3000)
    rng = random.Random(seed)
    done = False
    while not done:
        before_events = len(env.state.events)
        before_state = copy.deepcopy(gs(env))
        done, _ = env.step(_random_action(env, rng))
        g = gs(env)
        assert total_cards(g) == DECK_SIZE
        if env.state.error_count:
            assert g == before_state  # invalid moves are atomic
        for _, message, kind, to in env.state.events[before_events:]:
            assert not (kind == ta.ObservationType.PLAYER_ACTION and to == -1)
            if kind == ta.ObservationType.GAME_BOARD:
                assert to == env.state.current_player_id
                hand = g["players"][to]["hand"]
                assert message.count("Your hand") == 1
                assert (f"Your hand, front to back: {', '.join(hand)}" if hand else "Your hand is empty.") in message
            if message.startswith("You drew"):
                assert to == before_state["active_player"]
    assert env.state.turn < 3000
    assert gs(env)["deck_cycles_completed"] == 3
    rewards, _ = env.close()
    assert sorted(rewards.values()).count(1) == 1
