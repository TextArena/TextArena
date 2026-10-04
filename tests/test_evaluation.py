import pytest

import textarena as ta
from textarena.envs.registration import ENV_REGISTRY, register


class _HigherDigitEnv(ta.GameEnv):
    """Both players name a digit; the higher digit wins."""
    min_players = max_players = 2
    action_pattern = r"^(\d)$"

    def setup(self):
        return {"digits": {}}

    def prompt(self, player_id):
        return "Name a digit."

    def apply(self, player_id, move):
        self.game_state["digits"][player_id] = int(move.group(1))
        if len(self.game_state["digits"]) < 2:
            return None
        first, second = self.game_state["digits"][0], self.game_state["digits"][1]
        if first == second:
            return self.draw(reason="Equal digits.")
        return self.winner(0 if first > second else 1, reason="The higher digit wins.")


class _DigitScoreEnv(ta.GameEnv):
    """A single player names a digit and scores it divided by 9."""
    min_players = max_players = 1

    def setup(self):
        return {}

    def prompt(self, player_id):
        return "Name a digit."

    def apply(self, player_id, action):
        return self.outcome({0: int(action) / 9}, reason="Scored.")


@pytest.fixture(autouse=True)
def toy_games():
    register("__HigherDigit-v1", _HigherDigitEnv)
    register("__DigitScore-v1", _DigitScoreEnv)
    yield
    for env_id in ("__HigherDigit-v1", "__DigitScore-v1"):
        ENV_REGISTRY.pop(env_id, None)
        ENV_REGISTRY.pop(f"{env_id}-mdp", None)


def high(observation):
    return "9"


def low(observation):
    return "1"


def _by_agent(evaluation):
    return {row["agent"]: row for row in evaluation.summary()}


def test_every_agent_plays_every_seat_on_the_same_seeds():
    evaluation = ta.evaluate({"high": high, "low": low}, "__HigherDigit-v1", episodes=3, seed=10)
    played = sorted((game.seed, game.seats) for game in evaluation.games)
    assert played == sorted((seed, seats) for seed in (10, 11, 12) for seats in (("high", "low"), ("low", "high")))
    summary = _by_agent(evaluation)
    assert summary["high"]["games"] == 6 and summary["high"]["win_rate"] == 1 and summary["high"]["mean_reward"] == 1
    assert summary["low"]["win_rate"] == 0 and summary["low"]["mean_reward"] == -1


def test_single_player_games_score_each_agent_on_its_own():
    evaluation = ta.evaluate({"high": high, "low": low}, "__DigitScore-v1", episodes=2)
    assert len(evaluation.games) == 4
    summary = _by_agent(evaluation)
    assert summary["high"]["mean_reward"] == 1 and summary["high"]["win_rate"] is None
    assert summary["low"]["mean_reward"] == pytest.approx(1 / 9)


def test_a_failing_agent_is_recorded_instead_of_stopping_the_evaluation():
    def unavailable(observation):
        raise ConnectionError("model unavailable")

    evaluation = ta.evaluate({"high": high, "unavailable": unavailable}, "__HigherDigit-v1", episodes=2)
    assert all(game.error == "ConnectionError: model unavailable" for game in evaluation.games)
    assert {(row["games"], row["errors"]) for row in evaluation.summary()} == {(0, 4)}


def test_parallel_runs_match_serial_runs():
    agents, env_ids = {"high": high, "low": low}, ["__HigherDigit-v1", "__DigitScore-v1"]
    assert ta.evaluate(agents, env_ids, episodes=3, workers=4).to_rows() == ta.evaluate(agents, env_ids, episodes=3).to_rows()


def test_each_game_can_be_replayed_from_its_record():
    game = ta.evaluate({"high": high, "low": low}, "__HigherDigit-v1", episodes=1).games[0]
    assert ta.replay(game.record, game=_HigherDigitEnv).state.rewards == game.rewards
