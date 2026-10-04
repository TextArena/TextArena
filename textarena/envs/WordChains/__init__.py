from textarena.envs.registration import register_with_versions

register_with_versions(id="WordChains-v0", entry_point="textarena.envs.WordChains.env:WordChainsEnv")
