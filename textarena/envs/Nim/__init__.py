from textarena.envs.registration import register_with_versions

register_with_versions(id="Nim-v0", entry_point="textarena.envs.Nim.env:NimEnv", piles=[3, 4, 5])
