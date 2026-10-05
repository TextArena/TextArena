from textarena.envs.registration import register

register(
    id="IteratedTwoThirdsAverage-v1",
    entry_point="textarena.envs.IteratedTwoThirdsAverage.env:IteratedTwoThirdsAverageEnv",
    num_rounds=10, min_guess=0.0, max_guess=100.0,
)
