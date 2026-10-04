from textarena.envs.registration import register_with_versions

register_with_versions(
    id="IteratedRockPaperScissors-v1",
    entry_point="textarena.envs.IteratedRockPaperScissors.env:IteratedRockPaperScissorsEnv",
    num_rounds=9,
)
