"""Deterministic offline tests for Le Truc.

Two-player trick game to 12 match points on a 40-card deck ranked
3 2 A K Q J 7 6 5 4 (suits never matter). Cards are dealt randomly, so most
tests overwrite ``game_state['hands']`` to script tricks. Player 1 deals the
first hand, so Player 0 (the non-dealer, "mano") leads it; the deal then
alternates. A raise passes the turn to the opponent, who must 'accept', 'fold'
or re-'raise'; accepting hands the turn back to the player whose card play the
negotiation interrupted, and only the accepting player may make the next raise.
"""
import copy
import random

import pytest

import textarena as ta
from textarena.envs.LeTruc.env import LeTrucEnv


def _fresh(seed=42, **kwargs):
    env = LeTrucEnv(**kwargs)
    env.reset(num_players=2, seed=seed)
    return env


def _deal(env, hand0, hand1):
    env.state.game_state["hands"] = {0: list(hand0), 1: list(hand1)}


def _play(env, *actions):
    done = False
    for action in actions:
        done = env.step(action)
    return done


def _all_cards(gs):
    return sorted(gs["hands"][0] + gs["hands"][1] + gs["undealt_cards"] + gs["played_cards"])


# -- deck and ranks ------------------------------------------------------------
def test_deck_is_forty_cards_without_eights_nines_or_tens():
    env = LeTrucEnv()
    assert len(env.deck) == len(set(env.deck)) == 40
    assert {card[:-1] for card in env.deck} == set(LeTrucEnv.order)
    assert not any(card[:-1] in {"8", "9", "10"} for card in env.deck)


def test_rank_order_is_high_to_low_and_ignores_suits():
    env = LeTrucEnv()
    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]
    assert [env._rank_idx(rank + "♠") for rank in order] == list(range(10))
    assert env._rank_idx("K♣") == env._rank_idx("K♥")


def test_reset_deals_three_cards_each_and_the_non_dealer_leads():
    env = _fresh()
    gs = env.state.game_state
    assert (gs["hand_number"], gs["dealer"], env.state.current_player_id) == (1, 1, 0)
    assert gs["stake"] == 1 and gs["raiser"] is None
    assert len(gs["hands"][0]) == len(gs["hands"][1]) == 3
    assert _all_cards(gs) == sorted(env.deck)


# -- tricks and hands ----------------------------------------------------------
def test_higher_rank_wins_the_trick_regardless_of_suit():
    env = _fresh()
    _deal(env, ["4♠", "5♣", "6♣"], ["3♦", "5♦", "6♦"])
    _play(env, "play 4", "play 3")
    assert env.state.game_state["tricks"] == [1]
    assert env.state.current_player_id == 1  # the trick winner leads next


def test_equal_ranks_spoil_the_trick_and_the_same_player_leads_again():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["4♦", "5♦", "6♦"])
    _play(env, "play 4", "play 4")
    assert gs["tricks"] == [None]
    assert env.state.current_player_id == 0

    _play(env, "raise", "fold")  # end hand 1; Player 1 leads hand 2
    assert env.state.current_player_id == 1
    _deal(env, ["7♣", "5♣", "6♣"], ["7♦", "5♦", "6♦"])
    _play(env, "play 7", "play 7")
    assert gs["tricks"] == [None]
    assert env.state.current_player_id == 1


@pytest.mark.parametrize(
    "tricks, expected",
    [
        ([0, 0], 0),
        ([1, 1], 1),
        ([0, 1, 0], 0),
        ([1, 0, 1], 1),
        ([0, None], 0),               # first-trick winner takes a spoilt second trick
        ([None, 1], 1),               # a spoilt first trick is credited to the next winner
        ([None, None, 0], 0),
        ([0, 1, None], 0),            # 1-1 then spoilt: the first-trick winner
        ([1, 0, None], 1),
        ([None, None, None], None),   # all three spoilt: void
        ([0], None),
        ([None], None),
        ([None, None], None),
        ([0, 1], None),
    ],
)
def test_hand_winner_resolution(tricks, expected):
    assert LeTrucEnv._hand_winner(tricks) == expected


def test_first_trick_winner_takes_the_hand_when_the_next_trick_is_spoilt():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["3♣", "5♣", "6♣"], ["4♦", "5♦", "6♦"])
    _play(env, "play 3", "play 4")  # Player 0 wins and leads again
    _play(env, "play 5", "play 5")  # spoilt: the hand is decided after two tricks
    assert gs["match_points"] == {0: 1, 1: 0}
    assert gs["hand_number"] == 2 and gs["tricks"] == []


def test_spoilt_first_trick_is_decided_by_the_next_trick():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["4♦", "3♦", "6♦"])
    _play(env, "play 4", "play 4")  # spoilt; Player 0 leads again
    _play(env, "play 5", "play 3")  # the follower wins the deciding trick
    assert gs["match_points"] == {0: 0, 1: 1}


