"""Offline deterministic tests for the WinAsMuchAsYouCan environment.

A fully offline 4-player game (no LLM). Each of 10 rounds every player secretly
picks X or Y; rounds 5/8/10 add a talk phase first (multipliers 3x/5x/10x). This
suite consolidates the previous test file, driving whole games through the public
``env.step`` API and asserting the real reward convention (winners +1 / others -1).
"""
import pytest

from textarena.envs.WinAsMuchAsYouCan.env import WinAsMuchAsYouCanEnv


COMMUNICATION_ROUNDS = {5, 8, 10}
MULTIPLIER_SUM = 1 + 1 + 1 + 1 + 3 + 1 + 1 + 5 + 1 + 10  # == 25


def _fresh():
    env = WinAsMuchAsYouCanEnv()
    env.reset(num_players=4, seed=42)
    return env


def _advance_to_first_talk_phase(env):
    for _ in range(4):
        for _ in range(4):
            done, _ = env.step("Choose Y")
            assert not done
    assert env.state.game_state["current_phase"] == "talk"


def _play_full_game(env, act_actions):
    """Drive a complete 10-round game.

    ``act_actions`` is a list of four action strings applied (in player order
    0..3) during every act phase. Talk phases are ended immediately by having
    all four players pass.
    """
    done = False
    for rnd in range(1, 11):
        if rnd in COMMUNICATION_ROUNDS:
            for _ in range(4):  # everyone passes -> talk phase ends
                assert not done
                done, _ = env.step("Pass")
        for action in act_actions:
            assert not done
            done, _ = env.step(action)
    return done


def test_reset_initial_state():
    env = _fresh()
    assert env.state.num_players == 4
    assert env.state.current_player_id == 0
    gs = env.state.game_state
    assert gs["current_round"] == 1
    assert gs["current_phase"] == "act"
    assert gs["player_scores"] == {0: 0, 1: 0, 2: 0, 3: 0}


def test_reset_requires_four_players():
    env = WinAsMuchAsYouCanEnv()
    with pytest.raises(ValueError):
        env.reset(num_players=3, seed=42)


def test_act_phase_advances_to_next_chooser():
    env = _fresh()
    done, _ = env.step("Choose X")
    assert not done
    assert env.state.game_state["player_choices"][0] == "X"
    assert env.state.current_player_id == 1  # advanced to next chooser


def test_invalid_action_does_not_advance_turn():
    env = _fresh()
    done, _ = env.step("this is not a valid choice")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_talk_phase_accepts_bare_broadcast_and_whisper_commands():
    env = _fresh()
    _advance_to_first_talk_phase(env)

    done, _ = env.step("Broadcast: let's coordinate")
    assert not done
    assert env.state.game_state["talk_messages"][-1]["type"] == "broadcast"

    done, _ = env.step("Whisper 2: I will choose Y")
    assert not done
    whisper = env.state.game_state["talk_messages"][-1]
    assert whisper["type"] == "whisper"
    assert whisper["to"] == 2


def test_talk_phase_does_not_parse_incidental_prose_as_command():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    done, _ = env.step("I may broadcast a plan later")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_single_round_scoring_defector_leads():
    env = _fresh()
    # Round 1 (1x): player 0 picks X, everyone else Y -> X:+3, Y:-1 each.
    for action in ["Choose X", "Choose Y", "Choose Y", "Choose Y"]:
        env.step(action)
    scores = env.state.game_state["player_scores"]
    assert scores == {0: 3, 1: -1, 2: -1, 3: -1}
    assert env.state.game_state["current_round"] == 2


def test_full_game_single_winner():
    env = _fresh()
    # Player 0 defects (X) every round; others cooperate (Y).
    done = _play_full_game(env, ["Choose X", "Choose Y", "Choose Y", "Choose Y"])
    assert done
    scores = env.state.game_state["player_scores"]
    # X earns +3*mult, Y earns -1*mult; summed over all round multipliers.
    assert scores[0] == 3 * MULTIPLIER_SUM
    assert scores[1] == scores[2] == scores[3] == -1 * MULTIPLIER_SUM
    assert env.state.rewards == {0: 1, 1: -1, 2: -1, 3: -1}


