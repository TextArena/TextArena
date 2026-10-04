from textarena.envs.registration import register_with_versions

register_with_versions(id="Stratego-v1", entry_point="textarena.envs.Stratego.env:StrategoEnv")
