"""Offline deterministic tests for HighSociety (2-player version).

Ten prestige cards are auctioned. Each auction both players bid a money card
1-11; the higher bid wins the prestige card and discards that money card, the
loser keeps their card. Ties re-auction the same prestige card. Winner is the
higher final net-worth (remaining cash + prestige), as stated in the player prompt.
"""
import copy

from textarena.envs.HighSociety.env import HighSocietyEnv


def _fresh():
    env = HighSocietyEnv()
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["player_money"][0] == list(range(1, 12))
    assert gs["player_money"][1] == list(range(1, 12))
    assert gs["player_prestige"] == {0: 0, 1: 0}
    assert len(gs["prestige_deck"]) == 9   # one prize already popped for auction 1
    assert env.state.current_player_id == 0


def test_scripted_player0_wins_all_auctions():
    """P0 always outbids P1 (who always bids 1 and keeps it), winning every
    prestige card -> P0 prestige = 1+..+10 = 55, P1 = 0, regardless of order.

    Net-worth = cash + prestige: P0 = 55 + 1 = 56, P1 = 0 + 66 = 66, so P1
    wins despite taking no prestige cards."""
    env = _fresh()
    p0_bids = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2]  # distinct, all > 1, one per auction
    p0_idx = 0
    done = False
    for _ in range(40):
        pid = env.state.current_player_id
        if pid == 0:
            done, _ = env.step(str(p0_bids[p0_idx]))
            p0_idx += 1
        else:
            done, _ = env.step("1")
        if done:
            break
    assert done
    assert env.state.game_state["player_prestige"][0] == 55
    assert env.state.game_state["player_prestige"][1] == 0
    assert env.state.rewards == {0: -1, 1: 1}
    assert env.state.turn == 20
    assert env.state.game_state["round"] == 10


def test_invalid_format_does_not_end_game():
    env = _fresh()
    pid = env.state.current_player_id
    done, _ = env.step("no bid here")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == pid


def test_illegal_bid_of_spent_card():
    """After P0 wins auction 1 with 11, that card is gone; bidding it again is
    rejected."""
    env = _fresh()
    assert env.state.current_player_id == 0
    env.step("11")   # P0 bids 11 first
    env.step("1")    # P1 bids 1 -> P0 wins, discards 11
    assert 11 not in env.state.game_state["player_money"][0]
    # Auction 2: current player is P1 (bid second). Drive until it's P0's turn,
    # then have P0 try to bid the spent card.
    if env.state.current_player_id == 1:
        env.step("1")  # P1 opens auction 2
    assert env.state.current_player_id == 0
    done, _ = env.step("11")  # P0 no longer has 11
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


def test_networth_includes_cash():
    """Net-worth includes remaining money cards.

    Construct a terminal position where P0 has slightly more prestige but P1 has
    far more remaining cash; under cash + prestige scoring P1 wins.
    """
    env = _fresh()
    gs = env.state.game_state
    gs["player_prestige"] = {0: 5, 1: 4}
    gs["player_money"] = {0: [1], 1: list(range(1, 12))}  # P1 hoarded all cash
    outcome = env._end_match()
    # Intended outcome: P1 (4 + 66 = 70) beats P0 (5 + 1 = 6).
    assert outcome.rewards == {0: -1, 1: 1}


def test_tied_bids_stay_sealed_until_reveal_and_are_returned():
    env = _fresh()
    before_money = copy.deepcopy(env.game_state["player_money"])
    env.step("7")
    p1_pending = [message for _, message, _ in env.state.observations[1]]
    assert not any(message.strip() == "7" for message in p1_pending)
    done, _ = env.step("7")
    assert not done
    assert env.game_state["player_money"] == before_money
    assert env.game_state["pending_bids"] == {}
    assert env.game_state["round"] == 1
    assert env.state.current_player_id == 0


def test_mixed_or_duplicate_bid_text_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("7\n8")
    assert not done
    assert env.game_state == before
    assert env.state.current_player_id == 0


def test_seeded_reset_and_snapshot_restore_auction():
    first, second = _fresh(), _fresh()
    assert first.game_state["prestige_deck"] == second.game_state["prestige_deck"]
    assert first.game_state["current_prize"] == second.game_state["current_prize"]

    snapshot = first.snapshot()
    first.step("11")
    first.restore(snapshot)
    assert first.game_state["pending_bids"] == {}
    assert first.state.turn == 0
