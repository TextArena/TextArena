"""Deterministic offline tests for the Poker (Texas Hold'em) environment."""
import copy

import pytest
import textarena as ta

from textarena.envs.Poker.env import PokerEnv
from textarena.envs.Poker.renderer import create_board_str


def _fresh(num_rounds=1, num_players=2):
    env = PokerEnv(num_rounds=num_rounds)
    env.reset(num_players=num_players, seed=42)
    return env


def _card(rank, suit):
    return {"rank": rank, "suit": suit}


def _configure_showdown(env, hands, board, contributions, folded=(), eliminated=(), button=0):
    gs = env.state.game_state
    for pid in range(env.state.num_players):
        gs["player_hands"][pid] = list(hands.get(pid, []))
        gs["player_chips"][pid] = 0
    gs["hand_players"] = list(hands)
    gs["community_cards"] = list(board)
    gs["visible_community_cards"] = list(board)
    gs["hand_contributions"] = {
        pid: contributions.get(pid, 0) for pid in range(env.state.num_players)
    }
    gs["pot"] = sum(gs["hand_contributions"].values())
    gs["folded_players"] = set(folded)
    gs["button"] = button
    for pid in eliminated:
        env.eliminate(pid)


def test_reset_posts_blinds():
    env = _fresh()
    chips = env.state.game_state["player_chips"]
    # Heads-up: button/SB=0 posts 10, BB=1 posts 20.
    assert chips == {0: 990, 1: 980}
    assert env.state.game_state["pot"] == 30
    assert env.state.current_player_id == 0


def test_fold_ends_single_round_game():
    env = _fresh(num_rounds=1)
    done = env.step("fold")  # P0 folds; only P1 remains
    assert done
    assert env.state.rewards == {0: -1.0, 1: 1.0}


def test_call_playthrough_reaches_terminal_rewards():
    env = _fresh(num_rounds=1)
    done = False
    for _ in range(50):
        done = env.step("call")  # calling with nothing due behaves like check
        if done:
            break
    assert done
    assert sorted(env.state.rewards.values()) == [-1.0, 1.0]


def test_invalid_action_increments_error():
    env = _fresh()
    done = env.step("jump")
    assert not done
    assert env.state.error_count == 1


def test_eliminated_players_are_excluded_from_every_hand_role():
    env = _fresh(num_rounds=3, num_players=4)
    gs = env.state.game_state
    gs["player_chips"][2] = 0
    gs["button"] = 1

    env._reset_round()

    assert 2 in env.state.eliminated
    assert 2 not in gs["hand_players"]
    assert gs["player_hands"][2] == []
    assert 2 not in {gs["small_blind_player"], gs["big_blind_player"]}

    before = copy.deepcopy(gs)
    result = env.apply(2, "call")
    assert isinstance(result, ta.Invalid)
    assert gs == before

    hands = {
        0: [_card("A", "♠"), _card("A", "♥")],
        1: [_card("K", "♠"), _card("K", "♥")],
        2: [],
    }
    board = [
        _card("2", "♠"),
        _card("4", "♥"),
        _card("7", "♦"),
        _card("9", "♣"),
        _card("J", "♠"),
    ]
    _configure_showdown(
        env,
        hands,
        board,
        contributions={0: 10, 1: 10, 2: 10},
        eliminated={2},
    )
    env._handle_showdown()
    assert gs["player_chips"][0] == 30
    assert gs["player_chips"][2] == 0


def test_side_pots_use_total_hand_contributions_and_folded_dead_money():
    env = _fresh(num_players=4)
    hands = {
        0: [_card("9", "♥"), _card("9", "♣")],
        1: [_card("J", "♥"), _card("J", "♦")],
        2: [_card("K", "♥"), _card("K", "♦")],
        3: [_card("A", "♥"), _card("A", "♦")],
    }
    board = [
        _card("2", "♠"),
        _card("7", "♥"),
        _card("9", "♦"),
        _card("J", "♣"),
        _card("K", "♠"),
    ]
    _configure_showdown(
        env,
        hands,
        board,
        contributions={0: 100, 1: 60, 2: 30, 3: 100},
        folded={3},
    )

    env._handle_showdown()

    assert env.state.game_state["player_chips"] == {0: 80, 1: 90, 2: 120, 3: 0}
    assert env.state.game_state["pot"] == 0


def _showdown_messages(env):
    env._handle_showdown()
    return [message for _, message, _, _ in env.state.events]


