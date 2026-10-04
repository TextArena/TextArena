from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ScenarioPlanning-v0",
    entry_point="textarena.envs.ScenarioPlanning.env:ScenarioPlanningEnv",
    jury_size=11,
)
