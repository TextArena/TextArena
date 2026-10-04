from textarena.envs.registration import register_with_versions

register_with_versions(
    id="MemoryGame-v0",
    entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv",
    grid_size=4, max_turns=30,
)
register_with_versions(
    id="MemoryGame-v0-hard",
    entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv",
    grid_size=8, max_turns=80,
)
