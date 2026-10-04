from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ConnectFour-v0",
    entry_point="textarena.envs.ConnectFour.env:ConnectFourEnv",
    is_open=True, num_rows=6, num_cols=7,
)
register_with_versions(
    id="ConnectFour-v0-blind",
    entry_point="textarena.envs.ConnectFour.env:ConnectFourEnv",
    is_open=False, num_rows=6, num_cols=7,
)
