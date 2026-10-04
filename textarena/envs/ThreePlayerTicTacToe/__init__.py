from textarena.envs.registration import register_with_versions

register_with_versions(
    id="ThreePlayerTicTacToe-v1",
    entry_point="textarena.envs.ThreePlayerTicTacToe.env:ThreePlayerTicTacToeEnv",
)
