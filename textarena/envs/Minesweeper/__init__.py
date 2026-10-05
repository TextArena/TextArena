from textarena.envs.registration import register

register(
    id="Minesweeper-v1",
    entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv",
    rows=8, cols=8, num_mines=10, max_turns=100,
)
register(
    id="Minesweeper-v1-hard",
    entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv",
    rows=12, cols=12, num_mines=30, max_turns=100,
)
