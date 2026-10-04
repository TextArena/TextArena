"""Offline deterministic tests for IndianPoker.

Each player antes 1 chip (starting_chips=100 -> 99 after ante, pot=2). Each sees
only the opponent's card. With max_rounds=1 the match ends after a single hand.
The dealt cards are hidden from players but readable from game_state, so we can
predict showdown outcomes deterministically.
"""
import copy

from textarena.envs.IndianPoker.env import IndianPokerEnv


def _fresh(max_rounds=1, starting_chips=100):
    env = IndianPokerEnv(max_rounds=max_rounds, starting_chips=starting_chips)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["player_chips"] == {0: 99, 1: 99}  # anted 1 each
    assert gs["pot"] == 2
    assert gs["current_round"] == 1
    # starting_player flips from 0 to 1, so player 1 acts first.
    assert env.state.current_player_id == 1
    assert 0 in gs["player_cards"] and 1 in gs["player_cards"]


def test_check_check_showdown_matches_cards():
    env = _fresh()
    gs = env.state.game_state
    r0 = IndianPokerEnv._rank(gs["player_cards"][0])
    r1 = IndianPokerEnv._rank(gs["player_cards"][1])
    env.step("check")            # player 1 (starter)
    done, _ = env.step("check")  # player 0 -> showdown
    assert done
    if r0 > r1:
        assert env.state.rewards == {0: 1, 1: -1}
    elif r1 > r0:
        assert env.state.rewards == {0: -1, 1: 1}
    else:
        assert env.state.rewards == {0: 0, 1: 0}  # tie -> pot split -> equal banks -> draw


def test_bet_call_showdown_matches_cards():
    env = _fresh()
    gs = env.state.game_state
    r0 = IndianPokerEnv._rank(gs["player_cards"][0])
    r1 = IndianPokerEnv._rank(gs["player_cards"][1])
    env.step("bet 5")           # player 1 opens
    done, _ = env.step("call")  # player 0 calls -> showdown
    assert done
    if r0 > r1:
        assert env.state.rewards == {0: 1, 1: -1}
    elif r1 > r0:
        assert env.state.rewards == {0: -1, 1: 1}
    else:
        assert env.state.rewards == {0: 0, 1: 0}


def test_fold_gives_pot_to_opponent():
    env = _fresh()
    assert env.state.current_player_id == 1
    env.step("bet 2")          # player 1 bets
    done, _ = env.step("fold")  # player 0 folds -> player 1 wins the hand
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_invalid_format_does_not_end_game():
    env = _fresh()
    pid = env.state.current_player_id
    done, _ = env.step("do something")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == pid


def test_illegal_check_when_facing_bet():
    env = _fresh()
    env.step("bet 3")           # player 1 bets
    done, _ = env.step("check")  # player 0 cannot check facing a bet
    assert not done
    assert env.state.error_count == 1


def test_illegal_call_with_nothing_to_call():
    env = _fresh()
    done, _ = env.step("call")  # nothing to call at start
    assert not done
    assert env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    offender = env.state.current_player_id
    env.step("garbage")
    done, _ = env.step("more garbage")
    assert done
    assert env.state.rewards[offender] == -1
    assert env.state.rewards[1 - offender] == 1


def test_fold_without_a_bet_is_illegal_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step("fold")
    assert not done
    assert env.state.game_state == before


def test_raise_charges_only_call_plus_increment_and_conserves_chips():
    env = _fresh()
    gs = env.state.game_state
    env.step("bet 5")
    env.step("raise 3")
    assert gs["highest_bet"] == 8
    assert gs["current_bets"] == {0: 8, 1: 5}
    assert gs["player_chips"] == {0: 91, 1: 94}
    assert gs["pot"] == 15
    done, _ = env.step("call")
    assert done
    assert gs["pot"] == 0
    assert sum(gs["player_chips"].values()) == 200


def test_open_bet_cannot_exceed_opponents_effective_stack():
    env = _fresh()
    gs = env.state.game_state
    gs["player_chips"] = {0: 2, 1: 10}
    before = copy.deepcopy(gs)
    env.step("bet 3")
    assert gs == before


def test_equal_rank_showdown_splits_pot_exactly():
    env = _fresh()
    gs = env.state.game_state
    gs["player_cards"] = {0: 0, 1: 13}  # two physical deuces
    env.step("check")
    done, _ = env.step("check")
    assert done
    assert gs["player_chips"] == {0: 100, 1: 100}
    assert gs["pot"] == 0
    assert env.state.rewards == {0: 0, 1: 0}


def test_zero_stack_ends_match_before_another_ante():
    env = _fresh(max_rounds=3, starting_chips=2)
    cards = env.state.game_state["player_cards"]
    winner = 0 if env._rank(cards[0]) > env._rank(cards[1]) else 1
    if env._rank(cards[0]) == env._rank(cards[1]):
        env.state.game_state["player_cards"] = {0: 0, 1: 1}
        winner = 1
    env.step("bet 1")
    done, _ = env.step("call")
    assert done
    assert min(env.state.game_state["player_chips"].values()) == 0
    assert env.state.rewards[winner] == 1


def test_huge_numeric_action_is_invalid_without_mutation():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("bet " + "9" * 5000)
    assert env.state.game_state == before


def test_snapshot_restore_replays_identically():
    env = _fresh(max_rounds=2)
    snapshot = env.snapshot()
    env.step("check")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("check")
    assert env.state.game_state == expected


def test_new_round_resets_check_sequence_and_keeps_round_in_bounds():
    env = _fresh(max_rounds=2)
    env.step("check")
    done, _ = env.step("check")
    assert not done
    assert env.state.game_state["current_round"] == 2
    assert env.state.game_state["second_check"] is False

    done, _ = env.step("check")
    assert not done
    assert env.state.game_state["second_check"] is True
    done, _ = env.step("check")
    assert done
    assert env.state.game_state["current_round"] == 2
