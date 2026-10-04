from textarena.envs.registration import register_with_versions

register_with_versions(id="Battleship-v0", entry_point="textarena.envs.Battleship.env:BattleshipEnv", grid_size=5)
register_with_versions(
    id="Battleship-v0-standard",
    entry_point="textarena.envs.Battleship.env:BattleshipEnv",
    grid_size=10,
)
