"""Deterministic offline tests for the NewRecruit negotiation environment.

Player 0 is the Recruiter, Player 1 the Candidate. Proposals use one letter
(A-E) per issue for the 8 issues, in order:
    Salary, Signing Bonus, Job Assignment, Company Car,
    Starting Date, Vacation Days, Moving Expense Reimbursement, Insurance Coverage
"""
import time

import pytest

import textarena as ta
from textarena.envs.NewRecruit.env import NewRecruitEnv


def _fresh(**kwargs):
    env = NewRecruitEnv(**kwargs)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initializes_roles_and_preferences():
    env = _fresh()
    gs = env.state.game_state
    assert gs["roles"] == {0: "Recruiter", 1: "Candidate"}
    assert gs["current_proposal"] is None
    assert gs["accepted_proposal"] is None
    issues = [
        "Salary", "Signing Bonus", "Job Assignment", "Company Car",
        "Starting Date", "Vacation Days", "Moving Expense Reimbursement",
        "Insurance Coverage",
    ]
    for pid in (0, 1):
        for issue in issues:
            assert issue in gs["player_preferences"][pid]


def test_prompt_names_the_opponent_role_instead_of_a_placeholder():
    env = _fresh()
    recruiter_prompt, candidate_prompt = env.prompt(0), env.prompt(1)
    assert "{opponent_role}" not in recruiter_prompt + candidate_prompt
    assert "convince Candidate" in recruiter_prompt
    assert "persuade Candidate" in recruiter_prompt
    assert "convince Recruiter" in candidate_prompt
    assert "persuade Recruiter" in candidate_prompt


def test_propose_then_accept_recruiter_wins():
    env = _fresh()
    # "EEAAAEEE" heavily favours the Recruiter (score 14800 vs -4800).
    done, _ = env.step("This is a fair split.\nPropose EEAAAEEE")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["current_proposal"] is not None

    done, _ = env.step("Accept")
    assert done
    proposal = env.state.game_state["accepted_proposal"]["choices"]
    assert env._calculate_score(0, proposal) > env._calculate_score(1, proposal)
    assert env.state.rewards == {0: 1, 1: -1}


def test_reject_clears_current_proposal():
    env = _fresh()
    env.step("Propose AABCDEAA")
    assert env.state.game_state["current_proposal"] is not None
    done, _ = env.step("Reject")
    assert not done
    assert env.state.game_state["current_proposal"] is None
    assert len(env.state.game_state["proposal_history"]) == 1
    assert env.state.game_state["proposal_history"][0]["accepted"] is False


def test_proposal_parses_letters_to_choices():
    env = _fresh()
    env.step("Propose AABCDEAA")
    choices = env.state.game_state["current_proposal"]["choices"]
    assert choices["Salary"] == "$60000"          # A
    assert choices["Job Assignment"] == "Division B"  # B
    assert choices["Company Car"] == "RAND XTR"    # C
    assert choices["Starting Date"] == "Jul 15"    # D
    assert choices["Vacation Days"] == "10 days"   # E


def test_invalid_action_first_time_increments_error():
    env = _fresh(error_allowance=3)
    done, _ = env.step("just some rambling text")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_proposal"] is None


def test_incidental_accept_in_prose_is_not_a_decision():
    env = _fresh()
    env.step("Propose AABCDEAA")
    done, _ = env.step("I cannot accept this proposal yet.")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["current_proposal"] is not None


def test_repeated_invalids_end_game():
    env = _fresh(error_allowance=1)
    done, _ = env.step("garbage")
    assert not done
    done, _ = env.step("more garbage")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_max_turns_without_agreement_is_draw():
    env = _fresh(max_turns=2)
    # The turn limit is checked before the counter increments, so play until the
    # game ends (no proposal is ever accepted).
    actions = ["Propose AAAAAAAA", "Reject", "Propose BAAAAAAA", "Reject"]
    done = False
    for a in actions:
        done, _ = env.step(a)
        if done:
            break
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_counterproposal_replaces_pending_proposal_atomically():
    env = _fresh()
    env.step("Propose AAAAAAAA")
    done, _ = env.step("A counteroffer follows.\nPropose BBBBBBBB")
    assert not done
    gs = env.state.game_state
    assert gs["current_proposal"]["proposer_id"] == 1
    assert gs["current_rationale"] == "A counteroffer follows."
    assert len(gs["proposal_history"]) == 2


