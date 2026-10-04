from textarena.envs.registration import register_with_versions

register_with_versions(
    id="FrozenLake-v1",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=4, num_holes=3, randomize_start_goal=False,
)
register_with_versions(
    id="FrozenLake-v1-random",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=4, num_holes=3, randomize_start_goal=True,
)
register_with_versions(
    id="FrozenLake-v1-hardcore",
    entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv",
    size=5, num_holes=6, randomize_start_goal=False,
)
