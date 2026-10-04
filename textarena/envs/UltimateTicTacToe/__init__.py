from textarena.envs.registration import register_with_versions

register_with_versions(
    id="UltimateTicTacToe-v1",
    entry_point="textarena.envs.UltimateTicTacToe.env:UltimateTicTacToeEnv",
)
