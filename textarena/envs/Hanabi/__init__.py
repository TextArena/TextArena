from textarena.envs.registration import register_with_versions

register_with_versions(id="Hanabi-v1", entry_point="textarena.envs.Hanabi.env:HanabiEnv")
