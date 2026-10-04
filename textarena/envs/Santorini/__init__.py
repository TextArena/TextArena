from textarena.envs.registration import register_with_versions

register_with_versions(
    id="SantoriniBaseFixed-v0",
    entry_point="textarena.envs.Santorini.env:SantoriniBaseFixedWorkerEnv",
)
