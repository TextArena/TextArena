"""Offline deterministic tests for the UltimateTexasHoldem environment.

Single-player-vs-dealer poker. It is fully offline (a local shuffled deck; no
network/LLM). The overall game only terminates on chip depletion (loss) or after
``max_rounds`` rounds (win), so we shrink those knobs to script deterministic
terminal outcomes. Folding always forfeits ANTE+BLIND regardless of the cards,
which lets us drive a guaranteed bust without depending on the random deal.
Actions: '4x', '2x', '1x', 'check', 'fold', 'skip'.
"""

import pytest

from textarena.envs.UltimateTexasHoldem.env import UltimateTexasHoldemEnv


def _fresh(max_rounds=1000, start_chips=1000, ante_amount=25):
    env = UltimateTexasHoldemEnv(max_rounds=max_rounds, start_chips=start_chips, ante_amount=ante_amount)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_deals_cards_and_posts_blinds():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["player_hand"]) == 2
    assert len(gs["dealer_hand"]) == 2
    assert len(gs["community_cards"]) == 5
    assert gs["current_round"] == 1
    assert gs["current_phase"] == "pre_flop"
    # ANTE + BLIND posted and deducted from the starting stack.
    assert gs["ante_bet"] == 25 and gs["blind_bet"] == 25
    assert gs["chips"] == 1000 - 50


def test_reset_rejects_multiplayer():
    env = UltimateTexasHoldemEnv()
    with pytest.raises(ValueError):
        env.reset(num_players=2, seed=42)


def test_four_x_bet_transitions_and_deducts():
    env = _fresh()
    done = env.step("4x")  # pre-flop 4x play bet -> flop
    gs = env.state.game_state
    assert not done
    assert gs["play_bet"] == 100
    assert gs["current_phase"] == "flop"
    assert gs["legal_actions"] == ["skip"]


def test_three_x_bet_is_legal_preflop_and_deducts():
    env = _fresh()
    done = env.step("3x")
    gs = env.state.game_state
    assert not done
    assert gs["play_bet"] == 75
    assert gs["chips"] == 875
    assert gs["current_phase"] == "flop"
    assert gs["legal_actions"] == ["skip"]


def test_check_progresses_through_streets():
    env = _fresh()
    env.step("check")  # pre_flop -> flop
    assert env.state.game_state["current_phase"] == "flop"
    env.step("check")  # flop -> river
    assert env.state.game_state["current_phase"] == "river"
    # A full round resolves at the river; a new round should begin.
    done = env.step("fold")
    assert not done
    assert env.state.game_state["current_round"] == 2


@pytest.mark.parametrize(
    "actions",
    [
        ["4x", "skip", "skip"],
        ["3x", "skip", "skip"],
        ["check", "2x", "skip"],
        ["check", "check", "1x"],
    ],
)
def test_every_betting_branch_completes_a_full_round(actions):
    env = _fresh(max_rounds=1)
    done = False
    for action in actions:
        assert not done
        done = env.step(action)
    assert done
    assert env.state.game_state["current_phase"] == "showdown"
    assert env.state.rewards == {0: 1.0}


def test_invalid_action_for_phase_rejected():
    env = _fresh()
    # 'fold' is not legal pre-flop (only '4x'/'check').
    env.step("fold")
    assert env.state.error_count == 1
    assert not env.state.done


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("fold")  # invalid pre-flop (first)
    env.step("fold")  # invalid pre-flop (second) -> game over
    assert env.state.done
    assert env.state.rewards == {0: 0}


def test_folding_until_bust_loses():
    # Small stack: two folded rounds (-50 each) empties the 100-chip stack.
    env = _fresh(start_chips=100)
    done = False
    for _ in range(2):
        env.step("check")  # pre_flop -> flop
        env.step("check")  # flop -> river
        done = env.step("fold")   # forfeit ante+blind
    assert env.state.game_state["chips"] <= 0
    assert done
    assert env.state.rewards == {0: 0}


def test_completing_max_rounds_wins():
    # With max_rounds=1, the first complete round ends the game as a win.
    env = _fresh(max_rounds=1)
    env.step("check")
    env.step("check")
    done = env.step("fold")
    assert done
    assert env.state.rewards == {0: 1.0}


def test_custom_ante_controls_every_play_bet_amount():
    env = _fresh(start_chips=200, ante_amount=10)
    gs = env.state.game_state
    assert gs["chips"] == 180
    env.step("4x")
    assert gs["play_bet"] == 40
    assert gs["chips"] == 140
    assert gs["total_bet"] == 60


def test_insufficient_play_bet_is_invalid_and_atomic():
    env = _fresh(start_chips=100)
    gs = env.state.game_state
    before = (gs["chips"], gs["play_bet"], gs["total_bet"], gs["current_phase"])
    done = env.step("4x")
    assert not done
    assert env.state.error_count == 1
    assert (gs["chips"], gs["play_bet"], gs["total_bet"], gs["current_phase"]) == before


