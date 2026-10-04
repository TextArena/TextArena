from textarena.envs.registration import register_with_versions

register_with_versions(id="SimpleTak-v0", entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", board_size=4)
