from textarena.envs.registration import register

register(
    id="RetroSpaceDuel-v1",
    entry_point="textarena.envs.RetroSpaceDuel.env:RetroSpaceDuelEnv",
    max_turns=100,
)
