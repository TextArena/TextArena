from textarena.envs.registration import register_with_versions

register_with_versions(id="Chopsticks-v0", entry_point="textarena.envs.Chopsticks.env:ChopsticksEnv", max_turns=40)
