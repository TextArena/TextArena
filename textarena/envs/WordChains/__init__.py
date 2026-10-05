from textarena.envs.registration import register

register(id="WordChains-v1", entry_point="textarena.envs.WordChains.env:WordChainsEnv")
