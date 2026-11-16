from textarena.envs.LightsOut.env import LightsOutEnv

SOLVED_SCRAMBLE_SEED = 10067


def test_reset_never_starts_solved():
    env = LightsOutEnv()
    env.reset(num_players=1, seed=SOLVED_SCRAMBLE_SEED)
    assert not env._is_solved(env.state.game_state["grid"])