def test_only_all_ins_start_side_pots_and_uncalled_chips_are_returned():
    env = _fresh(num_players=3)
    hands = {
        0: [_card("6", "♦"), _card("6", "♥")],
        1: [_card("5", "♣"), _card("9", "♦")],
        2: [_card("Q", "♣"), _card("J", "♥")],
    }
    board = [_card("J", "♠"), _card("K", "♥"), _card("2", "♠"), _card("Q", "♥"), _card("A", "♣")]
    _configure_showdown(env, hands, board, contributions={0: 160, 1: 60, 2: 160}, folded={1})
    messages = _showdown_messages(env)
    assert "Player 2 wins the pot of 380 chips." in messages
    assert not any("side pot" in message for message in messages)

    env = _fresh(num_players=3)
    hands = {
        0: [_card("8", "♦"), _card("7", "♠")],
        1: [_card("A", "♥"), _card("A", "♦")],
        2: [_card("2", "♦"), _card("5", "♣")],
    }
    board = [_card("J", "♣"), _card("6", "♦"), _card("7", "♣"), _card("8", "♣"), _card("K", "♥")]
    _configure_showdown(env, hands, board, contributions={0: 780, 1: 940, 2: 980})
    messages = _showdown_messages(env)
    assert env.state.game_state["player_chips"] == {0: 2340, 1: 320, 2: 40}
    assert "Player 2's uncalled 40 chips are returned." in messages
    assert "Player 0 wins the main pot of 2340 chips." in messages
    assert "Player 1 wins side pot 1 of 320 chips." in messages


def test_uncalled_chips_are_returned_when_a_folded_player_contributed_less():
    env = _fresh(num_players=4)
    hands = {
        0: [_card("4", "♦"), _card("K", "♦")],
        2: [_card("9", "♣"), _card("9", "♥")],
        3: [_card("6", "♣"), _card("2", "♠")],
    }
    board = [_card("4", "♥"), _card("7", "♠"), _card("6", "♥"), _card("8", "♣"), _card("7", "♦")]
    _configure_showdown(env, hands, board, contributions={0: 60, 2: 21, 3: 4}, folded={2})
    messages = _showdown_messages(env)
    assert env.state.game_state["player_chips"] == {0: 73, 1: 0, 2: 0, 3: 12}
    assert "Player 0's uncalled 39 chips are returned." in messages
    assert "Player 3 wins the main pot of 12 chips." in messages
    assert "Player 0 wins side pot 1 of 34 chips." in messages


def test_tied_pot_odd_chip_goes_left_of_button_deterministically():
    env = _fresh(num_players=3)
    hands = {
        0: [_card("A", "♠"), _card("2", "♥")],
        1: [_card("7", "♠"), _card("6", "♥")],
        2: [_card("A", "♦"), _card("3", "♣")],
    }
    board = [
        _card("K", "♠"),
        _card("Q", "♥"),
        _card("J", "♦"),
        _card("9", "♣"),
        _card("8", "♠"),
    ]
    _configure_showdown(
        env,
        hands,
        board,
        contributions={0: 5, 1: 5, 2: 5},
        button=0,
    )

    env._handle_showdown()

    assert env.state.game_state["player_chips"] == {0: 7, 1: 0, 2: 8}


def test_preflop_big_blind_gets_option_and_raises_reopen_action():
    env = _fresh(num_players=3)
    gs = env.state.game_state

    env.step("call")  # P0 calls the big blind.
    assert env.state.current_player_id == 1
    env.step("raise 20")  # P1 makes the minimum raise to 40.
    assert env.state.current_player_id == 2
    env.step("call")
    assert env.state.current_player_id == 0
    assert gs["betting_round"] == 0

    env.step("call")

    assert gs["betting_round"] == 1
    assert env.state.current_player_id == 1
    assert gs["acted_players"] == set()


def test_street_and_hand_transitions_do_not_double_rotate():
    env = _fresh(num_rounds=2)
    gs = env.state.game_state

    env.step("call")
    assert env.state.current_player_id == 1  # BB still gets its pre-flop option.
    env.step("call")
    assert gs["betting_round"] == 1
    assert env.state.current_player_id == 1  # First post-flop seat left of button.
    env.step("check")
    assert env.state.current_player_id == 0
    env.step("check")
    assert gs["betting_round"] == 2
    assert env.state.current_player_id == 1

    fresh_hand = _fresh(num_rounds=2)
    fresh_hand.step("fold")
    assert fresh_hand.state.game_state["round"] == 2
    assert fresh_hand.state.game_state["button"] == 1
    assert fresh_hand.state.current_player_id == 1