def test_mixed_or_trailing_commands_do_not_create_a_proposal():
    env = _fresh()
    for action in (
        "Propose AAAAAAAA\nAccept",
        "Propose AAAAAAAA trailing words",
        "Accept\nPropose AAAAAAAA",
    ):
        before = list(env.state.game_state["proposal_history"])
        done, _ = env.step(action)
        assert not done
        assert env.state.game_state["proposal_history"] == before
        assert env.state.game_state["current_proposal"] is None


def test_proposer_cannot_accept_own_proposal_even_if_turn_is_tampered():
    env = _fresh()
    env.step("Propose AAAAAAAA")
    env.state.current_player_id = 0
    done, _ = env.step("Accept")
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["accepted_proposal"] is None


def test_reject_clears_proposal_rationale():
    env = _fresh()
    env.step("Please consider this.\nPropose AAAAAAAA")
    env.step("Reject")
    assert env.state.game_state["current_rationale"] is None


def test_repeat_reset_restores_pristine_state():
    env = _fresh()
    env.step("Propose AAAAAAAA")
    env.reset(num_players=2, seed=42)
    assert env.state.game_state["proposal_history"] == []
    assert env.state.game_state["current_proposal"] is None
    assert env.state.current_player_id == 0


def test_snapshot_restore_replays_proposal():
    env = _fresh()
    before = env.snapshot()
    env.step("Reasoned offer.\nPropose ABCDEABC")
    expected = env.snapshot()
    env.restore(before)
    env.step("Reasoned offer.\nPropose ABCDEABC")
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_turns": 0}, "max_turns"),
        ({"max_turns": True}, "max_turns"),
        ({"error_allowance": -1}, "error_allowance"),
        ({"error_allowance": False}, "error_allowance"),
    ],
)
def test_invalid_configuration_is_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        NewRecruitEnv(**kwargs)


def test_line_padded_input_is_rejected_quickly():
    env = _fresh()
    start = time.perf_counter()
    done, _ = env.step("a" + " \n" * 1500 + "x")
    assert time.perf_counter() - start < 1.0
    assert not done and env.state.error_count == 1


def test_padded_decision_is_rejected_quickly():
    env = _fresh()
    env.step("Propose AAAAAAAA")
    start = time.perf_counter()
    done, _ = env.step("Accept" + " " * 32_000 + "x")
    assert time.perf_counter() - start < 1.0
    assert not done and env.state.error_count == 1
    assert env.state.game_state["accepted_proposal"] is None


def test_multiline_rationale_and_padded_commands_still_parse():
    env = _fresh()
    env.step("  First point.\n\n  Second point.  \n  [Propose] a b c d e a b c  \n")
    gs = env.state.game_state
    assert gs["current_rationale"] == "First point.\n\n  Second point."
    assert gs["current_proposal"]["choices"]["Job Assignment"] == "Division C"
    done, _ = env.step("  [ accept ]  ")
    assert done


def test_prompt_states_the_actual_win_and_draw_rules():
    prompt = _fresh().prompt(1)
    assert "the player with the higher total wins" in prompt
    assert "the game ends in a draw" in prompt
    assert "0 points for both" not in prompt


def test_acting_player_sees_the_decoded_proposal_scored_with_their_own_points():
    env = _fresh()
    env.get_observation()
    env.step("This is a fair split.\nPropose EEAAAEEE")
    _, observation = env.get_observation()
    board = [message for _, message, kind in observation if kind == ta.ObservationType.GAME_BOARD][-1]
    assert "Turn 2 of 10" in board
    assert "Propose EEAAAEEE" in board
    assert "Salary: E. $52000 (-6000 points for you)" in board
    assert "Total for you: -4800 points" in board
    assert "14800" not in board  # the Recruiter's score stays private


def test_accept_without_a_proposal_explains_why():
    env = _fresh()
    env.step("Accept")
    _, observation = env.get_observation()
    assert any("There is no proposal to accept" in message for _, message, _ in observation)
