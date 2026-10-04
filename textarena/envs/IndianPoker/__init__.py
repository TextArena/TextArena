from textarena.envs.registration import register

register(id="IndianPoker-v1", entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", max_rounds=5)