def test_equal_terminal_stacks_receive_equal_dense_rewards():
    env = _fresh(num_players=4)
    env.state.game_state["player_chips"] = {0: 10, 1: 20, 2: 20, 3: 30}
    outcome = env._final_outcome()
    assert outcome.rewards == {0: -1.0, 1: 0.0, 2: 0.0, 3: 1.0}

    env.state.game_state["player_chips"] = {pid: 25 for pid in range(4)}
    outcome = env._final_outcome()
    assert outcome.rewards == {pid: 0.0 for pid in range(4)}


def test_tied_terminal_places_are_averaged_and_rewards_remain_zero_sum():
    env = _fresh(num_players=4)
    env.state.game_state["player_chips"] = {0: 10, 1: 10, 2: 20, 3: 30}

    outcome = env._final_outcome()

    assert outcome.rewards == {
        0: pytest.approx(-2 / 3),
        1: pytest.approx(-2 / 3),
        2: pytest.approx(1 / 3),
        3: 1.0,
    }
    assert sum(outcome.rewards.values()) == pytest.approx(0.0)


def test_players_busting_in_later_hands_rank_higher():
    env = PokerEnv(num_rounds=3, starting_chips=100)
    env.reset(num_players=4, seed=42)
    gs = env.state.game_state
    gs["player_chips"] = {0: 150, 1: 0, 2: 150, 3: 100}
    env._eliminate_busted_players()  # P1 busts in hand 1
    gs["round"] = 2
    gs["player_chips"].update({0: 250, 3: 0})
    env._eliminate_busted_players()  # P3 busts in hand 2

    outcome = env._final_outcome()

    assert outcome.rewards == {0: 1.0, 1: -1.0, 2: pytest.approx(1 / 3), 3: pytest.approx(-1 / 3)}
    assert outcome.reason == (
        "Player 0 wins with the most chips. Final ranking: 1. Player 0 (250 chips); 2. Player 2 (150 chips); "
        "3. Player 3 (out in hand 2); 4. Player 1 (out in hand 1)."
    )


@pytest.mark.parametrize(
    "starting, rewards, ranking",
    [
        ({1: 50, 2: 80}, {1: -1.0, 2: pytest.approx(-1 / 3)}, "3. Player 2 (out in hand 1); 4. Player 1 (out in hand 1)."),
        ({1: 65, 2: 65}, {1: pytest.approx(-2 / 3), 2: pytest.approx(-2 / 3)}, "3. Player 1 (out in hand 1); 3. Player 2 (out in hand 1)."),
    ],
)
def test_players_busting_in_the_same_hand_rank_by_starting_stack(starting, rewards, ranking):
    env = PokerEnv(num_rounds=1, starting_chips=100)
    env.reset(num_players=4, seed=42)
    gs = env.state.game_state
    hands = {
        0: [_card("A", "♠"), _card("A", "♥")],
        1: [_card("K", "♠"), _card("K", "♥")],
        2: [_card("Q", "♠"), _card("Q", "♥")],
    }
    board = [_card("2", "♣"), _card("5", "♦"), _card("7", "♣"), _card("9", "♦"), _card("J", "♠")]
    _configure_showdown(env, hands, board, contributions={0: 100, **starting})
    gs["player_chips"][3] = 400 - 100 - sum(starting.values())
    gs["hand_start_chips"] = {0: 100, 3: gs["player_chips"][3], **starting}

    env._handle_showdown()
    outcome = env._final_outcome()

    assert {pid: outcome.rewards[pid] for pid in (1, 2)} == rewards
    assert outcome.rewards[0] == 1.0 and outcome.rewards[3] == pytest.approx(1 / 3)
    assert outcome.reason.endswith(ranking)


