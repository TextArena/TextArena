from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Chess-v0",
    entry_point="textarena.envs.Chess.env:ChessEnv",
    is_open=True, max_turns=100, show_valid=True,
)
register_with_versions(
    id="Chess-v0-blind",
    entry_point="textarena.envs.Chess.env:ChessEnv",
    is_open=False, max_turns=100, show_valid=False,
)
