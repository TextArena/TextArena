from textarena.envs.registration import register_with_versions

register_with_versions(
    id="GameOfPureStrategy-v0",
    entry_point="textarena.envs.GameOfPureStrategy.env:GameOfPureStrategyEnv",
)
