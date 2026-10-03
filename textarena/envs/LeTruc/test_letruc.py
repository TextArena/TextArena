"""Unit tests for Le Truc's rule-critical helpers.

The multilingual scenario goldens exercise the common paths (leads, spoilt
tricks, raises, folds, match-to-12), but two faithful-Truc rules cannot be
forced from a fixed action list against a shuffled deck:

  * an all-three-tricks-tied hand (the "void" outcome), and
  * the full trick-ranking table (which rank beats which).

These are the parts most likely to regress silently, so they get a dedicated
test here.
"""
import pytest

from textarena.envs.LeTruc.env import LeTrucEnv


@pytest.fixture
def env():
    return LeTrucEnv()


# ── trick resolution (_resolve) ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "results, expected",
    [
        ([0, 0], 0),                     # two tricks outright
        ([1, 1], 1),
        ([0, 1, 0], 0),                  # 1-1 then a decider
        ([0, None], 0),                  # win first, second spoilt -> first-trick winner
        ([None, 0], 0),                  # spoilt credited to the first non-tied winner
        ([None, None, 0], 0),            # two spoilt + a win -> that player
        ([0, 1, None], 0),               # 1-1 + a final spoilt -> credited to first winner
        ([None, None, None], None),      # ALL THREE TIED -> void, nobody scores
        ([0], "undecided"),              # only one trick played so far
        ([None], "undecided"),           # a lone spoilt trick decides nothing yet
    ],
)
def test_resolve(env, results, expected):
    assert env._resolve(results) == expected


def test_resolve_void_only_after_three_tricks(env):
    """A void is returned only once all three tricks are in; earlier spoilts stay 'undecided'."""
    assert env._resolve([None]) == "undecided"
    assert env._resolve([None, None]) == "undecided"
    assert env._resolve([None, None, None]) is None


# ── rank ordering (_rank_idx) ────────────────────────────────────────────────
def test_rank_order_high_to_low(env):
    """Truc order high->low is 3 2 A K Q J 7 6 5 4 (lower index == stronger)."""
    order = ["3", "2", "A", "K", "Q", "J", "7", "6", "5", "4"]
    idxs = [env._rank_idx(r + "♠") for r in order]  # suit is ignored
    assert idxs == list(range(len(order)))


def test_rank_beats(env):
    # a few concrete match-ups a player would rely on
    assert env._rank_idx("3♣") < env._rank_idx("2♦")   # 3 beats 2
    assert env._rank_idx("A♥") < env._rank_idx("K♠")   # ace beats king
    assert env._rank_idx("7♠") < env._rank_idx("4♣")   # 7 beats 4
    assert env._rank_idx("K♣") == env._rank_idx("K♠")  # suits never break a tie


# ── stake ladder (_next_stake) ───────────────────────────────────────────────
def test_stake_ladder(env):
    """First raise lifts 1->2, then +2 each up to a hard cap of 12."""
    assert env._next_stake(1) == 2
    assert env._next_stake(2) == 4
    assert env._next_stake(4) == 6
    assert env._next_stake(6) == 8
    assert env._next_stake(8) == 10
    assert env._next_stake(10) == 12
    assert env._next_stake(12) == 12   # capped