def test_full_game_all_cooperate_is_tie():
    env = _fresh()
    # Everyone picks Y every round -> all gain +1*mult, so a 4-way tie.
    done = _play_full_game(env, ["Choose Y"] * 4)
    assert done
    scores = env.state.game_state["player_scores"]
    assert all(s == MULTIPLIER_SUM for s in scores.values())
    # All players tie as winners under the +1/-1 convention.
    assert env.state.rewards == {0: 1, 1: 1, 2: 1, 3: 1}


def test_secret_choice_is_not_echoed_to_other_players():
    env = _fresh()
    event_start = len(env.state.events)
    env.step("Choose X")
    new_events = env.state.events[event_start:]
    assert not any(message.strip() == "Choose X" and to_id in (-1, 1, 2, 3)
                   for _, message, _, to_id in new_events)
    assert env.state.game_state["player_choices"] == {0: "X"}


def test_talk_limit_is_enforced_per_player():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    env.step("Broadcast: first")
    env.step("Pass")
    env.step("Pass")
    env.step("Pass")
    for index in range(9):
        env.step(f"Broadcast: solo message {index}")
    gs = env.state.game_state
    assert gs["talk_actions_by_player"][0] == 10
    assert gs["current_phase"] == "act"
    assert env.state.current_player_id == 0


def test_all_negative_tie_still_awards_shared_victory():
    env = _fresh()
    done = _play_full_game(env, ["Choose X"] * 4)
    assert done
    assert all(score == -MULTIPLIER_SUM for score in env.state.game_state["player_scores"].values())
    assert env.state.rewards == {0: 1, 1: 1, 2: 1, 3: 1}


def test_private_whisper_content_is_routed_only_to_participants():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    event_start = len(env.state.events)
    env.step("Whisper 2: secret pact")
    private_events = [
        (message, to_id)
        for _, message, _, to_id in env.state.events[event_start:]
        if "secret pact" in message
    ]
    assert private_events
    assert {to_id for _, to_id in private_events} == {0, 2}


def test_repeat_reset_clears_round_and_talk_state():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    env.step("Broadcast: hello")
    env.reset(num_players=4, seed=42)
    gs = env.state.game_state
    assert gs["current_round"] == 1
    assert gs["talk_messages"] == []
    assert gs["talk_actions_by_player"] == {0: 0, 1: 0, 2: 0, 3: 0}


def test_snapshot_restore_replays_secret_choice():
    env = _fresh()
    before = env.snapshot()
    env.step("Choose X")
    expected = env.snapshot()
    env.restore(before)
    env.step("Choose X")
    assert env.state.game_state == expected["state"].game_state
    assert env.state.current_player_id == expected["state"].current_player_id


def test_talk_phase_ends_at_exact_global_action_limit():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    for index in range(40):
        env.step(f"Broadcast: message {index}")
    gs = env.state.game_state
    assert gs["talk_round"] == 40
    assert gs["talk_actions_by_player"] == {0: 10, 1: 10, 2: 10, 3: 10}
    assert gs["current_phase"] == "act"
    assert env.state.current_player_id == 0


@pytest.mark.parametrize("action", ["Whisper 0: self", "Whisper 4: missing"])
def test_whisper_target_must_be_another_existing_player(action):
    env = _fresh()
    _advance_to_first_talk_phase(env)
    before = list(env.state.game_state["talk_messages"])
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["talk_messages"] == before
    assert env.state.current_player_id == 0


@pytest.mark.parametrize("error_allowance", [-1, True])
def test_invalid_error_allowance_is_rejected(error_allowance):
    with pytest.raises(ValueError, match="error_allowance"):
        WinAsMuchAsYouCanEnv(error_allowance=error_allowance)