def test_invalid_move_elimination_busts_before_the_hands_showdown():
    env = PokerEnv(num_rounds=1, starting_chips=100)
    env.reset(num_players=3, seed=1)
    gs = env.state.game_state
    env.step("raise 1000")  # P0 (button) is all-in for 100
    env.step("garbage")
    env.step("garbage")  # P1 (small blind) is eliminated, forfeiting its stack
    done = env.step("call")  # P2 (big blind) calls all-in; P0 and P2 show down
    assert done
    loser = 0 if gs["player_chips"][0] == 0 else 2
    winner = 2 - loser
    assert gs["player_chips"][winner] == 300
    assert env.state.rewards == {winner: 1.0, loser: 0.0, 1: -1.0}
    assert env.state.game_info[0]["reason"] == (
        f"Player {winner} wins with the most chips. Final ranking: 1. Player {winner} (300 chips); "
        f"2. Player {loser} (out in hand 1); 3. Player 1 (eliminated for invalid moves in hand 1)."
    )


def test_invalid_move_elimination_ranks_above_earlier_busts():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    gs["player_chips"] = {0: 300, 1: 0, 2: 0}
    gs["busted"] = {1: (2, 0, 1), 2: (1, 1, 1000)}
    assert env._final_outcome().rewards == {0: 1.0, 1: 0.0, 2: -1.0}


def test_heads_up_bust_ends_the_game_with_full_rewards():
    env = PokerEnv(num_rounds=5, starting_chips=100)
    env.reset(num_players=2, seed=1)
    gs = env.state.game_state
    env.step("raise 1000")
    done = env.step("call")
    assert done
    winner = 0 if gs["player_chips"][0] == 200 else 1
    assert env.state.rewards == {winner: 1.0, 1 - winner: -1.0}
    assert env.state.game_info[0]["reason"] == (
        f"Player {winner} wins with the most chips. Final ranking: 1. Player {winner} (200 chips); "
        f"2. Player {1 - winner} (out in hand 1)."
    )


