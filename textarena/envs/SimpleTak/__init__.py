from textarena.envs.registration import register

register(id="SimpleTak-v1", entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", board_size=4)
