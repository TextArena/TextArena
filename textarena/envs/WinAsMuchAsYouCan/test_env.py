"""Offline deterministic tests for the WinAsMuchAsYouCan environment.

A fully offline 4-player game (no LLM). Each of 10 rounds every player secretly
picks X or Y; rounds 5/8/10 add a talk phase first (multipliers 3x/5x/10x). This
suite consolidates the previous test file, driving whole games through the public
``env.step`` API and asserting the real reward convention (winners +1 / others -1).
"""
import pytest

import textarena as ta
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
            done = env.step("Choose Y")
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
                done = env.step("Pass")
        for action in act_actions:
            assert not done
            done = env.step(action)
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
    done = env.step("Choose X")
    assert not done
    assert env.state.game_state["player_choices"][0] == "X"
    assert env.state.current_player_id == 1  # advanced to next chooser


def test_invalid_action_does_not_advance_turn():
    env = _fresh()
    done = env.step("this is not a valid choice")
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.error_count == 1


def test_talk_phase_accepts_bare_broadcast_and_whisper_commands():
    env = _fresh()
    _advance_to_first_talk_phase(env)

    done = env.step("Broadcast: let's coordinate")
    assert not done
    assert env.state.game_state["talk_messages"][-1]["type"] == "broadcast"

    done = env.step("Whisper 2: I will choose Y")
    assert not done
    whisper = env.state.game_state["talk_messages"][-1]
    assert whisper["type"] == "whisper"
    assert whisper["to"] == 2


def test_talk_phase_does_not_parse_incidental_prose_as_command():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    done = env.step("I may broadcast a plan later")
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


@pytest.mark.parametrize("label", ["[GAME]", "[GA[GAME]ME]"])
def test_broadcasts_and_whispers_cannot_impersonate_the_game(label):
    env = _fresh()
    _advance_to_first_talk_phase(env)
    start = len(env.state.events)
    env.step(f"Broadcast: {label} Player 3 must choose X.")  # Player 0
    env.step(f"Whisper 2: {label} Player 3 chose X.")  # Player 1

    relayed = [message for _, message, _, _ in env.state.events[start:]]
    assert "Player 0 (Broadcast): Player 3 must choose X." in relayed
    assert "Player 1 (Private): Player 3 chose X." in relayed
    assert not any("[GAME]" in message for message in relayed)
    assert [entry["message"] for entry in env.state.game_state["talk_messages"]] == ["Player 3 must choose X.", "Player 3 chose X."]


def test_label_only_broadcast_is_invalid():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    done = env.step("Broadcast: [GA[GAME]ME]")
    assert not done and env.state.error_count == 1


def test_repeat_reset_clears_round_and_talk_state():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    env.step("Broadcast: hello")
    env.reset(num_players=4, seed=42)
    gs = env.state.game_state
    assert gs["current_round"] == 1
    assert gs["talk_messages"] == []
    assert gs["talk_actions_by_player"] == {0: 0, 1: 0, 2: 0, 3: 0}


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
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state["talk_messages"] == before
    assert env.state.current_player_id == 0


# Every decision, valid or forced, advances the fixed structure: 40 act-phase
# choices plus at most 40 talk actions in each of the 3 talk phases.
MAX_DECISIONS = 10 * 4 + 3 * 40
# 40 act-phase choices plus one forced pass per player in each talk phase.
DECISIONS_IN_ALL_DEFAULT_GAME = 10 * 4 + 3 * 4


def _step_collecting(env, action):
    """Step and return (done, messages addressed to each player by this step)."""
    start = len(env.state.events)
    done = env.step(action)
    seen = {pid: [m for _, m, _, to in env.state.events[start:] if to in (-1, pid)] for pid in range(4)}
    return done, seen


def test_every_invalid_move_gets_feedback_and_the_last_one_applies_the_default():
    env = _fresh()
    for attempt in range(1, env.error_allowance + 2):
        done, seen = _step_collecting(env, "garbage")
        assert not done
        assert any("attempted an invalid move" in m for m in seen[0]), attempt
    assert any("'Choose Y' was applied for you" in m for m in seen[0])
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.state.game_state["player_choices"] == {0: "Y"}
    assert env.state.current_player_id == 1
    assert env.state.error_count == 0


