from textarena.envs.registration import register

register(
    id="LogicPuzzle-v1",
    entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv",
    difficulty="easy",
)
register(
    id="LogicPuzzle-v1-hard",
    entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv",
    difficulty="hard",
)
