from textarena.envs.registration import register_with_versions

register_with_versions(id="LightsOut-v0", entry_point="textarena.envs.LightsOut.env:LightsOutEnv", size=5, max_turns=20)
