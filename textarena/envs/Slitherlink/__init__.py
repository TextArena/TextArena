from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Slitherlink-v1",
    entry_point="textarena.envs.Slitherlink.env:SlitherlinkEnv",
    rows=4, cols=4, max_turns=200,
)
