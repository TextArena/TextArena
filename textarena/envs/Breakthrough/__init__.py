from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Breakthrough-v1",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=True,
)
register_with_versions(
    id="Breakthrough-v1-blind",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=False,
)
