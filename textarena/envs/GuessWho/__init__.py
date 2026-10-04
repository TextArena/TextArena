from textarena.envs.registration import register

register(id="GuessWho-v1", entry_point="textarena.envs.GuessWho.env:GuessWhoEnv", max_turns=20)
