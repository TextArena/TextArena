from textarena.envs.registration import register

register(
    id="Bomberman-v1",
    entry_point="textarena.envs.Bomberman.env:TwoPlayerBombermanEnv",
    grid_size=10, max_turns=100,
)
