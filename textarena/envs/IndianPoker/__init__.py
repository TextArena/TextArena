from textarena.envs.registration import register_with_versions

register_with_versions(id="IndianPoker-v1", entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", max_rounds=5)
