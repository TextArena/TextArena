from textarena.envs.registration import register_with_versions

register_with_versions(id="NewRecruit-v0", entry_point="textarena.envs.NewRecruit.env:NewRecruitEnv")
