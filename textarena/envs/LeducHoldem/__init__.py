from textarena.envs.registration import register

register(id="LeducHoldem-v1", entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", max_rounds=5)
