from textarena.envs.registration import register_with_versions

register_with_versions(
    id="DontSayIt-v1",
    entry_point="textarena.envs.DontSayIt.env:DontSayItEnv",
    hardcore=False, max_turns=20,
)
register_with_versions(
    id="DontSayIt-v1-hardcore",
    entry_point="textarena.envs.DontSayIt.env:DontSayItEnv",
    hardcore=True, max_turns=30,
)
