from textarena.envs.registration import register_with_versions

register_with_versions(id="GermanWhist-v0", entry_point="textarena.envs.GermanWhist.env:GermanWhistEnv")
