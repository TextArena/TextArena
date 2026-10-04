from textarena.envs.registration import register_with_versions

register_with_versions(id="GuessWho-v0", entry_point="textarena.envs.GuessWho.env:GuessWhoEnv", max_turns=20)
