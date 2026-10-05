from textarena.envs.registration import register

register(
    id="FifteenPuzzle-v1",
    entry_point="textarena.envs.FifteenPuzzle.env:FifteenPuzzleEnv",
    max_turns=200,
)
