"""Deterministic, network-free game-logic tests for Debate."""
import copy
import json

import pytest
from textarena.envs.Debate.env import DebateEnv


class _AffirmativeJury:
    """Fake jury: pre-debate favours Negative, post-debate swings to Affirmative."""

    def __init__(self, jury_size=5, options=None):
        self.calls = 0

    def evaluate(self, context):
        self.calls += 1
        # First call is the pre-debate vote, later calls are post-debate.
        if self.calls == 1:
            return {"Affirmative": 2, "Negative": 3}
        return {"Affirmative": 5, "Negative": 0}


class _TieJury:
    def __init__(self, jury_size=5, options=None):
        pass

    def evaluate(self, context):
        return {"Affirmative": 1, "Negative": 1}  # identical gains -> tie


class _NegativeJury:
    def __init__(self, jury_size=5, options=None):
        self.calls = 0

    def evaluate(self, context):
        self.calls += 1
        if self.calls == 1:
            return {"Affirmative": 3, "Negative": 2}
        return {"Affirmative": 0, "Negative": 5}


def _fresh(jury_class):
    env = DebateEnv(jury_class=jury_class)
    env.reset(num_players=2, seed=42)
    return env


def test_affirmative_side_wins_when_it_gains_support():
    env = _fresh(_AffirmativeJury)
    aff_pid = next(pid for pid, side in env.state.game_state["sides"].items() if side == "Affirmative")
    done = False
    for _ in range(env.max_turns):
        done, _ = env.step("Here is my argument.")
    assert done and env.state.rewards == {aff_pid: 1, 1 - aff_pid: -1}
    assert env.state.turn == env.max_turns
    assert sum(info["turn_count"] for info in env.state.game_info.values()) == env.max_turns


def test_equal_support_gain_is_a_draw():
    env = _fresh(_TieJury)
    done = False
    for _ in range(env.max_turns):
        done, _ = env.step("Here is my argument.")
    assert done and env.state.rewards == {0: 0, 1: 0}


def test_negative_side_wins_when_it_gains_support():
    env = _fresh(_NegativeJury)
    negative_pid = next(
        pid for pid, side in env.game_state["sides"].items() if side == "Negative"
    )
    for _ in range(env.max_turns):
        done, _ = env.step("Argument.")
    assert done
    assert env.state.rewards == {negative_pid: 1, 1 - negative_pid: -1}


def test_pre_debate_vote_is_lazy_and_recorded_on_first_argument():
    env = _fresh(_AffirmativeJury)
    assert env.state.game_state["pre_vote_recorded"] is False
    assert env.jury is None
    env.step("First argument.")
    pre = env.state.game_state["votes"]["pre-debate"]
    assert pre == {"Affirmative": 2, "Negative": 3}
    assert env.state.game_state["pre_vote_recorded"] is True


def test_arguments_are_stored_and_turn_rotates():
    env = _fresh(_AffirmativeJury)
    assert env.state.current_player_id == 0
    env.step("First argument from player 0.")
    assert env.state.current_player_id == 1
    assert env.state.game_state["arguments"][0] == ["First argument from player 0."]


def test_empty_argument_is_invalid_without_constructing_jury():
    constructions = []

    class Jury(_TieJury):
        def __init__(self, **kwargs):
            constructions.append(kwargs)

    env = DebateEnv(jury_class=Jury)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(" \n ")
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert env.game_state == before
    assert constructions == []


class _FailingPreJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        raise RuntimeError("offline")


class _FailingPostJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        if "No debate has occurred" in context:
            return {"Affirmative": 1, "Negative": 1}
        raise RuntimeError("offline")


def test_pre_vote_failure_is_retryable_and_atomic():
    env = DebateEnv(jury_class=_FailingPreJury)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("First argument")
    assert not done
    assert env.state.turn == 0
    assert env.state.error_count == 0
    assert env.game_state == before
    assert env.jury is None


def test_post_vote_failure_does_not_commit_final_argument():
    env = DebateEnv(max_turns=2, jury_class=_FailingPostJury)
    env.reset(num_players=2, seed=42)
    env.step("First argument")
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Final argument")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.turn == 1
    assert env.state.error_count == 0
    assert env.game_state == before


