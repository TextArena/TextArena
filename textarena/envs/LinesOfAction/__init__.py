from textarena.envs.registration import register_with_versions

register_with_versions(id="LinesOfAction-v1", entry_point="textarena.envs.LinesOfAction.env:LinesOfActionEnv")
