from textarena.envs.registration import register_with_versions

register_with_versions(id="LeducHoldem-v0", entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", max_rounds=5)
