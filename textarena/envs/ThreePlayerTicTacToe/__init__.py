from textarena.envs.registration import register

register(
    id="ThreePlayerTicTacToe-v1",
    entry_point="textarena.envs.ThreePlayerTicTacToe.env:ThreePlayerTicTacToeEnv",
)