def test_dealt_and_undealt_cards_form_one_unique_deck():
    env = _fresh()
    gs = env.state.game_state
    cards = gs["player_hand"] + gs["dealer_hand"] + gs["community_cards"] + gs["deck"]
    encoded = [(card["rank"], card["suit"]) for card in cards]
    assert len(encoded) == 52
    assert len(set(encoded)) == 52


def test_tied_showdown_pushes_all_bets():
    env = _fresh()
    gs = env.state.game_state
    gs["community_cards"] = [
        {"rank": "10", "suit": "♠"},
        {"rank": "J", "suit": "♠"},
        {"rank": "Q", "suit": "♠"},
        {"rank": "K", "suit": "♠"},
        {"rank": "A", "suit": "♠"},
    ]
    gs["player_hand"] = [{"rank": "2", "suit": "♥"}, {"rank": "3", "suit": "♥"}]
    gs["dealer_hand"] = [{"rank": "4", "suit": "♦"}, {"rank": "5", "suit": "♦"}]
    assert env._calculate_ante_result(25, gs["player_hand"], gs["dealer_hand"]) == 25
    assert env._calculate_blind_result(25, gs["player_hand"], gs["dealer_hand"]) == 25
    assert env._calculate_play_result(100, gs["player_hand"], gs["dealer_hand"]) == 100


def test_dealer_hand_hidden_until_terminal_showdown():
    env = _fresh(max_rounds=1)
    dealer_cards = [
        f"{card['rank']}{card['suit']}" for card in env.state.game_state["dealer_hand"]
    ]
    board = env.get_board_str()
    assert "Dealer's hand: [Hidden]" in board
    assert all(card not in board for card in dealer_cards)
    env.step("check")
    env.step("check")
    env.step("fold")
    board = env.get_board_str()
    assert all(card in board for card in dealer_cards)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"start_chips": 49, "ante_amount": 25}, "initial ante"),
    ],
)
def test_invalid_configuration_is_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        UltimateTexasHoldemEnv(**kwargs)


@pytest.mark.parametrize("action", ["4x check", "check\n4x", "[4x] [check]"])
def test_mixed_or_duplicate_actions_are_rejected_atomically(action):
    env = _fresh()
    gs = env.state.game_state
    before = (
        gs["chips"],
        gs["play_bet"],
        gs["total_bet"],
        gs["current_phase"],
        list(gs["visible_community_cards"]),
    )
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert (
        gs["chips"],
        gs["play_bet"],
        gs["total_bet"],
        gs["current_phase"],
        gs["visible_community_cards"],
    ) == before


def test_nonqualifying_dealer_pushes_ante_even_when_dealer_hand_is_higher():
    env = _fresh()
    gs = env.state.game_state
    gs["community_cards"] = [
        {"rank": "2", "suit": "♠"},
        {"rank": "4", "suit": "♥"},
        {"rank": "6", "suit": "♦"},
        {"rank": "8", "suit": "♣"},
        {"rank": "10", "suit": "♠"},
    ]
    player = [{"rank": "3", "suit": "♥"}, {"rank": "7", "suit": "♦"}]
    dealer = [{"rank": "A", "suit": "♥"}, {"rank": "K", "suit": "♦"}]
    assert env._evaluate_hand(dealer + gs["community_cards"]) > env._evaluate_hand(
        player + gs["community_cards"]
    )
    assert env._calculate_ante_result(25, player, dealer) == 25


def test_blind_flush_uses_official_three_to_two_payout():
    env = _fresh()
    # Return includes the original wager plus 3:2 winnings.
    assert env._get_blind_payout(10, 6) == 15
    assert env._get_blind_payout(25, 6) == 37.5


def test_every_decision_shows_hand_board_and_available_actions():
    import textarena as ta

    env = ta.make("UltimateTexasHoldem-v1")
    env.reset(num_players=1, seed=42)
    gs = env.env.state.game_state
    _, observation = env.get_observation()
    assert "ROUND 0" not in observation and "No cards yet" not in observation
    assert f"Your hand: {env.env._cards_str(gs['player_hand'])}" in observation
    assert "Community cards: none revealed (5 still hidden)" in observation
    assert "Available actions: '4x', '3x', 'check'" in observation
    env.step("4x")
    _, observation = env.get_observation()
    assert f"Community cards: {env.env._cards_str(gs['community_cards'][:3])} (2 still hidden)" in observation
    assert "Available actions: 'skip'" in observation
    assert all(f"{c['rank']}{c['suit']}" not in observation for c in gs["dealer_hand"])


def test_invalid_action_feedback_names_the_bare_commands():
    env = _fresh()
    env.step("fold")
    feedback = [message for _, message, _, _ in env.state.events if "Invalid action for current phase" in message]
    assert len(feedback) == 1
    assert "Available actions: '4x', '3x', 'check'" in feedback[0]


def test_prompt_interpolates_configured_play_bet_amounts():
    env = _fresh(ante_amount=10)
    prompt = env.prompt(0)
    assert "$40 PLAY bet" in prompt
    assert "$30 PLAY bet" in prompt
    assert "Royal Flush: 500:1 ($5000)" in prompt
    assert "Flush: 3:2 ($15)" in prompt
    assert "${self.ante_amount" not in prompt
