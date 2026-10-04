from textarena.envs.registration import register_with_versions

register_with_versions(id="SettlersOfCatan-v1", entry_point="textarena.envs.SettlersOfCatan.env:SettlersOfCatanEnv")
