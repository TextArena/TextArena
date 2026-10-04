"""Offline deterministic tests for IteratedMatchingPennies.

Player 0 is the "Matcher" (wins a round when both pick the same side);
Player 1 is the "Mismatcher" (wins when the picks differ).
Players alternate: current_player_id starts at 0, rotates every valid step.
"""
import pytest
import textarena as ta

from textarena.envs.IteratedMatchingPennies.env import IteratedMatchingPenniesEnv


def _fresh(num_rounds=3):
    env = IteratedMatchingPenniesEnv(num_rounds=num_rounds)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["round"] == 1
    assert gs["points"] == {0: 0, 1: 0}
    assert env.state.current_player_id == 0
    assert env.state.done is False


def test_player0_matcher_sweeps():
    # Both always pick heads -> every round matches -> Player 0 wins all.
    env = _fresh(num_rounds=3)
    done = False
    for _ in range(3):
        done, _ = env.step("heads")  # player 0
        assert not done
        done, _ = env.step("heads")  # player 1
    assert done
    assert env.state.game_state["points"] == {0: 3, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_player1_mismatcher_sweeps():
    # Player 0 heads, Player 1 tails -> mismatch every round -> Player 1 wins.
    env = _fresh(num_rounds=3)
    done = False
    for _ in range(3):
        done, _ = env.step("heads")  # player 0
        done, _ = env.step("tails")  # player 1
    assert done
    assert env.state.game_state["points"] == {0: 0, 1: 3}
    assert env.state.rewards == {0: -1, 1: 1}


def test_overall_draw():
    # Round 1 matches (P0 point), round 2 mismatches (P1 point) -> 1-1 draw.
    env = _fresh(num_rounds=2)
    env.step("heads"); env.step("heads")   # round 1: match
    done, _ = env.step("heads")
    done, _ = env.step("tails")              # round 2: mismatch
    assert done
    assert env.state.game_state["points"] == {0: 1, 1: 1}
    assert env.state.rewards == {0: 0, 1: 0}


def test_shorthand_tokens_accepted():
    env = _fresh(num_rounds=1)
    env.step("h")
    done, _ = env.step("t")  # mismatch -> P1 wins the single round
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_invalid_format_does_not_end_game():
    env = _fresh(num_rounds=3)
    done, _ = env.step("I refuse to choose")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0  # turn did not rotate
    # A valid resubmission continues normally.
    done, _ = env.step("heads")
    assert not done
    assert env.state.current_player_id == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh(num_rounds=3)
    done, _ = env.step("garbage")
    assert not done
    done, _ = env.step("still garbage")
    assert done
    # Offending player (0) loses.
    assert env.state.rewards == {0: -1, 1: 1}


def test_pending_choice_is_hidden_and_duplicate_is_atomic():
    env = _fresh(num_rounds=1)
    env.step("heads")
    assert not any(
        event[0] == 0 and event[2] == ta.ObservationType.PLAYER_ACTION
        for event in env.state.events
    )
    assert "P0→heads" not in env.get_board_str()

    result = env.apply(0, "tails")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state["moves"] == {0: "heads"}


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_choice_is_rejected_atomically(player_id):
    env = _fresh(num_rounds=1)
    before = env.state.game_state.copy()
    result = env.apply(player_id, "heads")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_terminal_state_keeps_last_round_and_turn_count():
    env = _fresh(num_rounds=1)
    env.step("heads")
    done, _ = env.step("heads")
    assert done
    assert env.state.game_state["round"] == 1
    assert env.state.turn == 2


def test_snapshot_restore_and_reset_preserve_hidden_choice_lifecycle():
    env = _fresh(num_rounds=1)
    env.step("heads")
    snapshot = env.snapshot()
    env.step("tails")
    assert env.state.rewards == {0: -1, 1: 1}

    env.restore(snapshot)
    assert env.state.current_player_id == 1
    assert env.state.game_state["moves"] == {0: "heads"}
    assert "P0→heads" not in env.get_board_str()
    done, _ = env.step("heads")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}

    env.reset(num_players=2, seed=42)
    assert env.state.game_state["moves"] == {}
    assert env.state.game_state["history"] == []
    assert env.state.game_state["points"] == {0: 0, 1: 0}


@pytest.mark.parametrize(
    "num_rounds",
    [0, -1, 1.5, True, pytest.param(10**5000, id="unrenderable-large-int")],
)
def test_invalid_num_rounds_rejected(num_rounds):
    with pytest.raises(ValueError):
        IteratedMatchingPenniesEnv(num_rounds=num_rounds)
