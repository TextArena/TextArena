"""Deterministic game-logic tests for ColonelBlotto."""
import copy

import pytest

from textarena.envs.ColonelBlotto.env import ColonelBlottoEnv


def _fresh(num_fields=3, num_total_units=3, num_rounds=1):
    env = ColonelBlottoEnv(num_fields=num_fields, num_total_units=num_total_units, num_rounds=num_rounds)
    env.reset(num_players=2, seed=42)
    return env


def test_player0_wins_single_round_game():
    env = _fresh()
    # Round only resolves once BOTH commanders have allocated.
    done, _ = env.step("A2 B1 C0")  # player 0 takes fields A and B
    assert not done and env.state.current_player_id == 1
    done, _ = env.step("A0 B0 C3")  # player 1 only takes field C
    assert done and env.state.rewards == {0: 1, 1: -1}
    assert env.state.turn == 2


def test_draw_when_field_counts_tie():
    # Two fields, one each -> tied round, and after the only round it's a draw.
    env = _fresh(num_fields=2, num_total_units=2, num_rounds=1)
    env.step("A2 B0")  # p0 wins A
    done, _ = env.step("A0 B2")  # p1 wins B -> tie round
    assert done and env.state.rewards == {0: 0, 1: 0}


def test_scores_update_after_round():
    env = _fresh()
    env.step("A3 B0 C0")
    env.step("A0 B3 C0")
    # Each won exactly one field -> tie round, both scores stay 0.
    assert env.state.game_state["scores"] == {0: 0, 1: 0}


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no allocation here")
    assert not done and env.state.error_count == 1


def test_illegal_wrong_unit_sum_rejected():
    env = _fresh()
    # Well-formatted but does not sum to the required number of units.
    done, _ = env.step("A1 B1 C0")
    assert not done and env.state.error_count == 1


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("bad")
    done, _ = env.step("A9 B9 C9")  # wrong sum again
    assert done and env.state.rewards == {0: -1, 1: 1}


def test_duplicate_or_mixed_allocation_tokens_are_rejected_atomically():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("A1 A2 B0 C0")
    assert not done
    assert env.game_state == before

    done, _ = env.step("A1 B1 C1; Accept")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_sealed_allocation_renderer_is_pure_and_hides_units():
    env = _fresh(num_rounds=2)
    env.step("A3 B0 C0")
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert "A:3" not in board
    assert "  3  " not in board
    assert "Complete" in board


def test_sealed_allocation_action_is_not_routed_to_opponent():
    env = _fresh(num_rounds=2)
    env.step("A3 B0 C0")
    opponent_messages = [message for _, message, _ in env.state.observations[1]]
    assert not any(message.strip() == "A3 B0 C0" for message in opponent_messages)


def test_terminal_resolution_does_not_announce_phantom_next_round():
    env = _fresh(num_rounds=1)
    env.step("A2 B1 C0")
    done, _ = env.step("A0 B0 C3")
    assert done
    messages = [message for _, message, _, _ in env.state.events]
    assert not any("Round 2/1" in message for message in messages)


def test_terminal_board_preserves_final_battle_and_is_repeatable():
    env = _fresh(num_rounds=1)
    env.step("A2 B1 C0")
    done, _ = env.step("A0 B0 C3")
    assert done

    before = copy.deepcopy(env.game_state)
    first = env.get_board_str()
    second = env.get_board_str()
    assert env.game_state == before
    assert first == second
    assert "Round 1 - Results Phase" in first
    assert "Round 2" not in first
    assert "│    A  │   2   │   0" in first
    assert "Alpha" in first


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_fields": 1},
        {"num_fields": 27},
        {"num_total_units": 2},
        {"num_rounds": 0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        ColonelBlottoEnv(**kwargs)


def test_snapshot_restores_hidden_round_allocation():
    env = _fresh(num_rounds=2)
    snapshot = env.snapshot()
    env.step("A3 B0 C0")
    env.restore(snapshot)
    assert env.game_state["player_states"][0]["allocation_complete"] is False
    assert env.game_state["fields"][0]["player_0_units"] == 0
