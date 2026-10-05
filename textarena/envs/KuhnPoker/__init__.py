from textarena.envs.registration import register

register(id="KuhnPoker-v1", entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", max_rounds=3)
