from textarena.envs.registration import register

register(id="SpellingBee-v1", entry_point="textarena.envs.SpellingBee.env:SpellingBeeEnv", num_letters=7)
