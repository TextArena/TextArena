from textarena.envs.registration import register_with_versions

register_with_versions(id="TicTacToe-v0", entry_point="textarena.envs.TicTacToe.env:TicTacToeEnv")