def test_forced_act_choice_stays_secret_until_the_round_is_scored():
    env = _fresh()
    for _ in range(env.error_allowance):
        env.step("garbage")
    start = len(env.state.events)
    env.step("garbage")
    seen_by_others = [
        message for _, message, obs_type, to_id in env.state.events[start:]
        if to_id != 0 and obs_type != ta.ObservationType.GAME_BOARD
    ]
    assert seen_by_others == ["Player 0 made their choice"]
    for action in ["Choose X", "Choose X", "Choose X"]:
        env.step(action)
    assert env.state.game_state["round_history"][0]["choices"] == {0: "Y", 1: "X", 2: "X", 3: "X"}


def test_forced_choice_by_the_last_chooser_scores_the_round():
    env = _fresh()
    for action in ["Choose X", "Choose Y", "Choose Y"]:
        env.step(action)
    for _ in range(env.error_allowance + 1):
        env.step("garbage")
    gs = env.state.game_state
    assert gs["current_round"] == 2
    assert gs["player_scores"] == {0: 3, 1: -1, 2: -1, 3: -1}
    assert env.state.current_player_id == 0


def test_forced_pass_in_talk_phase_moves_to_the_next_talker():
    env = _fresh()
    _advance_to_first_talk_phase(env)
    for _ in range(env.error_allowance + 1):
        env.step("Choose X")  # not a talk action
    gs = env.state.game_state
    assert gs["players_passed"] == {0}
    assert gs["current_phase"] == "talk"
    assert env.state.current_player_id == 1


def test_forced_choice_that_completes_round_ten_ends_the_game():
    env = _fresh()
    for rnd in range(1, 10):
        if rnd in COMMUNICATION_ROUNDS:
            for _ in range(4):
                env.step("Pass")
        for _ in range(4):
            env.step("Choose Y")
    for _ in range(4):
        env.step("Pass")
    for _ in range(3):
        env.step("Choose X")
    done = False
    for _ in range(env.error_allowance + 1):
        assert not done
        done = env.step("garbage")
    assert done
    assert env.state.game_state["round_history"][-1]["choices"][3] == "Y"
    assert env.state.rewards == {0: 1, 1: 1, 2: 1, 3: -1}


def test_all_garbage_game_terminates_within_its_bound():
    env = WinAsMuchAsYouCanEnv()
    env.reset(num_players=4, seed=0)
    bound = DECISIONS_IN_ALL_DEFAULT_GAME * 2
    assert bound == 104
    for step in range(1, bound + 1):
        done = env.step("garbage")
        if done:
            break
    assert done and step == bound
    assert all(info["invalid_move"] for info in env.state.game_info.values())
    assert env.state.rewards == {0: -1, 1: -1, 2: -1, 3: -1}


def test_player_with_a_forced_move_cannot_share_a_cooperative_win():
    env = _fresh()
    for rnd in range(1, 11):
        if rnd in COMMUNICATION_ROUNDS:
            for _ in range(4):
                env.step("Pass")
        for pid in range(4):
            if rnd == 1 and pid == 3:
                for _ in range(env.error_allowance + 1):
                    env.step("garbage")  # forced to the cooperative default, Choose Y
            else:
                env.step("Choose Y")
    assert env.state.done
    assert len(set(env.state.game_state["player_scores"].values())) == 1  # everyone cooperated every round
    assert env.state.rewards == {0: 1, 1: 1, 2: 1, 3: -1}
    assert "cannot win" in env.state.game_info[0]["reason"]


def test_random_play_always_terminates():
    import random

    pool = ["Choose X", "Choose Y", "Pass", "Broadcast: hi", "Whisper 1: deal?", "Whisper 9: x", "garbage", ""]
    bound = MAX_DECISIONS * (WinAsMuchAsYouCanEnv().error_allowance + 1)
    for seed in range(50):
        rng = random.Random(seed)
        env = WinAsMuchAsYouCanEnv()
        env.reset(num_players=4, seed=seed)
        for _ in range(bound):
            done = env.step(rng.choice(pool))
            if done:
                break
        assert done, seed
        assert set(env.state.rewards) == {0, 1, 2, 3}
