from textarena.envs.registration import register_with_versions

register_with_versions(id="SpellingBee-v0", entry_point="textarena.envs.SpellingBee.env:SpellingBeeEnv", num_letters=7)
