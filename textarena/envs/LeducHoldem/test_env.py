"""Deterministic offline tests for Leduc Hold'em.

Two-player, 6-card deck (JJQQKK). With ``max_rounds=1`` the match resolves after
one hand. Cards/board are dealt randomly; we read them from ``game_state`` to
predict the showdown. The starting player for the first hand is player 1.
"""
import copy

from textarena.envs.LeducHoldem.env import LeducHoldemEnv


def _fresh(max_rounds=1):
    env = LeducHoldemEnv(max_rounds=max_rounds)
    env.reset(num_players=2, seed=42)
    return env


def _showdown_winner(gs):
    c0, c1, b = gs["player_cards"][0], gs["player_cards"][1], gs["board_card"]
    pair0, pair1 = (c0 == b), (c1 == b)
    if pair0 != pair1:
        return 0 if pair0 else 1
    if c0 != c1:
        return 0 if c0 > c1 else 1
    return None  # exact tie


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 1  # starting_player flipped to 1
    gs = env.state.game_state
    assert gs["pot"] == 2  # both antes
    assert set(gs["player_cards"].keys()) == {0, 1}


def test_check_down_showdown():
    env = _fresh()
    winner = _showdown_winner(env.state.game_state)
    assert winner is not None  # seed=42 yields a decisive hand
    env.step("check")  # P1
    env.step("check")  # P0 -> flop revealed
    env.step("check")  # P1
    done, _ = env.step("check")  # P0 -> showdown
    assert done is True
    loser = 1 - winner
    assert env.state.rewards == {winner: 1, loser: -1}


def test_bet_fold():
    env = _fresh()
    starter = env.state.current_player_id  # P1
    env.step("bet")           # starter bets pre-flop
    done, _ = env.step("fold")  # opponent folds
    assert done is True
    other = 1 - starter
    assert env.state.rewards == {starter: 1, other: -1}


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("thinking about it")
    assert done is False
    assert env.state.error_count == 1


def test_illegal_action_rejected():
    env = _fresh()
    # current_bet is 0, so only 'check'/'bet' are legal; 'call' is illegal.
    done, _ = env.step("call")
    assert done is False
    assert env.state.error_count == 1


def test_bet_call_advances_to_flop():
    env = _fresh()
    env.step("bet")            # P1 bets pre-flop
    done, _ = env.step("call")  # P0 calls -> flop round begins
    assert done is False
    assert env.state.game_state["round"] == 1
    assert env.state.game_state["pot"] == 6  # 2 ante + 2 + 2


def test_raises_charge_only_each_players_unmatched_amount():
    env = _fresh()
    gs = env.state.game_state
    env.step("bet")    # P1 commits 2
    env.step("raise")  # P0 commits 4 total
    assert gs["round_bets"] == {0: 4, 1: 2}
    assert gs["pot"] == 8
    done, _ = env.step("call")  # P1 owes only 2
    assert not done
    assert gs["round"] == 1
    assert gs["pot"] == 10
    assert gs["player_bank"] == {0: 95, 1: 95}
    assert gs["round_bets"] == {0: 0, 1: 0}


def test_each_round_allows_only_the_opening_bet_and_one_raise():
    env = _fresh()
    gs = env.state.game_state
    env.step("bet")
    env.step("raise")
    assert env._legal(gs, env.state.current_player_id) == ["call", "fold"]
    before = copy.deepcopy(gs)
    env.step("raise")
    assert env.state.error_count == 1 and gs == before
    env.step("call")  # pre-flop pot: 2 antes + 4 + 4
    env.step("check")
    env.step("bet")   # post-flop: bet 4, raise to 8
    env.step("raise")
    assert env._legal(gs, env.state.current_player_id) == ["call", "fold"]
    env.step("call")
    assert env.state.done
    assert gs["pot"] == 0 and sum(gs["player_bank"].values()) == 200
    assert max(gs["player_bank"].values()) - 100 in (0, 13)  # at most 1 + 4 + 8 changes hands


def test_showdown_reveals_both_private_cards_and_the_public_card():
    env = _fresh(max_rounds=2)
    gs = env.state.game_state
    gs["player_cards"] = {0: 2, 1: 0}
    gs["board_card"] = 1
    for _ in range(4):
        env.step("check")
    assert any(
        message.startswith("Showdown: Player 0 shows K, Player 1 shows J; the public card is Q. Player 0 wins the pot of 2.")
        and to_id == -1
        for _, message, _, to_id in env.state.events
    )


