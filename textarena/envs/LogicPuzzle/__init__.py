from textarena.envs.registration import register_with_versions

register_with_versions(
    id="LogicPuzzle-v0",
    entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv",
    difficulty="easy",
)
register_with_versions(
    id="LogicPuzzle-v0-hard",
    entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv",
    difficulty="hard",
)
