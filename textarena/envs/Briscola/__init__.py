from textarena.envs.registration import register_with_versions

register_with_versions(id="Briscola-v0", entry_point="textarena.envs.Briscola.env:BriscolaEnv")
