from textarena.envs.registration import register_with_versions

register_with_versions(
    id="Minesweeper-v0",
    entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv",
    rows=8, cols=8, num_mines=10, max_turns=100,
)
register_with_versions(
    id="Minesweeper-v0-hard",
    entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv",
    rows=12, cols=12, num_mines=30, max_turns=100,
)