def test_split_first_two_tricks_are_decided_by_the_third():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["3♣", "4♣", "4♥"], ["4♦", "3♦", "5♦"])
    _play(env, "play 3", "play 4")  # Player 0 wins the first trick
    _play(env, "play 4", "play 3")  # Player 1 wins the second and leads
    _play(env, "play 5", "play 4")  # Player 1 wins the third
    assert gs["match_points"] == {0: 0, 1: 1}


def test_split_tricks_and_spoilt_third_go_to_the_first_trick_winner():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["3♣", "4♣", "6♣"], ["4♦", "3♦", "6♦"])
    _play(env, "play 3", "play 4")
    _play(env, "play 4", "play 3")
    _play(env, "play 6", "play 6")
    assert gs["match_points"] == {0: 1, 1: 0}


def test_three_spoilt_tricks_void_the_hand_and_pass_the_deal():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["4♦", "5♦", "6♦"])
    _play(env, "play 4", "play 4", "play 5", "play 5", "play 6", "play 6")
    assert gs["match_points"] == {0: 0, 1: 0}
    assert (gs["hand_number"], gs["dealer"], gs["stake"]) == (2, 0, 1)
    assert env.state.current_player_id == 1


def test_the_deal_alternates_and_the_non_dealer_leads_every_hand():
    env = _fresh()
    gs = env.state.game_state
    for hand_number, (dealer, leader) in enumerate([(1, 0), (0, 1), (1, 0), (0, 1)], start=1):
        assert (gs["hand_number"], gs["dealer"], env.state.current_player_id) == (hand_number, dealer, leader)
        _play(env, "raise", "fold")  # the leader raises and scores 1
    assert gs["match_points"] == {0: 2, 1: 2}


# -- raising -------------------------------------------------------------------
def test_stake_ladder_goes_one_two_then_plus_two_up_to_twelve():
    env = LeTrucEnv()
    assert [env._next_stake(stake) for stake in (1, 2, 4, 6, 8, 10, 12)] == [2, 4, 6, 8, 10, 12, 12]


def test_raise_proposes_the_next_stake_and_passes_the_turn():
    env = _fresh()
    gs = env.state.game_state
    env.step("raise")
    assert (gs["stake"], gs["pending_raise_value"], gs["raiser"], gs["raise_origin"]) == (1, 2, 0, 0)
    assert env.state.current_player_id == 1
    assert env._legal_actions(1) == ["accept", "fold", "raise"]


def test_accept_sets_the_stake_and_resumes_the_interrupted_card_play():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["3♦", "5♦", "6♦"])
    _play(env, "play 4", "raise")  # Player 1 raises instead of following
    assert env.state.current_player_id == 0
    env.step("accept")
    assert (gs["stake"], gs["raiser"], gs["pending_raise_value"]) == (2, None, None)
    assert env.state.current_player_id == 1  # Player 1 still has to follow the 4
    env.step("play 3")
    assert gs["tricks"] == [1]


def test_fold_concedes_the_stake_from_before_the_raise():
    env = _fresh()
    gs = env.state.game_state
    done = _play(env, "raise", "fold")
    assert not done
    assert gs["match_points"] == {0: 1, 1: 0}
    assert (gs["hand_number"], gs["stake"], gs["raiser"]) == (2, 1, None)


def test_reraise_accepts_the_standing_offer_and_a_fold_concedes_it():
    env = _fresh()
    gs = env.state.game_state
    _play(env, "raise", "raise")  # Player 1 accepts 2 and proposes 4
    assert (gs["stake"], gs["pending_raise_value"], gs["raiser"], gs["raise_origin"]) == (2, 4, 1, 0)
    assert env.state.current_player_id == 0
    env.step("fold")
    assert gs["match_points"] == {0: 0, 1: 2}


def test_accepting_a_reraise_returns_the_turn_to_the_interrupted_player():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["3♦", "5♦", "6♦"])
    _play(env, "play 4", "raise", "raise", "raise", "accept")  # 2, re-raise to 4, re-raise to 6
    assert gs["stake"] == 6 and gs["raiser"] is None
    assert env.state.current_player_id == 1


def test_stake_is_capped_at_twelve():
    env = _fresh()
    gs = env.state.game_state
    _play(env, "raise", "raise", "raise", "raise", "raise", "raise")  # 2, 4, 6, 8, 10, then 12 proposed
    env.step("accept")
    assert (gs["stake"], gs["raise_right"]) == (12, 0)
    assert env.state.current_player_id == 0
    assert "raise" not in env._legal_actions(0)
    done = env.step("raise")
    assert not done and env.state.error_count == 1
    assert (gs["stake"], gs["raiser"]) == (12, None)


