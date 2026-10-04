"""Deterministic game-logic tests for Blackjack-v1 (single player vs dealer)."""
import copy

from textarena.envs.Blackjack.env import BlackjackEnv


def _fresh(num_hands=1):
    env = BlackjackEnv(num_hands=num_hands)
    env.reset(num_players=1, seed=42)
    return env


def test_reset_deals_initial_cards():
    env = _fresh()
    gs = env.state.game_state
    assert len(gs["player_hand"]) == 2
    assert len(gs["dealer_hand"]) == 2
    assert gs["hand_number"] == 1


def test_hit_adds_card():
    env = _fresh()
    # Force a low hand so hitting cannot bust.
    env.state.game_state["player_hand"] = ["2♠", "2♥"]
    done, _ = env.step("hit")
    assert not done
    assert len(env.state.game_state["player_hand"]) == 3


def test_stand_win_yields_full_reward():
    env = _fresh(num_hands=1)
    # Player 20 vs a dealer that already stands on 17 -> guaranteed win.
    env.state.game_state["player_hand"] = ["K♠", "K♥"]
    env.state.game_state["dealer_hand"] = ["10♠", "7♥"]
    done, _ = env.step("stand")
    assert done
    assert env.state.rewards == {0: 1.0}


def test_bust_yields_zero_reward():
    env = _fresh(num_hands=1)
    done = False
    for _ in range(30):  # infinite deck: hitting repeatedly must eventually bust
        done, _ = env.step("hit")
        if done:
            break
    assert done
    assert env.state.rewards == {0: 0.0}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("do something")
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh(num_hands=1)
    env.step("nonsense")
    done, _ = env.step("more nonsense")
    assert done
    # no hands were won, so the anti-reward-hacking payout is 0.0
    assert env.state.rewards == {0: 0.0}


def test_draw_counts_as_half_credit():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["10♠", "7♥"]
    gs["dealer_hand"] = ["9♠", "8♥"]
    done, _ = env.step("stand")
    assert done
    assert gs["results_summary"] == {"win": 0, "lose": 0, "draw": 1}
    assert env.state.rewards == {0: 0.5}


def test_multi_hand_reward_uses_wins_and_draws():
    env = _fresh(num_hands=2)
    gs = env.state.game_state
    gs["player_hand"] = ["10♠", "7♥"]
    gs["dealer_hand"] = ["9♠", "8♥"]
    done, _ = env.step("stand")
    assert not done
    gs["player_hand"] = ["K♠", "K♥"]
    gs["dealer_hand"] = ["10♠", "7♥"]
    done, _ = env.step("stand")
    assert done
    assert gs["results_summary"] == {"win": 1, "lose": 0, "draw": 1}
    assert env.state.rewards == {0: 0.75}


def test_aces_are_downgraded_individually():
    env = _fresh()
    assert env._hand_score(["A♠", "A♥", "9♦"]) == 21
    assert env._hand_score(["A♠", "A♥", "9♦", "K♣"]) == 21


def test_dealer_draws_to_seventeen_and_busts():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["10♠", "9♥"]
    gs["dealer_hand"] = ["10♦", "6♣"]
    env._draw_card = lambda: "K♠"
    done, _ = env.step("stand")
    assert done
    assert gs["dealer_hand"] == ["10♦", "6♣", "K♠"]
    assert env.state.rewards == {0: 1.0}


def test_dealer_hole_card_is_hidden_until_hand_finishes():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["10♠", "8♥"]
    gs["dealer_hand"] = ["9♦", "8♣"]
    start = len(env.state.events)
    env._observe_state()
    active_messages = [message for _, message, _, _ in env.state.events[start:]]
    assert all("8♣" not in message for message in active_messages)
    env.step("stand")
    assert any("8♣" in message for _, message, _, _ in env.state.events[start:])


def test_invalid_action_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("hit twice")
    assert env.state.game_state == before


def test_blackjack_beats_a_dealer_21_and_settles_without_a_dealer_draw():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["A♠", "K♥"]
    gs["dealer_hand"] = ["9♦", "2♣"]
    env._draw_card = lambda: "K♠"  # would give the dealer 21 if the dealer drew
    done, _ = env.step("stand")
    assert done
    assert gs["dealer_hand"] == ["9♦", "2♣"]
    assert gs["results_summary"] == {"win": 1, "lose": 0, "draw": 0}
    assert env.state.rewards == {0: 1.0}


def test_dealer_blackjack_beats_a_three_card_21():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["7♠", "7♥", "7♦"]
    gs["dealer_hand"] = ["Q♣", "A♦"]
    done, _ = env.step("stand")
    assert done
    assert gs["results_summary"] == {"win": 0, "lose": 1, "draw": 0}
    assert env.state.rewards == {0: 0.0}


def test_two_blackjacks_push():
    env = _fresh()
    gs = env.state.game_state
    gs["player_hand"] = ["A♠", "J♥"]
    gs["dealer_hand"] = ["10♣", "A♦"]
    done, _ = env.step("stand")
    assert done
    assert gs["results_summary"] == {"win": 0, "lose": 0, "draw": 1}
    assert env.state.rewards == {0: 0.5}


def test_prompt_states_hand_count_dealer_rule_and_scoring():
    env = _fresh(num_hands=7)
    prompt = env.state.events[0][1]
    assert "for 7 hands" in prompt
    assert "draws until reaching 17 or more" in prompt and "soft 17" in prompt
    assert "blackjack" in prompt
    assert "(wins + 0.5 x pushes) / 7" in prompt


def test_snapshot_restores_rng_for_same_hit_card():
    env = _fresh()
    env.state.game_state["player_hand"] = ["2♠", "2♥"]
    snapshot = env.snapshot()
    env.step("hit")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("hit")
    assert env.state.game_state == expected
