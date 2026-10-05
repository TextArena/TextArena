from textarena.envs.registration import register

register(
    id="Tak-v1",
    entry_point="textarena.envs.Tak.env:TakEnv",
    board_size=4, stones=15, capstones=1, max_turns=100,
)
register(
    id="Tak-v1-hard",
    entry_point="textarena.envs.Tak.env:TakEnv",
    board_size=6, stones=30, capstones=1, max_turns=200,
)