def test_a_raise_to_twelve_cannot_be_reraised():
    env = _fresh()
    gs = env.state.game_state
    _play(env, "raise", "raise", "raise", "raise", "raise", "raise")
    assert (gs["stake"], gs["pending_raise_value"], gs["raiser"]) == (10, 12, 1)
    assert env._legal_actions(0) == ["accept", "fold"]
    done = env.step("raise")
    assert not done and env.state.error_count == 1
    assert (gs["stake"], gs["pending_raise_value"], gs["raiser"]) == (10, 12, 1)
    env.step("fold")
    assert gs["match_points"] == {0: 0, 1: 10}


def test_the_raiser_cannot_raise_again_after_the_raise_is_accepted():
    env = _fresh()
    _play(env, "raise", "accept")
    assert env.state.current_player_id == 0
    assert "raise" not in env._legal_actions(0)
    before = copy.deepcopy(env.state.game_state)
    done = env.step("raise")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before
    assert any("Only P1, who accepted the last raise, may raise next." in event[1] for event in env.state.events[-2:])


def test_only_the_player_who_accepted_may_raise_next():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["4♣", "5♣", "6♣"], ["3♦", "5♦", "7♦"])
    _play(env, "raise", "accept", "play 4")
    assert env.state.current_player_id == 1
    assert "raise" in env._legal_actions(1)
    _play(env, "raise", "accept")  # Player 1 raises to 4; Player 0 accepts and now holds the next raise
    assert (gs["stake"], gs["raise_right"]) == (4, 0)
    assert env.state.current_player_id == 1
    assert "raise" not in env._legal_actions(1)
    env.step("play 3")  # Player 1 wins the trick and leads
    assert env.state.current_player_id == 1
    assert "raise" not in env._legal_actions(1)
    env.step("play 5")
    assert "raise" in env._legal_actions(0)


def test_a_reraise_is_allowed_because_it_accepts_the_standing_raise():
    env = _fresh()
    gs = env.state.game_state
    _play(env, "raise", "raise", "accept")  # Player 0 accepts Player 1's re-raise to 4
    assert (gs["stake"], gs["raise_right"]) == (4, 0)
    assert env.state.current_player_id == 0
    assert "raise" in env._legal_actions(0)


def test_raise_right_resets_every_hand():
    env = _fresh()
    gs = env.state.game_state
    _deal(env, ["3♣", "3♦", "6♣"], ["4♦", "5♦", "6♦"])
    _play(env, "raise", "accept", "play 3", "play 4", "play 3", "play 5")
    assert gs["hand_number"] == 2 and gs["raise_right"] is None
    assert env.state.current_player_id == 1
    assert "raise" in env._legal_actions(1)


# -- invalid moves -------------------------------------------------------------
def test_pending_raise_blocks_card_play_atomically():
    env = _fresh()
    env.step("raise")
    before = copy.deepcopy(env.state.game_state)
    done = env.step(f"play {before['hands'][1][0][:-1]}")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["accept", "fold"])
def test_accept_or_fold_without_a_raise_is_rejected(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["raise 3", "accept K", "fold 2"])
def test_non_play_actions_reject_card_arguments(action):
    env = _fresh()
    if action != "raise 3":
        env.step("raise")
    before = copy.deepcopy(env.state.game_state)
    done = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


@pytest.mark.parametrize("action", ["play", "play 8", "play 10", "play Q", "nonsense", "[raise] [fold]"])
def test_unplayable_actions_are_rejected_atomically(action):
    env = _fresh()
    _deal(env, ["3♣", "5♣", "6♣"], ["4♦", "5♦", "6♦"])
    before = copy.deepcopy(env.state.game_state)
    done = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_actions_are_case_insensitive():
    env = _fresh()
    _deal(env, ["K♣", "5♣", "6♣"], ["3♦", "5♦", "6♦"])
    _play(env, "Play k", "PLAY 3")
    assert env.state.game_state["tricks"] == [1]
    assert env.state.error_count == 0


def test_two_consecutive_invalid_moves_forfeit_the_match():
    env = _fresh()
    env.step("nonsense")
    done = env.step("nonsense")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


# -- observations --------------------------------------------------------------
def test_render_shows_private_cards_negotiation_and_legal_actions():
    env = _fresh()
    _deal(env, ["K♣", "K♦", "6♣"], ["3♦", "5♦", "7♥"])
    board = env.render(0)
    assert "Your cards: K♣ K♦ 6♣" in board
    assert "Legal actions: 'play K', 'play 6', 'raise'" in board
    assert not any(card in board for card in ["3♦", "5♦", "7♥"])

    _play(env, "play K", "raise")
    board = env.render(0)
    assert "Current trick: P0 led K♣." in board
    assert "Pending raise: P1 raised to 2." in board
    assert "Legal actions: 'accept', 'fold', 'raise'" in board

    env.step("accept")
    board = env.render(1)
    assert "Next raise: only P0 may raise (they accepted the last raise)." in board
    assert "'raise'" not in board.split("Legal actions: ")[1]


