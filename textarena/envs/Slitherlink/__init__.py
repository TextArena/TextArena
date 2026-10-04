from textarena.envs.registration import register

register(
    id="Slitherlink-v1",
    entry_point="textarena.envs.Slitherlink.env:SlitherlinkEnv",
    rows=4, cols=4, max_turns=200,
)
