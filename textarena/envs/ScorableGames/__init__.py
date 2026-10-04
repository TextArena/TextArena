from textarena.envs.registration import register

register(
    id="ScorableGames-v1",
    entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv",
    game_config="base", max_rounds=120, invalid_move_default="Accept",
)
