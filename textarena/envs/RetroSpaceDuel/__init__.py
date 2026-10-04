from textarena.envs.registration import register_with_versions

register_with_versions(
    id="RetroSpaceDuel-v1",
    entry_point="textarena.envs.RetroSpaceDuel.env:RetroSpaceDuelEnv",
    max_turns=100,
)
