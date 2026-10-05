from textarena.envs.registration import register

register(
    id="Othello-v1",
    entry_point="textarena.envs.Othello.env:OthelloEnv",
    board_size=8, show_valid=True,
)
register(
    id="Othello-v1-hard",
    entry_point="textarena.envs.Othello.env:OthelloEnv",
    board_size=8, show_valid=False,
)