def test_board_shows_cards_pot_chips_and_valid_actions():
    env = _fresh(max_rounds=3)
    gs = env.state.game_state
    actor = env.state.current_player_id
    board = env.render(actor)
    own_card = env._rank_to_str(gs["player_cards"][actor])
    assert f"Your card: {own_card} | Public card: not revealed yet" in board
    assert "Pot: 2 | Your chips: 99 | Opponent chips: 99" in board
    assert "Valid actions: 'check', 'bet'" in board
    env.step("bet")
    board = env.render(1 - actor)
    assert "Pot: 4 | Your chips: 99 | Opponent chips: 97" in board
    assert "to call: 2" in board
    assert "Valid actions: 'call', 'raise', 'fold'" in board


def test_mdp_observation_lists_valid_actions_for_the_actor():
    import textarena as ta

    env = ta.make("LeducHoldem-v0-mdp")
    env.reset(num_players=2, seed=3)
    env.get_observation()
    env.step("bet")
    _, observation = env.get_observation()
    assert observation.rstrip().endswith("Valid actions: 'call', 'raise', 'fold'")


def test_short_stacks_cannot_go_negative():
    env = LeducHoldemEnv(starting_bank=3, max_rounds=1)
    env.reset(num_players=2, seed=42)
    env.step("bet")
    env.step("call")
    gs = env.state.game_state
    assert gs["round"] == 1
    assert gs["player_bank"] == {0: 0, 1: 0}
    assert env._legal(gs, env.state.current_player_id) == ["check"]
    env.step("check")
    done, _ = env.step("check")
    assert done
    assert min(gs["player_bank"].values()) >= 0
    assert gs["pot"] == 0
    assert sum(gs["player_bank"].values()) == 6


def test_new_hand_clears_previous_check_state():
    env = _fresh(max_rounds=2)
    for _ in range(4):
        done, _ = env.step("check")
    assert not done
    assert env.state.game_state["hands_dealt"] == 2
    assert env.state.game_state["round"] == 0
    env.step("check")
    assert env.state.game_state["round"] == 0
    assert env.state.game_state["prev_check"] is True


def test_pair_beats_higher_unpaired_private_card():
    env = _fresh()
    gs = env.state.game_state
    gs["player_cards"] = {0: 0, 1: 2}
    gs["board_card"] = 0
    for _ in range(3):
        env.step("check")
    done, _ = env.step("check")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_exact_tie_splits_pot_and_draws_match():
    env = _fresh()
    gs = env.state.game_state
    gs["player_cards"] = {0: 1, 1: 1}
    gs["board_card"] = 2
    for _ in range(3):
        env.step("check")
    done, _ = env.step("check")
    assert done
    assert gs["pot"] == 0
    assert gs["player_bank"] == {0: 100, 1: 100}
    assert env.state.rewards == {0: 0, 1: 0}


def test_illegal_action_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("call")
    assert env.state.game_state == before


def test_legal_actions_are_listed_in_a_fixed_order():
    # Observations must not depend on set iteration order, which varies with PYTHONHASHSEED.
    env = _fresh()
    env.step("call")  # P1 cannot call an unopened pot
    env.step("bet")
    env.step("check")  # P0 cannot check facing a bet
    messages = [message for _, message, _, _ in env.state.events]
    assert any("Illegal now. Allowed: 'check', 'bet'." in message for message in messages)
    assert any("Illegal now. Allowed: 'call', 'raise', 'fold'." in message for message in messages)
    assert any(message.endswith("Valid actions: 'call', 'raise', 'fold'") for message in messages)
    env.step("raise")  # the raise is the round's second and last bet
    assert env._legal(env.state.game_state, env.state.current_player_id) == ["call", "fold"]


def test_board_stays_hidden_until_first_betting_round_finishes():
    env = _fresh()
    assert env.state.game_state["board_revealed"] is False
    assert not any("Flop card revealed" in message for _, message, _, _ in env.state.events)
    env.step("check")
    env.step("check")
    assert env.state.game_state["board_revealed"] is True
    assert any("Flop card revealed" in message for _, message, _, _ in env.state.events)


def test_snapshot_restore_replays_same_betting_state():
    env = _fresh()
    snapshot = env.snapshot()
    env.step("bet")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("bet")
    assert env.state.game_state == expected
