"""Offline deterministic tests for ScenarioPlanning."""
import copy
import json

import pytest
from textarena.envs.ScenarioPlanning.env import ScenarioPlanningEnv
from textarena.utils.jury import OpenRouterJury


class _FakeJury:
    """Deterministic stand-in for OpenRouterJury."""

    _votes = {"Player 0": 3, "Player 1": 2}

    def __init__(self, jury_size=5, options=None):
        self.jury_size = jury_size
        self.options = options

    def evaluate(self, context):
        return dict(self._votes)


def _fresh(votes=None):
    if votes is not None:
        jury = type("J", (_FakeJury,), {"_votes": votes})
    else:
        jury = _FakeJury
    env = ScenarioPlanningEnv(jury_class=jury)
    env.reset(num_players=2, seed=42)
    return env


def test_reset_initial_state():
    env = _fresh()
    gs = env.state.game_state
    assert gs["strategies"] == {0: None, 1: None}
    assert isinstance(gs["scenario"], str) and gs["scenario"]
    assert env.state.current_player_id == 0


def test_first_strategy_does_not_end_game():
    env = _fresh()
    done, _ = env.step("Build a shelter and ration food.")
    assert not done
    assert env.state.game_state["strategies"][0] is not None
    assert env.state.current_player_id == 1


def test_player0_wins_when_jury_favors_them():
    env = _fresh(votes={"Player 0": 4, "Player 1": 1})
    env.step("Strategy from player 0")
    done, _ = env.step("Strategy from player 1")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert env.state.turn == 2
    assert env.state.game_info[0]["turn_count"] == 1
    assert env.state.game_info[1]["turn_count"] == 1


def test_player1_wins_when_jury_favors_them():
    env = _fresh(votes={"Player 0": 1, "Player 1": 4})
    env.step("Strategy from player 0")
    done, _ = env.step("Strategy from player 1")
    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_tie_is_a_draw():
    env = _fresh(votes={"Player 0": 2, "Player 1": 2})
    env.step("Strategy from player 0")
    done, _ = env.step("Strategy from player 1")
    assert done
    assert env.state.rewards == {0: 0, 1: 0}


def test_empty_strategy_is_invalid_and_atomic():
    env = _fresh()
    before = copy.deepcopy(env.game_state)
    done, _ = env.step(" \n ")
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert env.game_state == before


def test_strategy_is_private_from_the_other_player():
    env = _fresh()
    env.get_observation()  # consume player 0's prompt
    strategy = "Private strategy from player zero"
    env.step(strategy)
    pid, observations = env.get_observation()
    assert pid == 1
    assert all(strategy not in message for _, message, _ in observations)


class _FailingJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        raise RuntimeError("service unavailable")


class _MalformedJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        return {"Player 0": float("nan"), "Player 1": 0}


class _NoVotesJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        return {"Player 0": 0, "Player 1": 0}


class _ExcessVotesJury:
    def __init__(self, **kwargs):
        pass

    def evaluate(self, context):
        return {"Player 0": 1e308, "Player 1": 1e308}


@pytest.mark.parametrize(
    "jury_class",
    [_FailingJury, _MalformedJury, _NoVotesJury, _ExcessVotesJury],
)
def test_jury_failure_does_not_commit_second_strategy(jury_class):
    env = ScenarioPlanningEnv(jury_class=jury_class)
    env.reset(num_players=2, seed=42)
    env.step("First strategy")
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("Second strategy")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.turn == 1
    assert env.state.error_count == 0
    assert env.game_state == before
    assert env.judge is None


def test_jury_error_cannot_leak_the_other_players_strategy():
    private_strategy = "PLAYER ZERO PRIVATE STRATEGY"

    class LeakingJury:
        def __init__(self, **kwargs):
            pass

        def evaluate(self, context):
            raise RuntimeError(context)

    env = ScenarioPlanningEnv(jury_class=LeakingJury)
    env.reset(num_players=2, seed=42)
    env.get_observation()
    env.step(private_strategy)
    env.get_observation()
    done, _ = env.step("Player one's strategy")
    assert not done
    _, observations = env.get_observation()
    assert private_strategy not in "\n".join(message for _, message, _ in observations)


