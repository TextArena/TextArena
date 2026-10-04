"""Offline deterministic tests for GameOfPureStrategy (GOPS).

Both players hold cards A(1)..K(13), each usable once. Each of 13 rounds a prize
is revealed; both bid a card secretly and the higher bid wins the prize (+ any
carry pot from ties). Highest total after 13 rounds wins.

Cards are entered as bare faces; value->face uses A=1, J=11, Q=12, K=13 and
plain digits for 2..10.
"""
import copy
import time

import pytest

from textarena.envs.GameOfPureStrategy.env import GameOfPureStrategyEnv


def _fresh():
    env = GameOfPureStrategyEnv()
    env.reset(num_players=2, seed=42)
    return env


def _tok(value: int) -> str:
    return GameOfPureStrategyEnv._val_to_face(value)


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["round"] == 1
    assert sorted(gs["prize_deck"]) == list(range(1, 14))
    assert gs["player_hands"][0] == list(range(1, 14))
    assert gs["player_hands"][1] == list(range(1, 14))
    # Player 1 leads the first round (starting_player flips from 0 to 1).
    assert env.state.current_player_id == 1


def test_scripted_full_game_player0_wins():
    """Player 0 beats player 1 in rounds 1-12 and only loses round 13.

    Schedule (by that player's k-th play == round k):
      P0: 2,3,4,...,13,1   ->  in round r plays r+1 (r<13), and 1 in round 13
      P1: 1,2,3,...,13     ->  in round r plays r
    So P0 wins 12 prizes, P1 wins only the last -> P0 always wins the match
    regardless of the (hidden, random) prize ordering.
    """
    env = _fresh()
    p0_queue = list(range(2, 14)) + [1]   # [2,3,...,13,1]
    p1_queue = list(range(1, 14))         # [1,2,...,13]
    idx = {0: 0, 1: 0}
    done = False
    for _ in range(26):
        pid = env.state.current_player_id
        card = (p0_queue if pid == 0 else p1_queue)[idx[pid]]
        idx[pid] += 1
        done, _ = env.step(_tok(card))
        if done:
            break
    assert done
    scores = env.state.game_state["player_scores"]
    assert scores[0] > scores[1]
    assert scores[0] + scores[1] == sum(range(1, 14))  # 91, no carry left over
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["round"] == 13


def test_invalid_format_does_not_end_game():
    env = _fresh()
    pid = env.state.current_player_id
    done, _ = env.step("I do not name a card")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == pid  # turn did not rotate


def test_two_tokens_is_invalid():
    env = _fresh()
    done, _ = env.step("A and also K")  # more than one card
    assert not done
    assert env.state.error_count == 1


def test_illegal_replay_of_spent_card():
    """Replaying a card already used earlier is rejected as illegal."""
    env = _fresh()
    # Round 1: leader plays A(1), opponent plays K(13). Round resolves.
    first = env.state.current_player_id
    env.step(_tok(1))                # leader bids A
    env.step(_tok(13))              # opponent bids K -> round 1 resolves
    # Now round 2. Whoever is on turn, make them replay a card they already spent.
    pid = env.state.current_player_id
    spent = 1 if pid == first else 13
    assert spent not in env.state.game_state["player_hands"][pid]
    done, _ = env.step(_tok(spent))
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


def test_tied_bid_carries_prize_without_losing_value():
    env = _fresh()
    first_prize = env.state.game_state["current_prize"]
    env.step("A")
    env.step("A")
    gs = env.state.game_state
    assert gs["round"] == 2
    assert gs["carry_pot"] == first_prize
    assert gs["player_scores"] == {0: 0, 1: 0}
    assert (
        sum(gs["player_scores"].values())
        + gs["carry_pot"]
        + sum(gs["prize_deck"][gs["round"] - 1:])
        == 91
    )


def test_final_tied_prize_remains_unclaimed_and_match_draws():
    env = _fresh()
    done = False
    for card in range(1, 14):
        env.step(_tok(card))
        done, _ = env.step(_tok(card))
    assert done
    gs = env.state.game_state
    assert gs["player_scores"] == {0: 0, 1: 0}
    assert gs["carry_pot"] == 91
    assert env.state.rewards == {0: 0, 1: 0}


def test_first_bid_raw_action_is_visible_only_to_its_author():
    env = _fresh()
    bidder = env.state.current_player_id
    env.step("K")
    matching_events = [
        event for event in env.state.events
        if event[0] == bidder and event[1] == "K"
    ]
    assert matching_events
    assert all(to_id == bidder for _, _, _, to_id in matching_events)
    assert "opponent" not in env.render(1 - bidder).lower()


def test_malformed_bid_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    env.step("A K")
    assert env.state.game_state == before


def test_snapshot_with_pending_secret_bid_restores_exactly():
    env = _fresh()
    env.step("Q")
    snapshot = env.snapshot()
    env.step("J")
    expected = copy.deepcopy(env.state.game_state)
    env.restore(snapshot)
    env.step("J")
    assert env.state.game_state == expected


PADDING = 30_000


@pytest.mark.parametrize(
    "action",
    [
        pytest.param(" " * PADDING + "x" + " " * 1000, id="leading-trailing-spaces"),
        pytest.param("4" + " " * PADDING + "x", id="inner-spaces"),
        pytest.param("\t\n " * (PADDING // 3) + "x", id="tab-newline-runs"),
        pytest.param("[" * (PADDING // 2) + "x" + "]" * (PADDING // 2 - 2), id="deep-brackets"),
    ],
)
def test_long_padded_input_is_rejected_quickly_without_changing_state(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    player = env.state.current_player_id
    start = time.perf_counter()
    env.step(action)
    assert time.perf_counter() - start < 0.25
    assert env.state.error_count == 1
    assert env.state.current_player_id == player
    assert env.state.game_state == before