def test_each_player_is_dealt_their_cards_privately():
    env = _fresh()
    gs = env.state.game_state
    deals = [(to_id, message) for _, message, _, to_id in env.state.events if message.startswith("### Hand 1")]
    assert [to_id for to_id, _ in deals] == [0, 1]
    for to_id, message in deals:
        assert f"Your cards: {' '.join(gs['hands'][to_id])}" in message


def test_prompt_teaches_bare_actions_and_the_rules():
    env = _fresh()
    prompt = env.prompt(0)
    for token in ("'play <rank>'", "'play K'", "'raise'", "'accept'", "'fold'", "3 2 A K Q J 7 6 5 4"):
        assert token in prompt
    assert "only the player who accepted it may make the next raise" in prompt
    assert "[" not in prompt
    assert "actions pass" not in prompt
    assert "If 40 actions pass" in _fresh(max_turns=40).prompt(1)


# -- match end -----------------------------------------------------------------
def test_winning_a_raised_hand_can_end_the_match_at_twelve():
    env = _fresh()
    gs = env.state.game_state
    gs["match_points"][0] = 10
    _deal(env, ["3♣", "3♦", "6♣"], ["4♦", "5♦", "6♦"])
    done = _play(env, "raise", "accept", "play 3", "play 4", "play 3", "play 5")
    assert done
    assert gs["match_points"] == {0: 12, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_fold_can_end_the_match_at_twelve():
    env = _fresh()
    gs = env.state.game_state
    gs["match_points"][0] = 11
    done = _play(env, "raise", "fold")
    assert done
    assert gs["match_points"][0] == 12
    assert env.state.rewards == {0: 1, 1: -1}


def test_scripted_complete_match_terminates_at_twelve():
    env = _fresh()
    gs = env.state.game_state
    steps = 0
    while not env.state.done and steps < 200:
        env.step(env._legal_actions(env.state.current_player_id)[0])
        steps += 1
    assert env.state.done
    assert max(gs["match_points"].values()) >= 12


def test_turn_limit_awards_the_match_point_leader():
    env = _fresh(max_turns=2)
    done = _play(env, "raise", "fold")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_turn_limit_with_level_match_points_is_a_draw():
    env = _fresh(max_turns=1)
    done = env.step("raise")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


@pytest.mark.parametrize("seed", range(20))
def test_random_legal_play_keeps_invariants_and_terminates(seed):
    env = _fresh(seed=seed)
    gs = env.state.game_state
    chooser = random.Random(seed)
    previous_points = dict(gs["match_points"])
    done = False
    for _ in range(2_000):
        assert _all_cards(gs) == sorted(env.deck)
        assert gs["stake"] in (1, 2, 4, 6, 8, 10, 12)
        assert all(gs["match_points"][pid] >= previous_points[pid] for pid in (0, 1))
        previous_points = dict(gs["match_points"])
        done = env.step(chooser.choice(env._legal_actions(env.state.current_player_id)))
        assert env.state.error_count == 0
        if done:
            break
    assert done
    winner = max((0, 1), key=lambda pid: gs["match_points"][pid])
    assert gs["match_points"][winner] >= 12
    assert env.state.rewards == {winner: 1, 1 - winner: -1}


# -- determinism and snapshots -------------------------------------------------
def test_repeat_reset_replays_the_same_deal():
    env = _fresh()
    first_hands = copy.deepcopy(env.state.game_state["hands"])
    env.step(f"play {first_hands[0][0][:-1]}")
    env.reset(num_players=2, seed=42)
    assert env.state.game_state["hands"] == first_hands


def test_snapshot_restore_mid_negotiation_replays_the_next_hand():
    env = _fresh()
    env.step("raise")
    before = env.snapshot()
    _play(env, "raise", "fold")
    expected = copy.deepcopy(env.state.game_state), env.state.current_player_id
    env.restore(before)
    _play(env, "raise", "fold")
    assert (env.state.game_state, env.state.current_player_id) == expected


def test_registered_default_and_mdp_variants_are_usable():
    for env_id in ("LeTruc-v1", "LeTruc-v1-mdp"):
        wrapped = ta.make(env_id)
        wrapped.reset(num_players=2, seed=42)
        player_id, observation = wrapped.get_observation()
        assert wrapped.env.__class__ is LeTrucEnv
        assert player_id == 0
        assert "Your cards:" in observation
        assert "Legal actions:" in observation
