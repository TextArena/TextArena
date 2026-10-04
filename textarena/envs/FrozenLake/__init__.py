from textarena.envs.registration import register

register(
    id="FrozenLake-v1",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=4, num_holes=3, randomize_start_goal=False,
)
register(
    id="FrozenLake-v1-random",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=4, num_holes=3, randomize_start_goal=True,
)
register(
    id="FrozenLake-v1-hardcore",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=5, num_holes=6, randomize_start_goal=False,
)
