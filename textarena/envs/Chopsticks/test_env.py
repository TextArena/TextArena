"""Deterministic game-logic tests for Chopsticks-v0."""
import pytest
from textarena.envs.Chopsticks.env import ChopsticksEnv


def _fresh(max_turns=40):
    env = ChopsticksEnv(max_turns=max_turns)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_hands():
    env = _fresh()
    assert env.state.game_state["hands"] == {0: [1, 1], 1: [1, 1]}
    assert env.state.current_player_id == 0


@pytest.mark.parametrize("num_players", [1, 3])
def test_reset_requires_exactly_two_players(num_players):
    with pytest.raises(ValueError):
        ChopsticksEnv().reset(num_players=num_players, seed=42)


@pytest.mark.parametrize("max_turns", [0, -1, True, 1.5])
def test_max_turns_must_be_a_positive_integer(max_turns):
    with pytest.raises(ValueError):
        ChopsticksEnv(max_turns=max_turns)


def test_attack_adds_fingers_and_rotates():
    env = _fresh()
    done, _ = env.step("attack 0 0")
    assert not done
    assert env.state.game_state["hands"][1] == [2, 1]
    assert env.state.current_player_id == 1
    assert env.state.game_state["history"] == [
        "P0 attacks P1’s hand 0: it goes from 1 to 2."
    ]


def test_split_redistributes_fingers():
    env = _fresh()
    done, _ = env.step("split 2 0")
    assert not done
    assert env.state.game_state["hands"][0] == [2, 0]
    assert env.state.current_player_id == 1


def test_split_cannot_stall_by_only_swapping_hand_indices():
    env = _fresh()
    env.state.game_state["hands"][0] = [1, 2]
    before = env.state.game_state["hands"][0].copy()

    done, _ = env.step("split 2 1")

    assert not done
    assert env.state.game_state["hands"][0] == before
    assert env.state.game_state["history"] == []
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_split_cannot_create_hand_above_four_and_is_atomic():
    env = _fresh()
    env.state.game_state["hands"][0] = [4, 2]
    before = env.state.game_state["hands"][0].copy()
    done, _ = env.step("split 6 0")
    assert not done
    assert env.state.game_state["hands"][0] == before
    assert env.state.game_state["history"] == []
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_out_of_range_split_explains_the_finger_limit():
    env = _fresh()
    env.state.game_state["hands"][0] = [4, 2]
    done, _ = env.step("split 5 1")
    assert not done
    assert env.state.game_state["hands"][0] == [4, 2]
    _, observations = env.get_observation()
    assert any("between 0 and 4 fingers" in message for _, message, _ in observations)


def test_prompt_states_goal_split_limits_and_turn_limit():
    env = _fresh(max_turns=12)
    prompt = env.prompt(0)
    assert "You win by making both of your opponent's hands dead." in prompt
    assert "After 12 moves in total, the game is a draw." in prompt
    assert "Each hand holds 0 to 4 fingers" in prompt and "only swapping them is not allowed" in prompt
    assert "You cannot attack with a dead (0) hand or attack a dead hand." in prompt


def test_large_split_token_is_invalid_without_integer_conversion():
    env = _fresh()
    done, _ = env.step(f"split {'9' * 10_000} 0")
    assert not done
    assert env.state.game_state["hands"][0] == [1, 1]
    assert env.state.error_count == 1


def test_killing_both_opponent_hands_wins():
    env = _fresh()
    env.state.game_state["hands"] = {0: [4, 1], 1: [0, 1]}
    done, _ = env.step("attack 0 1")  # 4 + 1 = 5 -> opponent hand dies
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.game_state["hands"][1] == [0, 0]


def test_deterministic_complete_game_without_state_injection():
    env = _fresh()
    moves = [
        "attack 0 0",  # P1 [2,1]
        "attack 0 0",  # P0 [3,1]
        "attack 0 0",  # P1 [0,1]
        "attack 1 0",  # P0 [4,1]
        "attack 0 1",  # P1 [0,0]
    ]
    for move in moves:
        done, _ = env.step(move)
    assert done
    assert env.state.game_state["hands"] == {0: [4, 1], 1: [0, 0]}
    assert env.state.rewards == {0: 1, 1: -1}


def test_attacking_dead_hand_is_illegal():
    env = _fresh()
    env.state.game_state["hands"][1] = [0, 1]
    done, _ = env.step("attack 0 0")  # opponent hand 0 is dead
    assert not done
    assert env.state.error_count == 1


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("do a thing")
    assert not done
    assert env.state.error_count == 1


def test_turn_limit_results_in_draw():
    env = _fresh(max_turns=2)
    done, _ = env.step("split 2 0")
    assert not done
    done, _ = env.step("split 2 0")
    assert done
    assert env.state.turn == 2
    assert env.state.rewards == {0: 0, 1: 0}


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_snapshot_restore_and_repeat_reset_restore_hands_and_history():
    env = _fresh()
    snap = env.snapshot()
    env.step("attack 0 0")
    env.restore(snap)
    assert env.state.game_state == {"hands": {0: [1, 1], 1: [1, 1]}, "history": []}
    assert env.state.current_player_id == 0
    env.reset(num_players=2, seed=42)
    assert env.state.game_state == {"hands": {0: [1, 1], 1: [1, 1]}, "history": []}
