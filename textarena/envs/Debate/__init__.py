from textarena.envs.registration import register_with_versions

register_with_versions(id="Debate-v1", entry_point="textarena.envs.Debate.env:DebateEnv", max_turns=6, jury_size=7)
