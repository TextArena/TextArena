from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Surround-v1",
    entry_point="textarena.envs.Surround.env:SurroundEnv",
    width=5, height=5, max_turns=40,
)
