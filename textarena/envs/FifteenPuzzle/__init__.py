from textarena.envs.registration import register_with_versions

register_with_versions(
    id="FifteenPuzzle-v1",
    entry_point="textarena.envs.FifteenPuzzle.env:FifteenPuzzleEnv",
    max_turns=200,
)
