from textarena.envs.registration import register_with_versions

register_with_versions(id="LeTruc-v1", entry_point="textarena.envs.LeTruc.env:LeTrucEnv")
