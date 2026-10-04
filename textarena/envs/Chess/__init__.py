from textarena.envs.registration import register

register(
    id="Chess-v1",
    entry_point="textarena.envs.Chess.env:ChessEnv",
    is_open=True, max_turns=100, show_valid=True,
)
register(
    id="Chess-v1-blind",
    entry_point="textarena.envs.Chess.env:ChessEnv",
    is_open=False, max_turns=100, show_valid=False,
)
