from textarena.envs.registration import register

register(id="Nim-v1", entry_point="textarena.envs.Nim.env:NimEnv", piles=[3, 4, 5])
