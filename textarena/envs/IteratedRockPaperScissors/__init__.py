from textarena.envs.registration import register

register(
    id="IteratedRockPaperScissors-v1",
    entry_point="textarena.envs.IteratedRockPaperScissors.env:IteratedRockPaperScissorsEnv",
    num_rounds=9,
)
