from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Breakthrough-v0",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=True,
)
register_with_versions(
    id="Breakthrough-v0-blind",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=False,
)
