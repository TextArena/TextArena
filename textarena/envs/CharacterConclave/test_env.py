"""Deterministic tests for CharacterConclave-v0.

The scored outcome depends only on message length + votes (no LLM jury), so it is fully
offline.
"""
import pytest
import textarena as ta
from textarena.envs.CharacterConclave.env import CharacterConclaveEnv


def _fresh(num_players=3, budget=5):
    env = CharacterConclaveEnv(character_budget=budget)
    env.reset(num_players=num_players, seed=42)
    return env


def test_reset_sets_discussion_phase_and_budgets():
    env = _fresh()
    gs = env.state.game_state
    assert gs["phase"] == "discussion"
    assert gs["budget_remaining"] == {0: 5, 1: 5, 2: 5}
    assert gs["votes"] == {}
    assert env.state.current_player_id == 0


def test_player_count_bounds_accept_minimum_and_maximum_only():
    CharacterConclaveEnv(character_budget=1).reset(num_players=3, seed=42)
    CharacterConclaveEnv(character_budget=1).reset(num_players=15, seed=42)
    for num_players in (2, 16):
        with pytest.raises(AssertionError):
            CharacterConclaveEnv(character_budget=1).reset(
                num_players=num_players,
                seed=42,
            )


@pytest.mark.parametrize("budget", [0, -1, 1.5, True])
def test_character_budget_must_be_a_positive_integer(budget):
    with pytest.raises(ValueError):
        CharacterConclaveEnv(character_budget=budget)


def test_each_player_gets_a_prompt():
    env = _fresh()
    for pid in range(3):
        kinds = [obs[2] for obs in env.state.observations[pid]]
        assert ta.ObservationType.PROMPT in kinds


def test_discussion_message_consumes_budget():
    env = _fresh()
    env.step("aaaaa")  # 5 chars -> should exhaust player 0's budget
    assert env.state.game_state["budget_remaining"][0] == 0


def test_overlong_message_is_truncated_to_budget():
    env = _fresh()
    env.step("aaaaaaaaaa")  # 10 chars, but only 5 budget remain
    assert env.state.game_state["budget_remaining"][0] == 0
    assert any(
        message == "aaaaa" and kind == ta.ObservationType.PLAYER_ACTION and target == -1
        for _, message, kind, target in env.state.events
    )
    assert not any(message == "aaaaaaaaaa" for _, message, _, _ in env.state.events)


def test_overlong_message_cannot_truncate_to_blank_content():
    env = _fresh(budget=2)
    before_events = len(env.state.events)
    done, _ = env.step("  hidden-after-budget")

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state["budget_remaining"][0] == 2
    assert not any(
        kind == ta.ObservationType.PLAYER_ACTION
        for _, _, kind, _ in env.state.events[before_events:]
    )


def test_empty_discussion_message_is_invalid_and_atomic():
    env = _fresh()
    before = env.state.game_state["budget_remaining"].copy()
    done, _ = env.step("   ")
    assert not done
    assert env.state.game_state["budget_remaining"] == before
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_discussion_rotation_skips_exhausted_players():
    env = _fresh(budget=3)
    env.step("a")    # P0 retains two characters.
    env.step("bbb")  # P1 is exhausted.
    env.step("ccc")  # P2 is exhausted; rotation returns to P0.
    assert env.state.current_player_id == 0
    env.step("zz")
    assert env.state.game_state["phase"] == "voting"
    assert env.state.current_player_id == 0


def test_exhausting_all_budgets_starts_voting_phase():
    env = _fresh()
    env.step("aaaaa")  # P0 spends full budget
    env.step("bbbbb")  # P1
    env.step("ccccc")  # P2 -> nobody has budget left
    assert env.state.game_state["phase"] == "voting"


def test_full_game_winner_by_votes():
    env = _fresh()
    # Discussion: each player spends their full budget in one message.
    env.step("aaaaa")  # P0
    env.step("bbbbb")  # P1
    env.step("ccccc")  # P2 -> voting phase begins, P2 votes first
    assert env.state.game_state["phase"] == "voting"
    assert env.state.current_player_id == 2
    env.step("0")          # P2 votes for P0
    done, _ = env.step("1")  # P0 votes for P1
    assert not done
    done, _ = env.step("0")  # P1 votes for P0 -> P0 has 2 votes, P1 has 1, P2 has 0
    assert done
    assert env.state.game_state["votes"] == {2: 0, 0: 1, 1: 0}
    assert env.state.rewards[0] == 1.0   # most votes
    assert env.state.rewards[2] == -1.0  # fewest votes
    assert -1.0 < env.state.rewards[1] < 1.0


def test_equal_vote_cycle_is_a_draw_not_a_collective_loss():
    env = _fresh(budget=1)
    for message in ("a", "b", "c"):
        env.step(message)
    for vote in ("0", "1", "2"):  # P2->P0, P0->P1, P1->P2
        done, _ = env.step(vote)
    assert done
    assert env.state.rewards == {0: 0.0, 1: 0.0, 2: 0.0}
    board = env.get_board_str()
    assert "Final Vote Count" in board
    assert all(f"Player {pid}: 1 vote(s)" in board for pid in range(3))
    assert any(
        message == "Final vote count: P0=1, P1=1, P2=1" and target == -1
        for _, message, _, target in env.state.events
    )


def test_players_tied_in_middle_receive_the_same_reward():
    env = _fresh(num_players=5, budget=1)
    for message in ("a", "b", "c", "d", "e"):
        env.step(message)
    # Voting order is P4, P0, P1, P2, P3. Counts: P0=2, P1=P2=P3=1, P4=0.
    for vote in ("3", "1", "0", "0", "2"):
        done, _ = env.step(vote)
    assert done
    assert env.state.rewards == {0: 1.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: -1.0}


def test_vote_is_private_and_eliminated_target_is_rejected():
    env = _fresh(budget=1)
    for message in ("a", "b", "c"):
        env.step(message)
    env.eliminate(0)
    before_events = len(env.state.events)
    done, _ = env.step("0")
    assert not done
    assert env.state.game_state["votes"] == {}
    assert env.state.current_player_id == 2
    assert not any(
        kind == ta.ObservationType.PLAYER_ACTION
        for _, _, kind, _ in env.state.events[before_events:]
    )


def test_valid_vote_confirmation_is_private_and_vote_cannot_be_replaced():
    env = _fresh(budget=1)
    for message in ("a", "b", "c"):
        env.step(message)
    before_events = len(env.state.events)
    env.step("0")  # P2 votes.
    new_events = env.state.events[before_events:]
    confirmations = [
        event for event in new_events
        if "successfully voted" in event[1]
    ]
    assert confirmations == [
        (-1, "You have successfully voted for Player 0.", ta.ObservationType.GAME_MESSAGE, 2)
    ]
    env.set_current_player(2)
    done, _ = env.step("1")
    assert not done
    assert env.state.game_state["votes"][2] == 0
    assert env.state.error_count == 1


def test_snapshot_and_repeat_reset_restore_vote_queue():
    env = _fresh(budget=1)
    for message in ("a", "b", "c"):
        env.step(message)
    snap = env.snapshot()
    env.step("0")
    env.restore(snap)
    assert env.state.game_state["votes"] == {}
    assert env.state.current_player_id == 2
    env.reset(num_players=3, seed=42)
    assert env.state.game_state["phase"] == "discussion"
    assert env.state.game_state["budget_remaining"] == {0: 1, 1: 1, 2: 1}