def test_snapshot_replays_stateful_jury_outcome():
    class Jury:
        def __init__(self, **kwargs):
            self.calls = 0

        def evaluate(self, context):
            self.calls += 1
            if self.calls == 1:
                return {"Affirmative": 1, "Negative": 1}
            if self.calls == 2:
                return {"Affirmative": 2, "Negative": 0}
            return {"Affirmative": 0, "Negative": 2}

    env = DebateEnv(max_turns=2, jury_class=Jury)
    env.reset(num_players=2, seed=7)
    env.step("First")
    snapshot = env.snapshot()
    assert "jury" not in snapshot["attributes"]
    env.step("Final")
    expected = copy.deepcopy(env.state.rewards)
    env.restore(snapshot)
    env.step("Final")
    assert env.state.rewards == expected


def test_oversized_argument_is_rejected_before_jury_construction():
    constructions = []

    class Jury(_TieJury):
        def __init__(self, **kwargs):
            constructions.append(kwargs)

    env = DebateEnv(jury_class=Jury)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("x" * (env.max_argument_chars + 1))
    assert not done
    assert env.game_state == before
    assert constructions == []


def test_seeded_rng_is_forwarded_to_compatible_jury():
    samples = []

    class Jury:
        def __init__(self, *, rng, **kwargs):
            samples.append(rng.random())

        def evaluate(self, context):
            return {"Affirmative": 1, "Negative": 1}

    for _ in range(2):
        env = DebateEnv(max_turns=2, jury_class=Jury)
        env.reset(num_players=2, seed=9)
        env.step("First")
    assert samples[0] == samples[1]


def test_malformed_votes_are_rejected_without_argument_mutation():
    for votes in (
        {"Affirmative": float("inf"), "Negative": 0},
        {"Affirmative": 0, "Negative": 0},
        {"Affirmative": 1e308, "Negative": 1e308},
    ):
        class Jury:
            def __init__(self, **kwargs):
                pass

            def evaluate(self, context):
                return votes

        env = DebateEnv(jury_class=Jury)
        env.reset(num_players=2, seed=42)
        before = copy.deepcopy(env.game_state)
        env.step("First argument")
        assert env.game_state == before
        assert env.state.error_count == 0


def test_transcript_is_chronological_and_actions_are_public():
    contexts = []

    class Jury:
        def __init__(self, **kwargs):
            pass

        def evaluate(self, context):
            contexts.append(context)
            return {"Affirmative": 1, "Negative": 1}

    env = DebateEnv(max_turns=2, jury_class=Jury)
    env.reset(num_players=2, seed=42)
    env.get_observation()
    env.step("Argument zero")
    _, observations = env.get_observation()
    assert any("Argument zero" in message for _, message, _ in observations)
    env.step("Argument one")
    transcript = contexts[-1]
    assert transcript.index("Argument zero") < transcript.index("Argument one")


def test_reset_snapshot_seed_and_renderer_are_fresh_and_pure():
    env = _fresh(_TieJury)
    topic_and_sides = (env.game_state["topic"], copy.deepcopy(env.game_state["sides"]))
    pending = env.get_board_str()
    assert "Pending" in pending
    env.step("First argument")
    snapshot = env.snapshot()
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert "Pre-debate Votes" in board
    for _ in range(env.max_turns - 1):
        env.step("More argument")
    env.restore(snapshot)
    assert env.game_state == before
    env.reset(num_players=2, seed=42)
    assert (env.game_state["topic"], env.game_state["sides"]) == topic_and_sides
    assert env.game_state["arguments"] == {0: [], 1: []}
    assert env.jury is None


def test_invalid_topic_data_has_clear_error(tmp_path):
    path = tmp_path / "topics.json"
    path.write_text(json.dumps({"topics": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty list"):
        DebateEnv(jury_class=_TieJury, topics_path=str(path))


def test_bundled_topics_are_unique():
    env = DebateEnv(jury_class=_TieJury)
    assert len(env.topics) == len({topic.casefold() for topic in env.topics})


@pytest.mark.parametrize("max_turns", [0, 1, 3, True])
def test_invalid_turn_count_is_rejected(max_turns):
    with pytest.raises(ValueError):
        DebateEnv(max_turns=max_turns, jury_class=_TieJury)


def test_jury_size_and_player_bounds_are_validated():
    with pytest.raises(ValueError):
        DebateEnv(jury_class=_TieJury, jury_size=0)
    with pytest.raises(ValueError):
        DebateEnv(jury_class=_TieJury, jury_size=101)
    env = DebateEnv(jury_class=_TieJury)
    with pytest.raises(AssertionError):
        env.reset(num_players=1)
    with pytest.raises(AssertionError):
        env.reset(num_players=3)
