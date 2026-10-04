from textarena.envs.registration import register

register(id="Sudoku-v1", entry_point="textarena.envs.Sudoku.env:SudokuEnv", clues=60, max_turns=100)
register(id="Sudoku-v1-hard", entry_point="textarena.envs.Sudoku.env:SudokuEnv", clues=20, max_turns=100)
