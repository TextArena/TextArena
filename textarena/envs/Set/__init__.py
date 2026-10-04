from textarena.envs.registration import register_with_versions

register_with_versions(id="Set-v0", entry_point="textarena.envs.Set.env:SetEnv")