@pytest.mark.parametrize("action", ["check", "bet 10", "raise 0"])
def test_invalid_actions_do_not_mutate_poker_gameplay_state(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    current_player = env.state.current_player_id

    done = env.step(action)

    assert not done
    assert env.state.game_state == before
    assert env.state.game_state["round_turn"] == 0
    assert env.state.current_player_id == current_player


def test_bet_cannot_be_used_to_call_an_existing_bet():
    env = _fresh()
    gs = env.state.game_state

    done = env.step("bet 10")

    assert not done
    assert env.state.error_count == 1
    assert gs["pot"] == 30
    assert gs["player_bets"] == {0: 10, 1: 20}


def test_three_pair_uses_third_pair_as_kicker():
    env = PokerEnv()
    cards = [
        _card("A", "♠"),
        _card("A", "♥"),
        _card("K", "♠"),
        _card("K", "♥"),
        _card("Q", "♠"),
        _card("Q", "♥"),
        _card("2", "♣"),
    ]
    assert env._evaluate_hand(cards) == (3, [14, 13, 12])


@pytest.mark.parametrize(
    "ranks, high",
    [
        ([2, 3, 4, 5, 6, 7], 7),           # the highest window, not the first one found
        ([2, 3, 4, 5, 6, 14], 6),          # a natural six-high straight beats the wheel
        ([2, 3, 4, 5, 9, 14], 5),          # the wheel is only a fallback
        ([9, 10, 11, 12, 13, 14], 14),
    ],
)
def test_check_straight_returns_the_highest_straight(ranks, high):
    assert PokerEnv()._check_straight(ranks) == (True, high)


def test_six_high_straight_with_an_ace_splits_with_another_six_high_straight():
    env = _fresh()
    hands = {0: [_card("6", "♥"), _card("A", "♣")], 1: [_card("6", "♦"), _card("9", "♦")]}
    board = [_card("2", "♠"), _card("3", "♦"), _card("4", "♣"), _card("5", "♥"), _card("K", "♠")]
    _configure_showdown(env, hands, board, contributions={0: 50, 1: 50})
    env._handle_showdown()
    assert env.state.game_state["player_chips"] == {0: 50, 1: 50}


def test_zero_due_call_emits_game_action_description():
    env = _fresh()
    env.step("call")
    env.step("call")

    assert any(
        message == "Player 1 calls with nothing due (checks)."
        and observation_type is ta.ObservationType.GAME_ACTION_DESCRIPTION
        for _, message, observation_type, _ in env.state.events
    )


def test_renderer_hides_opponent_hole_cards_unless_reveal_all():
    kwargs = {
        "community_cards": [],
        "pot": 30,
        "player_chips": {0: 90, 1: 80},
        "player_hands": {
            0: [_card("A", "♠"), _card("K", "♥")],
            1: [_card("Q", "♦"), _card("J", "♣")],
        },
        "bets": {0: 10, 1: 20},
    }

    safe_board = create_board_str(**kwargs, viewer_id=0)
    assert "│ Q       │" not in safe_board
    assert "│    ♦    │" not in safe_board

    revealed_board = create_board_str(**kwargs, viewer_id=0, reveal_all=True)
    assert "│ Q       │" in revealed_board
    assert "│    ♦    │" in revealed_board


def test_heads_up_board_labels_button_as_small_blind():
    env = _fresh()
    board_messages = [
        message
        for _, message, observation_type, to_id in env.state.events
        if observation_type is ta.ObservationType.GAME_BOARD and to_id == 0
    ]
    assert any("P0 (Dealer/SB)" in message for message in board_messages)
    assert any("P1 (BB)" in message for message in board_messages)


def test_board_lists_amount_to_call_and_legal_raise_range():
    env = _fresh()
    board = env.render(0)
    assert "To call: 10 | Your options: 'fold', 'call' (10 chips), 'raise N' (N from 20 to 980; 980 is all-in)" in board
    env.step("call")
    assert "To call: 0 | Your options: 'check', 'raise N' (N from 20 to 980; 980 is all-in)" in env.render(1)


def test_board_offers_no_raise_after_a_short_all_in_that_does_not_reopen_action():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    env.step("call")
    env.step("call")
    gs["player_chips"][2] = 5
    env.step("raise 20")  # P2 is all-in for 25 total, a short raise
    board = env.render(0)
    assert "To call: 5 | Your options: 'fold', 'call' (5 chips)" in board
    assert "raise" not in board.split("Your options:")[1]


def test_each_decision_gets_exactly_one_board():
    env = _fresh(num_rounds=2)
    start = len(env.state.events)
    env.step("fold")  # ends hand 1 and deals hand 2
    boards = [
        to_id for _, _, observation_type, to_id in env.state.events[start:]
        if observation_type is ta.ObservationType.GAME_BOARD
    ]
    assert boards == [env.state.current_player_id]


def _last_rejection(env):
    return next(
        message for _, message, _, _ in reversed(env.state.events) if "attempted an invalid move" in message
    )


def test_unrecognized_action_lists_the_current_options():
    env = _fresh()
    env.step("jump")
    assert (
        "Invalid poker action. Reply with one of: 'fold', 'call' (10 chips), "
        "'raise N' (N from 20 to 980; 980 is all-in)." in _last_rejection(env)
    )


@pytest.mark.parametrize(
    "chips, action, expected",
    [
        (990, "raise 1", "A raise must add at least 20 chips (a total bet of at least 40): reply 'raise 20' or more."),
        (
            25,
            "raise 10",
            "A raise must add at least 20 chips (a total bet of at least 40), and only an all-in may be smaller; "
            "your stack allows only 'raise 15' (all-in).",
        ),
        (5, "raise 20", "You cannot raise: your stack only covers a call. Reply with one of: 'fold', 'call' (5 chips, all-in)."),
    ],
)
def test_raise_rejections_use_increment_semantics(chips, action, expected):
    env = _fresh()
    env.state.game_state["player_chips"][0] = chips
    env.step(action)
    assert env.state.error_count == 1
    assert expected in _last_rejection(env)


@pytest.mark.parametrize(
    "chips, expected",
    [
        (980, "A bet must be at least 20 chips: reply 'bet 20' or more."),
        (15, "A bet must be at least 20 chips, and only an all-in may be smaller; your stack allows only 'bet 15' (all-in)."),
    ],
)
def test_short_bet_rejection_names_the_minimum_or_the_all_in(chips, expected):
    env = _fresh()
    env.step("call")
    env.step("check")
    env.state.game_state["player_chips"][1] = chips
    env.step("bet 10")
    assert env.state.error_count == 1
    assert expected in _last_rejection(env)


def test_under_minimum_raise_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    env.step("raise 1")

    assert env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["raise 20", "bet 10"])
def test_postflop_requires_a_full_opening_bet(action):
    env = _fresh()
    env.step("call")
    env.step("call")
    assert env.state.game_state["betting_round"] == 1
    before = copy.deepcopy(env.state.game_state)

    env.step(action)

    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_short_all_in_raise_runs_out_without_extra_solo_betting():
    env = PokerEnv(
        num_rounds=1,
        starting_chips=21,
        small_blind=10,
        big_blind=20,
    )
    env.reset(num_players=2, seed=42)
    gs = env.state.game_state

    done = env.step("raise 20")
    assert not done
    assert gs["current_bet"] == 21
    assert gs["player_chips"][0] == 0
    assert 0 in gs["all_in_players"]

    done = env.step("call")
    assert done
    assert gs["pot"] == 0
    assert sum(gs["player_chips"].values()) == 42
    assert len(gs["visible_community_cards"]) == 5


