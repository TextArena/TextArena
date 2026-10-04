from textarena.envs.registration import register_with_versions

register_with_versions(id="Crusade-v1", entry_point="textarena.envs.Crusade.env:CrusadeEnv")
