"""Unit tests for Tak's termination logic.

The multilingual golden covers the road win and the board-full flat-win / draw,
but the turn-cap safeguard and the flat-count helpers are awkward to force from a
fixed scenario, so they get dedicated tests here. These guard the fix for the
original non-termination bug (a game with no road used to never end).
"""
import pytest

from textarena.envs.Tak.env import TakEnv


def _place(r, c, tok):
    return f"[place () {{({r},{c}): [{tok}]}}]"


@pytest.fixture
def env():
    e = TakEnv()
    e.lang = "en"
    return e


# ── flat counting ────────────────────────────────────────────────────────────
def test_flat_counts_only_flats(env):
    env.reset(num_players=2, seed=0)
    # hand-place a mix directly on the board: flats, a wall, a capstone
    env.board[0][0] = ["F0"]
    env.board[0][1] = ["F0"]
    env.board[1][0] = ["W0"]   # wall: does NOT count
    env.board[1][1] = ["C1"]   # capstone: does NOT count
    env.board[2][2] = ["F1"]
    env.board[2][3] = ["F0", "F1"]  # only the top ('F1') counts, for player 1
    assert env._flat_counts() == {0: 2, 1: 2}


def test_board_full_detection(env):
    env.reset(num_players=2, seed=0)
    assert env._board_full() is False
    for r in range(env.board_size):
        for c in range(env.board_size):
            env.board[r][c] = ["F0"]
    assert env._board_full() is True


def test_out_of_pieces(env):
    env.reset(num_players=2, seed=0)
    assert env._out_of_pieces(0) is False
    env.players[0]["stones"] = 0
    assert env._out_of_pieces(0) is False   # still has a capstone
    env.players[0]["capstones"] = 0
    assert env._out_of_pieces(0) is True


# ── termination: the safeguard turn cap ──────────────────────────────────────
def test_turn_cap_resolves_and_terminates():
    """A road-less move-shuffle game must end at the turn cap (was: never ended)."""
    env = TakEnv(max_turns=8)
    env.lang = "en"
    env.reset(num_players=2, seed=0)
    done, _ = env.step(_place(0, 0, "F0"))   # P0
    assert not done
    done, _ = env.step(_place(3, 3, "F1"))   # P1
    assert not done
    # shuffle two lone flats back and forth; no road can form, board never fills
    moves = [
        "[move (0,0) {(0,1): [F0]}]", "[move (3,3) {(3,2): [F1]}]",
        "[move (0,1) {(0,0): [F0]}]", "[move (3,2) {(3,3): [F1]}]",
    ] * 5
    for mv in moves:
        done, _ = env.step(mv)
        if done:
            break
    assert done, "game must terminate at the turn cap"
    assert env.state.turn >= env.state.max_turns
    # resolved by flat count; here it is a 1-1 tie -> draw
    assert env.state.rewards == {0: 0, 1: 0}


def test_road_win_still_wins():
    """A completed road ends the game immediately for the road-builder."""
    env = TakEnv()
    env.lang = "en"
    env.reset(num_players=2, seed=0)
    seq = [_place(0, 0, "F0"), _place(0, 3, "F1"),
           _place(1, 0, "F0"), _place(1, 3, "F1"),
           _place(2, 0, "F0"), _place(2, 3, "F1"),
           _place(3, 0, "F0")]  # P0 connects column 0 (top edge -> bottom edge)
    done = False
    for a in seq:
        done, _ = env.step(a)
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
