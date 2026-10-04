"""Offline deterministic tests for IteratedRockPaperScissors.

Players alternate submitting a move; a round resolves once both have moved.
current_player_id starts at 0.
"""
import pytest
import textarena as ta

from textarena.envs.IteratedRockPaperScissors.env import IteratedRockPaperScissorsEnv


def _fresh(num_rounds=3):
    env = IteratedRockPaperScissorsEnv(num_rounds=num_rounds)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["round"] == 1
    assert gs["points"] == {0: 0, 1: 0}
    assert env.state.current_player_id == 0
    assert env.state.done is False


def test_player0_sweeps():
    # P0 rock beats P1 scissors every round.
    env = _fresh(num_rounds=3)
    done = False
    for _ in range(3):
        done = env.step("rock")       # player 0
        assert not done
        done = env.step("scissors")   # player 1
    assert done
    assert env.state.game_state["points"] == {0: 3, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_player1_sweeps():
    # P1 paper beats P0 rock every round.
    env = _fresh(num_rounds=3)
    done = False
    for _ in range(3):
        done = env.step("rock")   # player 0
        done = env.step("paper")  # player 1
    assert done
    assert env.state.game_state["points"] == {0: 0, 1: 3}
    assert env.state.rewards == {0: -1, 1: 1}


def test_all_draws_is_overall_draw():
    # Both play rock every round -> all ties -> no points -> draw.
    env = _fresh(num_rounds=2)
    for _ in range(2):
        env.step("rock")
        done = env.step("rock")
    assert done
    assert env.state.game_state["points"] == {0: 0, 1: 0}
    assert env.state.rewards == {0: 0, 1: 0}


def test_shorthand_tokens_accepted():
    env = _fresh(num_rounds=1)
    env.step("r")
    done = env.step("s")  # rock beats scissors -> P0 wins
    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_invalid_format_does_not_end_game():
    env = _fresh(num_rounds=3)
    done = env.step("no valid token here")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh(num_rounds=3)
    env.step("nope")
    done = env.step("still nope")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_round_results_reveal_both_moves_and_running_score_to_both_players():
    env = _fresh(num_rounds=3)
    env.step("rock"); env.step("scissors")  # P0 wins
    env.step("paper"); env.step("paper")    # draw
    for pid in (0, 1):
        messages = [message for _, message, _ in env.state.observations[pid]]
        assert "Player 0 played rock; Player 1 played scissors." in messages
        assert "Score after round 1/3: Player 0 1, Player 1 0." in messages
        assert "Player 0 played paper; Player 1 played paper." in messages
        assert "Score after round 2/3: Player 0 1, Player 1 0." in messages


def test_prompt_states_how_the_game_is_won():
    assert "The player who wins more rounds wins the game; equal round wins is a draw." in _fresh().prompt(0)


def test_pending_move_is_private_and_duplicate_is_atomic():
    env = _fresh(num_rounds=1)
    env.step("rock")
    assert not any(
        event[0] == 0
        and event[2] == ta.ObservationType.PLAYER_ACTION
        and event[3] in (-1, 1)
        for event in env.state.events
    )
    assert "Player 0 🪨" not in env.get_board_str()

    result = env.apply(0, "paper")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state["moves"] == {0: "rock", 1: None}


@pytest.mark.parametrize("player_id", [-1, 1, 2, True])
def test_unauthorized_move_is_rejected_atomically(player_id):
    env = _fresh(num_rounds=1)
    before = env.state.game_state.copy()
    result = env.apply(player_id, "rock")
    assert isinstance(result, ta.Invalid)
    assert env.state.game_state == before


def test_terminal_state_and_renderer_keep_last_round():
    env = _fresh(num_rounds=1)
    env.step("rock")
    done = env.step("scissors")
    assert done
    assert env.state.game_state["round"] == 1
    assert env.state.turn == 2
    assert "Round: 1 / 1" in env.get_board_str()


@pytest.mark.parametrize(
    "num_rounds",
    [pytest.param(10**5000, id="unrenderable-large-int")],
)
def test_invalid_num_rounds_rejected(num_rounds):
    with pytest.raises(ValueError):
        IteratedRockPaperScissorsEnv(num_rounds=num_rounds)
