from textarena.envs.registration import register_with_versions

register_with_versions(id="2048-v1-easy", entry_point="textarena.envs.Game2048.env:Game2048Env", target_tile=1024)
register_with_versions(id="2048-v1", entry_point="textarena.envs.Game2048.env:Game2048Env", target_tile=2048)
register_with_versions(
    id="2048-v1-3x3",
    entry_point="textarena.envs.Game2048.env:Game2048Env",
    target_tile=256, board_size=3,
)
