from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Countdown-v0",
    entry_point="textarena.envs.Countdown.env:CountdownEnv",
    numbers=[100, 75, 6, 4, 3, 2], target=532,
)
