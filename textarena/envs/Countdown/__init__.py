from textarena.envs.registration import register

register(
    id="Countdown-v1",
    entry_point="textarena.envs.Countdown.env:CountdownEnv",
    numbers=[100, 75, 6, 4, 3, 2], target=532,
)