def test_short_all_in_raise_does_not_reopen_prior_action():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    env.step("call")  # P0 acts.
    env.step("call")  # P1 acts.
    assert env.state.current_player_id == 2
    gs["player_chips"][2] = 5

    env.step("raise 20")  # P2 can only raise from 20 to 25 all-in.
    assert env.state.current_player_id == 0
    assert gs["current_bet"] == 25
    before = copy.deepcopy(gs)

    env.step("raise 20")

    assert env.state.error_count == 1
    assert gs == before


def test_cumulative_short_all_in_raises_reopen_prior_action():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    env.step("call")  # P0 acts at 20.

    gs["player_chips"][1] = 15
    env.step("raise 15")  # P1 can only raise from 20 to 25 all-in.
    gs["player_chips"][2] = 20
    env.step("raise 15")  # P2 can only raise from 25 to 40 all-in.

    assert env.state.current_player_id == 0
    assert gs["current_bet"] == 40
    done = env.step("raise 20")

    assert done  # both opponents are all-in, so the accepted raise runs out
    assert env.state.error_count == 0
    assert gs["current_bet"] == 60
    assert any(
        message == "Player 0 raises to 60."
        for _, message, _, _ in env.state.events
    )


def test_short_big_blind_does_not_lower_preflop_bring_in():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    gs["player_chips"] = {0: 100, 1: 100, 2: 5}

    env._reset_round()

    assert gs["big_blind_player"] == 2
    assert gs["player_bets"][2] == 5
    assert gs["current_bet"] == env.big_blind
    assert env.state.current_player_id == 0
    env.set_current_player(0)
    env.step("call")
    assert gs["player_bets"][0] == env.big_blind


@pytest.mark.parametrize("num_players", [2, 3])
def test_small_blind_covering_a_short_all_in_big_blind_does_not_act(num_players):
    env = PokerEnv(num_rounds=2, starting_chips=100)
    env.reset(num_players=num_players, seed=3)
    gs = env.state.game_state
    gs["player_chips"] = {pid: 100 for pid in range(num_players)}
    gs["player_chips"][num_players - 1] = 5
    total = sum(gs["player_chips"].values())
    env._reset_round()
    assert gs["small_blind_player"] == num_players - 2
    assert gs["big_blind_player"] == num_players - 1
    if num_players == 3:
        env.set_current_player(env._cur)
        env.step("fold")  # the button folds; the small blind already covers the all-in big blind
    else:
        assert env._is_hand_over()
        env._handle_hand_completion()
    assert sum(gs["player_chips"].values()) + gs["pot"] == total
    messages = [message for _, message, _, _ in env.state.events]
    assert f"Player {num_players - 2}'s uncalled 5 chips are returned." in messages
    assert any(message.startswith("Showdown round 1:") for message in messages)


def test_fold_does_not_reveal_unreached_community_cards():
    env = _fresh(num_rounds=1)
    gs = env.state.game_state
    assert gs["visible_community_cards"] == []

    done = env.step("fold")

    assert done
    assert gs["visible_community_cards"] == []
    assert not any(
        "Community cards:" in message
        for _, message, _, _ in env.state.events
    )


def test_invalid_move_elimination_forfeits_stack_without_losing_chips():
    env = _fresh(num_players=3)
    gs = env.state.game_state
    initial_total = sum(gs["player_chips"].values()) + gs["pot"]

    env.step("garbage")
    done = env.step("still garbage")

    assert not done
    assert 0 in env.state.eliminated
    assert gs["player_chips"][0] == 0
    assert sum(gs["player_chips"].values()) + gs["pot"] == initial_total
    assert sum(gs["hand_contributions"].values()) == gs["pot"]


def test_huge_numeric_poker_action_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)

    env.step("raise " + "9" * 5000)

    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_small_blind_above_big_blind_is_rejected():
    with pytest.raises(ValueError, match="small_blind cannot exceed big_blind"):
        PokerEnv(small_blind=20, big_blind=10)
