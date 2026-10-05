from textarena.envs.registration import register

register(
    id="Breakthrough-v1",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=True,
)
register(
    id="Breakthrough-v1-blind",
    entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv",
    board_size=8, is_open=False,
)
