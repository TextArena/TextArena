from textarena.envs.registration import register_with_versions

register_with_versions(id="Sudoku-v1", entry_point="textarena.envs.Sudoku.env:SudokuEnv", clues=60, max_turns=100)
register_with_versions(id="Sudoku-v1-hard", entry_point="textarena.envs.Sudoku.env:SudokuEnv", clues=20, max_turns=100)
