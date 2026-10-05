from textarena.envs.registration import register

register(
    id="MemoryGame-v1",
    entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv",
    grid_size=4, max_turns=30,
)
register(
    id="MemoryGame-v1-hard",
    entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv",
    grid_size=8, max_turns=80,
)
