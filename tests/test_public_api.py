import random

import pytest

import textarena as ta
from textarena.envs.registration import ENV_REGISTRY, register
from textarena.wrappers.renderers import SimpleRenderWrapper


def test_extract_action_uses_last_non_empty_tag():
    response = "Reasoning <action>1</action> more thought <ACTION> 4 </ACTION>"
    assert ta.extract_action(response) == "4"


def test_extract_action_falls_back_to_raw_text():
    assert ta.extract_action("  roll  ") == "roll"


def test_registry_has_only_default_and_mdp_pairs():
    for env_id in ENV_REGISTRY:
        assert not env_id.endswith(("-raw", "-train"))
        if env_id.endswith("-mdp"):
            assert env_id[:-4] in ENV_REGISTRY
        else:
            assert f"{env_id}-mdp" in ENV_REGISTRY


def test_equivalent_registration_is_idempotent_but_conflicts_fail():
    env_id = "__test-idempotent-registration__"

    def factory():
        return object()

    try:
        register(env_id, factory, marker=1)
        register(env_id, factory, marker=1)
        with pytest.raises(ValueError, match="different specification"):
            register(env_id, factory, marker=2)
    finally:
        ENV_REGISTRY.pop(env_id, None)


def test_default_observation_contains_only_unseen_messages():
    env = ta.make("TicTacToe-v0")
    env.reset(num_players=2, seed=1)
    player_id, first = env.get_observation()
    assert player_id == 0
    assert "You are Player 0" in first
    _, second = env.get_observation()
    assert second == ""


def test_shared_renderer_excludes_private_events():
    class State:
        events = [
            (0, "public", ta.ObservationType.PLAYER_ACTION, -1),
            (1, "secret", ta.ObservationType.PLAYER_ACTION, 0),
        ]

    assert SimpleRenderWrapper._public_logs(State()) == [(0, "public")]


def test_mdp_observation_accumulates_history_and_reset_clears_it():
    env = ta.make("TicTacToe-v0-mdp")
    env.reset(num_players=2, seed=1)
    env.get_observation()
    env.step("0")
    env.get_observation()
    env.step("4")
    player_id, observation = env.get_observation()
    assert player_id == 0
    assert "You are Player 0" in observation
    assert "placed their symbol" in observation

    env.reset(num_players=2, seed=1)
    _, reset_observation = env.get_observation()
    assert reset_observation.count("You are Player 0") == 1


def test_mdp_snapshot_restores_wrapper_history():
    env = ta.make("TicTacToe-v0-mdp")
    env.reset(num_players=2, seed=1)
    env.get_observation()
    snapshot = env.snapshot()

    env.step("0")
    env.get_observation()
    env.restore(snapshot)
    player_id, observation = env.get_observation()

    assert player_id == 0
    assert "placed their symbol" not in observation
    assert "'0'" in observation


def test_terminal_action_is_counted_and_final_board_is_rendered():
    env = ta.make("TicTacToe-v0")
    env.reset(num_players=2, seed=1)
    for move in ("0", "3", "1", "4"):
        done, _ = env.step(move)
        assert not done

    done, _ = env.step("2")

    assert done
    assert env.state.turn == 5
    assert env.state.game_info[0]["turn_count"] == 3
    final_boards = [
        message
        for _, message, observation_type, _ in env.state.events
        if observation_type == ta.ObservationType.GAME_BOARD
    ]
    assert "'2'" not in final_boards[-1]


def test_oversized_actions_are_rejected_before_event_logging():
    env = ta.make("TicTacToe-v0")
    env.reset(num_players=2, seed=1)
    oversized = "x" * (env.max_action_chars + 1)

    done, _ = env.step(oversized)

    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert all(message != oversized for _, message, _, _ in env.state.events)


def test_reset_does_not_mutate_global_random_state():
    random.seed(99)
    expected = random.Random(99).random()
    env = ta.make("PigDice-v0")
    env.reset(num_players=2, seed=42)
    assert random.random() == expected


def test_seeded_environments_have_independent_rngs():
    first = ta.make("PigDice-v0")
    second = ta.make("PigDice-v0")
    first.reset(num_players=2, seed=42)
    second.reset(num_players=2, seed=42)
    first.step("roll")
    second.step("roll")
    assert first.state.game_state["turn_total"] == second.state.game_state["turn_total"] == 6


def test_snapshot_restores_environment_attributes_and_aliases():
    external_resource = object()

    class SnapshotEnv(ta.GameEnv):
        min_players = max_players = 1
        snapshot_excluded_attributes = ("external_resource",)

        def setup(self):
            self.deck = [1, 2, 3]
            return {"deck": self.deck}

        def prompt(self, player_id):
            return "Choose."

        def apply(self, player_id, move):
            return None

    env = SnapshotEnv()
    env.external_resource = external_resource
    env.reset(num_players=1, seed=42)
    snapshot = env.snapshot()
    expected_random = env.rng.random()
    env.deck.pop()

    env.restore(snapshot)

    assert env.deck == [1, 2, 3]
    assert env.deck is env.game_state["deck"]
    assert env.rng.random() == expected_random
    assert env.external_resource is external_resource
