from textarena.envs.registration import register_with_versions

register_with_versions(id="Checkers-v0", entry_point="textarena.envs.Checkers.env:CheckersEnv", max_turns=100)
