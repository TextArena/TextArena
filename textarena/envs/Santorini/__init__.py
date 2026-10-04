from textarena.envs.registration import register

register(
    id="SantoriniBaseFixed-v1",
    entry_point="textarena.envs.Santorini.env:SantoriniBaseFixedWorkerEnv",
)
