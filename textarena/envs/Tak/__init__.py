from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Tak-v0",
    entry_point="textarena.envs.Tak.env:TakEnv",
    board_size=4, stones=15, capstones=1, max_turns=100,
)
register_with_versions(
    id="Tak-v0-hard",
    entry_point="textarena.envs.Tak.env:TakEnv",
    board_size=6, stones=30, capstones=1, max_turns=200,
)
