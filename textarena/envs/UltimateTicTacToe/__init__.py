from textarena.envs.registration import register

register(
    id="UltimateTicTacToe-v1",
    entry_point="textarena.envs.UltimateTicTacToe.env:UltimateTicTacToeEnv",
)
