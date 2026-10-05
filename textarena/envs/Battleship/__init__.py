from textarena.envs.registration import register

register(id="Battleship-v1", entry_point="textarena.envs.Battleship.env:BattleshipEnv", grid_size=5)
register(
    id="Battleship-v1-standard",
    entry_point="textarena.envs.Battleship.env:BattleshipEnv",
    grid_size=10,
)