def test_oversized_strategy_is_rejected_before_jury_construction():
    constructions = []

    class Jury(_FakeJury):
        def __init__(self, **kwargs):
            constructions.append(kwargs)
            super().__init__()

    env = ScenarioPlanningEnv(jury_class=Jury)
    env.reset(num_players=2, seed=42)
    before = copy.deepcopy(env.game_state)
    done, _ = env.step("x" * (env.max_strategy_chars + 1))
    assert not done
    assert env.game_state == before
    assert constructions == []


def test_seeded_rng_is_forwarded_to_compatible_jury():
    samples = []

    class Jury:
        def __init__(self, *, rng, **kwargs):
            samples.append(rng.random())

        def evaluate(self, context):
            return {"Player 0": 1, "Player 1": 1}

    for _ in range(2):
        env = ScenarioPlanningEnv(jury_class=Jury)
        env.reset(num_players=2, seed=7)
        env.step("First")
        env.step("Second")
    assert samples[0] == samples[1]


def test_jury_is_lazy_and_recreated_after_reset():
    constructions = []

    class TrackingJury(_FakeJury):
        _votes = {"Player 0": 2, "Player 1": 1}

        def __init__(self, **kwargs):
            constructions.append(kwargs)
            super().__init__(**kwargs)

    env = ScenarioPlanningEnv(jury_class=TrackingJury, jury_size=3)
    env.reset(num_players=2, seed=5)
    assert constructions == []
    env.step("First")
    env.step("Second")
    assert len(constructions) == 1
    env.reset(num_players=2, seed=5)
    assert env.judge is None
    env.step("First")
    env.step("Second")
    assert len(constructions) == 2


def test_reset_snapshot_seed_and_renderer_are_fresh_and_pure():
    env = _fresh()
    scenario = env.game_state["scenario"]
    env.step("First strategy")
    snapshot = env.snapshot()
    assert "judge" not in snapshot["attributes"]
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert scenario[:30] in board
    assert env.game_state == before
    env.step("Second strategy")
    env.restore(snapshot)
    assert env.game_state == before
    env.reset(num_players=2, seed=42)
    assert env.game_state["scenario"] == scenario
    assert env.game_state["strategies"] == {0: None, 1: None}


def test_invalid_scenario_data_has_clear_error(tmp_path):
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps({"scenarios": [""]}), encoding="utf-8")
    with pytest.raises(ValueError, match="non-empty list"):
        ScenarioPlanningEnv(jury_class=_FakeJury, scenarios_path=str(path))


def test_bundled_scenarios_are_unique():
    env = ScenarioPlanningEnv(jury_class=_FakeJury)
    assert len(env.scenarios) == len({scenario.casefold() for scenario in env.scenarios})


def test_default_jury_class_resolves_without_building_a_jury():
    env = ScenarioPlanningEnv()
    assert env._jury_class is OpenRouterJury
    env.reset(num_players=2, seed=42)
    assert env.judge is None


def test_configuration_and_player_bounds_are_validated():
    with pytest.raises(ValueError):
        ScenarioPlanningEnv(jury_class=_FakeJury, jury_size=0)
    with pytest.raises(ValueError):
        ScenarioPlanningEnv(jury_class=_FakeJury, jury_size=101)
    env = ScenarioPlanningEnv(jury_class=_FakeJury)
    with pytest.raises(ValueError):
        env.reset(num_players=1)
    with pytest.raises(ValueError):
        env.reset(num_players=3)


def test_prompt_explains_single_hidden_submission_and_jury_vote():
    env = ScenarioPlanningEnv(jury_class=_FakeJury, jury_size=11)
    env.reset(num_players=2, seed=42)
    prompt = env.prompt(1)
    assert "exactly one strategy" in prompt
    assert "the other player never sees it" in prompt
    assert "a panel of 11 AI judges" in prompt
    assert "equal votes are a draw" in prompt
    assert f"at most {env.max_strategy_chars} characters" in prompt
