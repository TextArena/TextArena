"""Deterministic offline tests for Letter Auction.

Two-player game: 26 letters are auctioned one at a time, then each player forms
the highest-value English word from letters won. Player 0 bids first.

NOTE: importing this env triggers ``nltk.download("words")`` (cached locally),
required to validate submitted words. Tests avoid needing the network at runtime.
Full "form a real word and win" outcomes depend on which letters are won, so we
verify auction mechanics, invalid handling, and a scripted terminal reached by
passing every letter then submitting invalid words.
"""
import copy

import pytest

import textarena.envs.LetterAuction.env as letter_auction_module
from textarena.envs.LetterAuction.env import LetterAuctionEnv


def _fresh():
    env = LetterAuctionEnv(starting_coins=100)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.round_number == 0
    assert len(env.letters) == 26
    assert env.player_states[0]["coins"] == 100


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("hello")
    assert done is False
    assert env.state.error_count == 1


def test_bid_more_than_coins_rejected():
    env = _fresh()
    done, _ = env.step("bid 101")  # only 100 coins
    assert done is False
    assert env.state.error_count == 1


def test_pass_moves_to_opponent():
    env = _fresh()
    done, _ = env.step("pass")  # P0 passes, opponent hasn't acted
    assert done is False
    assert env.state.current_player_id == 1
    assert env.round_number == 0  # still same letter


def test_valid_bid_sets_amount_and_rotates():
    env = _fresh()
    done, _ = env.step("bid 5")
    assert done is False
    assert env.bid_amount == 5
    assert env.state.current_player_id == 1


def test_bid_then_win_when_opponent_passes():
    env = _fresh()
    letter = env.round_letter
    env.step("bid 5")             # P0 bids 5
    done, _ = env.step("pass")     # P1 passes -> P0 wins the letter
    assert done is False
    assert letter in env.player_states[0]["letters"]
    assert env.player_states[0]["coins"] == 95
    assert env.round_number == 1     # advanced to next letter


def test_all_pass_then_invalid_words_terminal():
    env = _fresh()
    # Pass on every letter -> reach the word-submission phase with no letters.
    guard = 0
    while env.round_number < len(env.letters) and guard < 300:
        env.step("pass")
        guard += 1
    assert env.round_number == len(env.letters)
    offender = env.state.current_player_id
    done, _ = env.step("zzzzq")   # invalid word #1
    assert done is False
    assert env.state.error_count == 1
    done, _ = env.step("zzzzq")   # invalid word #2 -> offender forfeits
    assert done is True
    assert env.state.rewards == {offender: -1, 1 - offender: 1}


def test_zero_bid_is_invalid_and_does_not_mutate_auction():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("bid 0")
    assert not done
    assert env.game_state == before
    assert env.state.current_player_id == 0


def test_pathologically_large_bid_is_invalid_not_an_exception():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("bid " + "9" * 5000)
    assert not done
    assert env.game_state == before


def test_word_requires_the_owned_letter_multiplicity(monkeypatch):
    env = _fresh()
    gs = env.game_state
    gs["round_number"] = len(gs["letters"])
    gs["player_states"][0]["letters"] = ["A", "B"]
    gs["player_states"][0]["letter_values"] = [3, 5]
    monkeypatch.setattr(letter_auction_module, "en_uk_dict", {"aba"})
    before = copy.deepcopy(gs["player_states"][0])
    done, _ = env.step("aba")
    assert not done
    assert gs["player_states"][0] == before


def test_complete_valid_game_reaches_scored_draw():
    env = _fresh()
    while env.round_number < len(env.letters):
        letter = env.round_letter
        target = 0 if letter == "A" else 1 if letter == "I" else None
        current = env.state.current_player_id
        if target is None:
            env.step("pass")
            env.step("pass")
        elif current == target:
            env.step("bid 1")
            env.step("pass")
        else:
            env.step("pass")
            env.step("bid 1")

    assert env.player_states[0]["letters"] == ["A"]
    assert env.player_states[1]["letters"] == ["I"]
    words = {0: "a", 1: "i"}
    done, _ = env.step(words[env.state.current_player_id])
    assert not done
    done, _ = env.step(words[env.state.current_player_id])
    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert env.state.turn == 54
    assert "Auction complete" in env.game_state["rendered_text"]


def test_mixed_auction_command_is_rejected():
    env = _fresh()
    done, _ = env.step("bid 2\npass")
    assert not done
    assert env.state.error_count == 1
    assert env.round_number == 0


def test_seeded_reset_snapshot_and_configuration_bounds():
    first, second = _fresh(), _fresh()
    assert first.letters == second.letters
    snapshot = first.snapshot()
    first.step("pass")
    first.restore(snapshot)
    assert first.current_player == 0
    assert first.round_number == 0
    with pytest.raises(ValueError):
        LetterAuctionEnv(starting_coins=0)
    with pytest.raises(ValueError):
        LetterAuctionEnv(max_turns=0)
    with pytest.raises(ValueError):
        LetterAuctionEnv(max_turns=True)


def test_renderer_is_pure_and_does_not_reveal_future_letter_order():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    rendered = env.render_text()
    assert env.game_state == before
    assert str(env.letters) not in rendered
    assert "Auctioned letters: []" in rendered
    assert f"Current letter: {env.round_letter}" in rendered
