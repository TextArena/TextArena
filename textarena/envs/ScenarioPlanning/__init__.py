from textarena.envs.registration import register

register(
    id="ScenarioPlanning-v1",
    entry_point="textarena.envs.ScenarioPlanning.env:ScenarioPlanningEnv",
    jury_size=11,
)
