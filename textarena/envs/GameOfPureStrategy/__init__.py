from textarena.envs.registration import register

register(
    id="GameOfPureStrategy-v1",
    entry_point="textarena.envs.GameOfPureStrategy.env:GameOfPureStrategyEnv",
)
