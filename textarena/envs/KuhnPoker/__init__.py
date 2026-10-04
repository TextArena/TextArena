from textarena.envs.registration import register_with_versions

register_with_versions(id="KuhnPoker-v1", entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", max_rounds=3)
