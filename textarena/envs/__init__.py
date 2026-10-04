""" Register all game environments """ 

from textarena.envs.registration import register, register_with_versions
from textarena.utils.jury import OpenRouterJury
from textarena.wrappers import FullHistoryObservationWrapper, BoardObservationWrapper

# '-mdp' wrapper choices (the default variant always uses CurrentTurnObservationWrapper)
HISTORY_MDP = [FullHistoryObservationWrapper]   # conversation/negotiation games: the dialogue is the state
BOARD_MDP = [BoardObservationWrapper]           # board games: game messages + latest board capture the state


# 2048 [1 Player]
# Standard 4x4 board variants
register_with_versions(id="2048-v0-ultra-easy",     entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=32    )
register_with_versions(id="2048-v0-mega-easy",      entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=64    )
register_with_versions(id="2048-v0-super-easy",     entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=128    )
register_with_versions(id="2048-v0-very-easy",      entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=256    )
register_with_versions(id="2048-v0-easy",           entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=1024   )
register_with_versions(id="2048-v0",                entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=2048   )
register_with_versions(id="2048-v0-hard",           entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=4096   )
register_with_versions(id="2048-v0-very-hard",      entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=8192   )
register_with_versions(id="2048-v0-extreme",        entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=16384  )

# Arbitrary board size variants
register_with_versions(id="2048-v0-3x3",            entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=256, board_size=3)
register_with_versions(id="2048-v0-5x5",            entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=2048, board_size=5)
register_with_versions(id="2048-v0-6x6",            entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=2048, board_size=6)
register_with_versions(id="2048-v0-8x8",            entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=2048, board_size=8)
register_with_versions(id="2048-v0-10x10",          entry_point="textarena.envs.Game2048.env:Game2048Env", mdp_wrappers=BOARD_MDP, target_tile=2048, board_size=10)

# Bandit [1 Player]
register_with_versions(id="Bandit-v0",        entry_point="textarena.envs.Bandit.env:BanditEnv", mdp_wrappers=BOARD_MDP, buttons=['red', 'blue', 'green', 'yellow', 'purple'],                                               p_gap=0.10, num_turns=20)
register_with_versions(id="Bandit-v0-hard",   entry_point="textarena.envs.Bandit.env:BanditEnv", mdp_wrappers=BOARD_MDP, buttons=['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'pink', 'brown', 'gray', 'black'],   p_gap=0.05, num_turns=40)

# Blackjack (1 Player)
register_with_versions(id="Blackjack-v0",       entry_point="textarena.envs.Blackjack.env:BlackjackEnv", mdp_wrappers=BOARD_MDP, num_hands=5   )
register_with_versions(id="Blackjack-v0-long",  entry_point="textarena.envs.Blackjack.env:BlackjackEnv", mdp_wrappers=BOARD_MDP, num_hands=15  )

# Countdown [1 Player]
register_with_versions(id="Countdown-v0", entry_point="textarena.envs.Countdown.env:CountdownEnv", mdp_wrappers=BOARD_MDP, numbers=[100, 75, 6, 4, 3, 2], target=532)

# Crosswords [1 Player]
register_with_versions(id="Crosswords-v0",          entry_point="textarena.envs.Crosswords.env:CrosswordsEnv", mdp_wrappers=BOARD_MDP, hardcore=False,    max_turns=30, num_words=3)
register_with_versions(id="Crosswords-v0-hardcore", entry_point="textarena.envs.Crosswords.env:CrosswordsEnv", mdp_wrappers=BOARD_MDP, hardcore=True,     max_turns=30, num_words=3)

# Cryptarithm [1 Player]
register_with_versions(id="Cryptarithm-v0", entry_point="textarena.envs.Cryptarithm.env:CryptarithmEnv", mdp_wrappers=BOARD_MDP, equation="SEND + MORE = MONEY", max_turns=100)

# FifteenPuzzle [1 Player]
register_with_versions(id="FifteenPuzzle-v0", entry_point="textarena.envs.FifteenPuzzle.env:FifteenPuzzleEnv", mdp_wrappers=BOARD_MDP, max_turns=200)

# FrozenLake [1 Player]
register_with_versions(id="FrozenLake-v0",          entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv", mdp_wrappers=BOARD_MDP, size=4, num_holes=3, randomize_start_goal=False  )
register_with_versions(id="FrozenLake-v0-random",   entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv", mdp_wrappers=BOARD_MDP, size=4, num_holes=3, randomize_start_goal=True   )
register_with_versions(id="FrozenLake-v0-hardcore", entry_point="textarena.envs.FrozenLake.env:FrozenLakeEnv", mdp_wrappers=BOARD_MDP, size=5, num_holes=6, randomize_start_goal=False  )

# GuessTheNumber [1 Player]
register_with_versions(id="GuessTheNumber-v0",          entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv", mdp_wrappers=BOARD_MDP, min_number=1, max_number=20, max_turns=10)
register_with_versions(id="GuessTheNumber-v0-hardcore", entry_point="textarena.envs.GuessTheNumber.env:GuessTheNumberEnv", mdp_wrappers=BOARD_MDP, min_number=1, max_number=50, max_turns=10)

# GuessWho [1 Player]
register_with_versions(id="GuessWho-v0", entry_point="textarena.envs.GuessWho.env:GuessWhoEnv", mdp_wrappers=BOARD_MDP, max_turns=20)

# Hangman [1 Player]
register_with_versions(id="Hangman-v0",             entry_point="textarena.envs.Hangman.env:HangmanEnv", mdp_wrappers=BOARD_MDP, hardcore=False    )
register_with_versions(id="Hangman-v0-hardcore",    entry_point="textarena.envs.Hangman.env:HangmanEnv", mdp_wrappers=BOARD_MDP, hardcore=True     )

# LightsOut [1 Player]
register_with_versions(id="LightsOut-v0",           entry_point="textarena.envs.LightsOut.env:LightsOutEnv", mdp_wrappers=BOARD_MDP, size=5, max_turns=20)

# LogicPuzzle [1 Player]
register_with_versions(id="LogicPuzzle-v0",         entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv", mdp_wrappers=BOARD_MDP, difficulty="easy")
register_with_versions(id="LogicPuzzle-v0-hard",    entry_point="textarena.envs.LogicPuzzle.env:LogicPuzzleEnv", mdp_wrappers=BOARD_MDP, difficulty="hard")

# Mastermind [1 Player]
register_with_versions(id="Mastermind-v0",          entry_point="textarena.envs.Mastermind.env:MastermindEnv", mdp_wrappers=BOARD_MDP, code_length=4, num_numbers=6, max_turns=20, duplicate_numbers=False)
register_with_versions(id="Mastermind-v0-hard",     entry_point="textarena.envs.Mastermind.env:MastermindEnv", mdp_wrappers=BOARD_MDP, code_length=4, num_numbers=8, max_turns=30, duplicate_numbers=False)
register_with_versions(id="Mastermind-v0-extreme",  entry_point="textarena.envs.Mastermind.env:MastermindEnv", mdp_wrappers=BOARD_MDP, code_length=6, num_numbers=12, max_turns=50, duplicate_numbers=True)

# Minesweeper [1 Player]
register_with_versions(id="Minesweeper-v0",         entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv", mdp_wrappers=BOARD_MDP, rows=8,  cols=8,     num_mines=10,   max_turns=100)
register_with_versions(id="Minesweeper-v0-small",   entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv", mdp_wrappers=BOARD_MDP, rows=5,  cols=5,     num_mines=5,    max_turns=100)
register_with_versions(id="Minesweeper-v0-medium",  entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv", mdp_wrappers=BOARD_MDP, rows=10, cols=10,    num_mines=20,   max_turns=100)
register_with_versions(id="Minesweeper-v0-hard",    entry_point="textarena.envs.Minesweeper.env:MinesweeperEnv", mdp_wrappers=BOARD_MDP, rows=12, cols=12,    num_mines=30,   max_turns=100)

# PegJump [1 Player]
register_with_versions(id="PegJump-v0", entry_point="textarena.envs.PegJump.env:PegJumpEnv", mdp_wrappers=BOARD_MDP, initial_empty=5)

# RushHour [1 Player]
register_with_versions(id="RushHour-v0", entry_point="textarena.envs.RushHour.env:RushHourEnv", mdp_wrappers=BOARD_MDP)

# Secretary [1 Player]
register_with_versions(id="Secretary-v0",       entry_point="textarena.envs.Secretary.env:SecretaryEnv", mdp_wrappers=HISTORY_MDP, N=5    )
register_with_versions(id="Secretary-v0-long",  entry_point="textarena.envs.Secretary.env:SecretaryEnv", mdp_wrappers=HISTORY_MDP, N=10   )

# Set [1 Player]
register_with_versions(id="Set-v0", entry_point="textarena.envs.Set.env:SetEnv", mdp_wrappers=BOARD_MDP)

# Klondike Solitaire [1 Player]
register_with_versions(id="Klondike-v0", entry_point="textarena.envs.Klondike.env:KlondikeEnv", mdp_wrappers=BOARD_MDP, max_turns=200, draw_count=1)

# Slitherlink [1 Player]
register_with_versions(id="Slitherlink-v0", entry_point="textarena.envs.Slitherlink.env:SlitherlinkEnv", mdp_wrappers=BOARD_MDP, rows = 4, cols = 4, max_turns = 200)

# Sokoban [1 Player]
register_with_versions(id="Sokoban-v0",         entry_point="textarena.envs.Sokoban.env:SokobanEnv", mdp_wrappers=BOARD_MDP, dim_room=(6,6), max_turns=30, num_boxes=3)
register_with_versions(id="Sokoban-v0-medium",  entry_point="textarena.envs.Sokoban.env:SokobanEnv", mdp_wrappers=BOARD_MDP, dim_room=(8,8), max_turns=50, num_boxes=5)

# Sudoku [1 Player]
register_with_versions(id="Sudoku-v0-very-easy",entry_point="textarena.envs.Sudoku.env:SudokuEnv", mdp_wrappers=BOARD_MDP, clues=75, max_turns=100)
register_with_versions(id="Sudoku-v0-easy",     entry_point="textarena.envs.Sudoku.env:SudokuEnv", mdp_wrappers=BOARD_MDP, clues=70, max_turns=100)
register_with_versions(id="Sudoku-v0",          entry_point="textarena.envs.Sudoku.env:SudokuEnv", mdp_wrappers=BOARD_MDP, clues=60, max_turns=100)
register_with_versions(id="Sudoku-v0-medium",   entry_point="textarena.envs.Sudoku.env:SudokuEnv", mdp_wrappers=BOARD_MDP, clues=40, max_turns=100)
register_with_versions(id="Sudoku-v0-hard",     entry_point="textarena.envs.Sudoku.env:SudokuEnv", mdp_wrappers=BOARD_MDP, clues=20, max_turns=100)

# ThreeCardMonte [1 Player]
register_with_versions(id="ThreeCardMonte-v0", entry_point="textarena.envs.ThreeCardMonte.env:ThreeCardMonteEnv", mdp_wrappers=BOARD_MDP, num_cups=3, steps=10)

# TowerOfHanoi [1 Player]
register_with_versions(id="TowerOfHanoi-v0",            entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv", mdp_wrappers=BOARD_MDP, num_disks=3, max_turns=14  )
register_with_versions(id="TowerOfHanoi-v0-medium",     entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv", mdp_wrappers=BOARD_MDP, num_disks=4, max_turns=30  )
register_with_versions(id="TowerOfHanoi-v0-hard",       entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv", mdp_wrappers=BOARD_MDP, num_disks=5, max_turns=62  )
register_with_versions(id="TowerOfHanoi-v0-hardcore",   entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv", mdp_wrappers=BOARD_MDP, num_disks=6, max_turns=126 )
register_with_versions(id="TowerOfHanoi-v0-extreme",    entry_point="textarena.envs.TowerOfHanoi.env:TowerOfHanoiEnv", mdp_wrappers=BOARD_MDP, num_disks=7, max_turns=254 )

# TwentyQuestions [1 Player]
register_with_versions(id="TwentyQuestions-v0",             entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv", mdp_wrappers=BOARD_MDP, hardcore=False  )
register_with_versions(id="TwentyQuestions-v0-hardcore",    entry_point="textarena.envs.TwentyQuestions.env:TwentyQuestionsEnv", mdp_wrappers=BOARD_MDP, hardcore=True   )

# WordLadder (1 Player)
register_with_versions(id="WordLadder-v0",          entry_point="textarena.envs.WordLadder.env:WordLadderEnv", mdp_wrappers=BOARD_MDP, min_distance=5,     max_distance=7,     max_turns=100)
register_with_versions(id="WordLadder-v0-medium",   entry_point="textarena.envs.WordLadder.env:WordLadderEnv", mdp_wrappers=BOARD_MDP, min_distance=8,     max_distance=12,    max_turns=100)
register_with_versions(id="WordLadder-v0-hard",     entry_point="textarena.envs.WordLadder.env:WordLadderEnv", mdp_wrappers=BOARD_MDP, min_distance=13,    max_distance=15,    max_turns=100)

# Wordle (1 Player)
register_with_versions(id="Wordle-v0",                  entry_point="textarena.envs.Wordle.env:WordleEnv", mdp_wrappers=BOARD_MDP, hardcore=False, word_length=5, num_guesses=6)
register_with_versions(id="Wordle-v0-hardcore",         entry_point="textarena.envs.Wordle.env:WordleEnv", mdp_wrappers=BOARD_MDP, hardcore=True,  word_length=5, num_guesses=6)
register_with_versions(id="Wordle-v0-long",             entry_point="textarena.envs.Wordle.env:WordleEnv", mdp_wrappers=BOARD_MDP, hardcore=False, word_length=7, num_guesses=9)
register_with_versions(id="Wordle-v0-long-hardcore",    entry_point="textarena.envs.Wordle.env:WordleEnv", mdp_wrappers=BOARD_MDP, hardcore=True,  word_length=7, num_guesses=9)

# WordSearch (1 Player)
register_with_versions(id="WordSearch-v0",          entry_point="textarena.envs.WordSearch.env:WordSearchEnv", mdp_wrappers=BOARD_MDP, hardcore=False )
register_with_versions(id="WordSearch-v0-hardcore", entry_point="textarena.envs.WordSearch.env:WordSearchEnv", mdp_wrappers=BOARD_MDP, hardcore=True  )









# Alquerque [2 Player]
register_with_versions(id="Alquerque-v0", entry_point="textarena.envs.Alquerque.env:AlquerqueEnv", mdp_wrappers=BOARD_MDP)

# Battleship (2 Player)
register_with_versions(id="Battleship-v0",          entry_point="textarena.envs.Battleship.env:BattleshipEnv", mdp_wrappers=BOARD_MDP, grid_size=5 )
register_with_versions(id="Battleship-v0-standard", entry_point="textarena.envs.Battleship.env:BattleshipEnv", mdp_wrappers=BOARD_MDP, grid_size=10)
register_with_versions(id="Battleship-v0-large",    entry_point="textarena.envs.Battleship.env:BattleshipEnv", mdp_wrappers=BOARD_MDP, grid_size=14)
register_with_versions(id="Battleship-v0-extreme",  entry_point="textarena.envs.Battleship.env:BattleshipEnv", mdp_wrappers=BOARD_MDP, grid_size=20)

# Breakthrough [2 Player]
register_with_versions(id="Breakthrough-v0-tiny",   entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=5,   is_open=True  )
register_with_versions(id="Breakthrough-v0-small",  entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=6,   is_open=True  )
register_with_versions(id="Breakthrough-v0",        entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=8,   is_open=True  )
register_with_versions(id="Breakthrough-v0-large",  entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=10,  is_open=True  )
register_with_versions(id="Breakthrough-v0-blind",  entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=8,   is_open=False )
register_with_versions(id="Breakthrough-v0-long",   entry_point="textarena.envs.Breakthrough.env:BreakthroughEnv", mdp_wrappers=BOARD_MDP, board_size=8,   is_open=True  )

# Briscola (2 Player)
register_with_versions(id="Briscola-v0", entry_point="textarena.envs.Briscola.env:BriscolaEnv", mdp_wrappers=BOARD_MDP)

# Checkers [2 Player]
register_with_versions(id="Checkers-v0",      entry_point="textarena.envs.Checkers.env:CheckersEnv", mdp_wrappers=BOARD_MDP, max_turns=100)
register_with_versions(id="Checkers-v0-long", entry_point="textarena.envs.Checkers.env:CheckersEnv", mdp_wrappers=BOARD_MDP, max_turns=300)

# Chess [2 Player]
register_with_versions(id="Chess-v0",         entry_point="textarena.envs.Chess.env:ChessEnv", mdp_wrappers=BOARD_MDP, is_open=True,  max_turns=100, show_valid=True  )
register_with_versions(id="Chess-v0-long",    entry_point="textarena.envs.Chess.env:ChessEnv", mdp_wrappers=BOARD_MDP, is_open=True,  max_turns=250, show_valid=True  )
register_with_versions(id="Chess-v0-blind",   entry_point="textarena.envs.Chess.env:ChessEnv", mdp_wrappers=BOARD_MDP, is_open=False, max_turns=100, show_valid=False )

# Chopsticks [2 Player]
register_with_versions(id="Chopsticks-v0",        entry_point="textarena.envs.Chopsticks.env:ChopsticksEnv", mdp_wrappers=BOARD_MDP, max_turns=40)
register_with_versions(id="Chopsticks-v0-medium", entry_point="textarena.envs.Chopsticks.env:ChopsticksEnv", mdp_wrappers=BOARD_MDP, max_turns=60)
register_with_versions(id="Chopsticks-v0-long",   entry_point="textarena.envs.Chopsticks.env:ChopsticksEnv", mdp_wrappers=BOARD_MDP, max_turns=80)

# ColonelBlotto [2 Player]
register_with_versions(id="ColonelBlotto-v0-small",     entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv", mdp_wrappers=BOARD_MDP, num_fields=3, num_total_units=20, num_rounds=5   )
register_with_versions(id="ColonelBlotto-v0",           entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv", mdp_wrappers=BOARD_MDP, num_fields=3, num_total_units=20, num_rounds=9   )
register_with_versions(id="ColonelBlotto-v0-large",     entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv", mdp_wrappers=BOARD_MDP, num_fields=5, num_total_units=50, num_rounds=15  )
register_with_versions(id="ColonelBlotto-v0-extreme",   entry_point="textarena.envs.ColonelBlotto.env:ColonelBlottoEnv", mdp_wrappers=BOARD_MDP, num_fields=7, num_total_units=75, num_rounds=25  )

# ConnectFour [2 Player]
register_with_versions(id="ConnectFour-v0",       entry_point="textarena.envs.ConnectFour.env:ConnectFourEnv", mdp_wrappers=BOARD_MDP, is_open=True,  num_rows=6,  num_cols=7  )
register_with_versions(id="ConnectFour-v0-blind", entry_point="textarena.envs.ConnectFour.env:ConnectFourEnv", mdp_wrappers=BOARD_MDP, is_open=False, num_rows=6,  num_cols=7  )
register_with_versions(id="ConnectFour-v0-large", entry_point="textarena.envs.ConnectFour.env:ConnectFourEnv", mdp_wrappers=BOARD_MDP, is_open=True,  num_rows=12, num_cols=15 )

# Coup [2-6 Players]
register_with_versions(id="Coup-v0", entry_point="textarena.envs.Coup.env:CoupEnv", mdp_wrappers=HISTORY_MDP)

# Crusade [2 Player]
register_with_versions(id="Crusade-v0", entry_point="textarena.envs.Crusade.env:CrusadeEnv", mdp_wrappers=BOARD_MDP)

# Debate [2 Player]
register_with_versions(id="Debate-v0",        entry_point="textarena.envs.Debate.env:DebateEnv", mdp_wrappers=HISTORY_MDP, max_turns=6,     jury_class=OpenRouterJury, jury_size=7  )
register_with_versions(id="Debate-v0-medium", entry_point="textarena.envs.Debate.env:DebateEnv", mdp_wrappers=HISTORY_MDP, max_turns=12,    jury_class=OpenRouterJury, jury_size=9  )
register_with_versions(id="Debate-v0-long",   entry_point="textarena.envs.Debate.env:DebateEnv", mdp_wrappers=HISTORY_MDP, max_turns=30,    jury_class=OpenRouterJury, jury_size=13 )

# DontSayIt [2 Player]
register_with_versions(id="DontSayIt-v0",             entry_point="textarena.envs.DontSayIt.env:DontSayItEnv", mdp_wrappers=HISTORY_MDP, hardcore=False,   max_turns=20    )
register_with_versions(id="DontSayIt-v0-hardcore",    entry_point="textarena.envs.DontSayIt.env:DontSayItEnv", mdp_wrappers=HISTORY_MDP, hardcore=True,    max_turns=30    )
register_with_versions(id="DontSayIt-v0-unlimited",   entry_point="textarena.envs.DontSayIt.env:DontSayItEnv", mdp_wrappers=HISTORY_MDP, hardcore=False,   max_turns=None  )

# GameOfPureStrategy [2 Player]
register_with_versions(id="GameOfPureStrategy-v0", entry_point="textarena.envs.GameOfPureStrategy.env:GameOfPureStrategyEnv", mdp_wrappers=BOARD_MDP)

# GermanWhist [2 Player]
register_with_versions(id="GermanWhist-v0", entry_point="textarena.envs.GermanWhist.env:GermanWhistEnv", mdp_wrappers=BOARD_MDP)

# Golf [2 Player]
register_with_versions(id="Golf-v0",        entry_point="textarena.envs.Golf.env:GolfEnv", mdp_wrappers=BOARD_MDP, num_cards=6, num_columns=3)
register_with_versions(id="Golf-v0-medium", entry_point="textarena.envs.Golf.env:GolfEnv", mdp_wrappers=BOARD_MDP, num_cards=9, num_columns=3)

# HighSociety [2 Player]
register_with_versions(id="HighSociety-v0", entry_point="textarena.envs.HighSociety.env:HighSocietyEnv", mdp_wrappers=BOARD_MDP)

# IndianPoker [2 Player]
register_with_versions(id="IndianPoker-v0-short",     entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=3)
register_with_versions(id="IndianPoker-v0",           entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=5)
register_with_versions(id="IndianPoker-v0-medium",    entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=9)
register_with_versions(id="IndianPoker-v0-long",      entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=15)
register_with_versions(id="IndianPoker-v0-extreme",   entry_point="textarena.envs.IndianPoker.env:IndianPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=25)

# IteratedMatchingPennies [2 Player]
register_with_versions(id="IteratedMatchingPennies-v0", entry_point="textarena.envs.IteratedMatchingPennies.env:IteratedMatchingPenniesEnv", mdp_wrappers=BOARD_MDP, num_rounds=10)

# IteratedPrisonersDilemma [2 Player]
register_with_versions(id="IteratedPrisonersDilemma-v0", entry_point="textarena.envs.IteratedPrisonersDilemma.env:IteratedPrisonersDilemmaEnv", mdp_wrappers=HISTORY_MDP, num_rounds=10, communication_turns=1, cooperate_reward=3, defect_reward=5, sucker_reward=0, mutual_defect_reward=1)
register_with_versions(id="IteratedPrisonersDilemma-v0-short", entry_point="textarena.envs.IteratedPrisonersDilemma.env:IteratedPrisonersDilemmaEnv", mdp_wrappers=HISTORY_MDP, num_rounds=5, communication_turns=1, cooperate_reward=3, defect_reward=5, sucker_reward=0, mutual_defect_reward=1)

# IteratedRockPaperScissors [2 Player]
register_with_versions(id="IteratedRockPaperScissors-v0", entry_point="textarena.envs.IteratedRockPaperScissors.env:IteratedRockPaperScissorsEnv", mdp_wrappers=BOARD_MDP, num_rounds=9)

# IteratedTwoThirdsAverage [2 Player]
register_with_versions(id="IteratedTwoThirdsAverage-v0", entry_point="textarena.envs.IteratedTwoThirdsAverage.env:IteratedTwoThirdsAverageEnv", mdp_wrappers=BOARD_MDP, num_rounds=10, min_guess=0.0, max_guess=100.0)

# IteratedStagHunt [2 Player]
register_with_versions(id="IteratedStagHunt-v0",            entry_point="textarena.envs.IteratedStagHunt.env:IteratedStagHuntEnv", mdp_wrappers=HISTORY_MDP, num_rounds=5, conversation_rounds=3, mutual_stag_reward=10, single_hare_reward=8, single_stag_reward=1, mutual_hare_reward=5, randomize_payoff=False    )
register_with_versions(id="IteratedStagHunt-v0-randomized", entry_point="textarena.envs.IteratedStagHunt.env:IteratedStagHuntEnv", mdp_wrappers=HISTORY_MDP, num_rounds=5, conversation_rounds=3, mutual_stag_reward=10, single_hare_reward=8, single_stag_reward=1, mutual_hare_reward=5, randomize_payoff=True     )

# KuhnPoker [2 Player]
register_with_versions(id="KuhnPoker-v0",         entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=3   )
register_with_versions(id="KuhnPoker-v0-short",   entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=5   )
register_with_versions(id="KuhnPoker-v0-medium",  entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=9   )
register_with_versions(id="KuhnPoker-v0-long",    entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=15  )
register_with_versions(id="KuhnPoker-v0-extreme", entry_point="textarena.envs.KuhnPoker.env:KuhnPokerEnv", mdp_wrappers=BOARD_MDP, max_rounds=25  )

# LeducHoldem [2 Player]
register_with_versions(id="LeducHoldem-v0",         entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", mdp_wrappers=BOARD_MDP, max_rounds=5   )
register_with_versions(id="LeducHoldem-v0-medium",  entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", mdp_wrappers=BOARD_MDP, max_rounds=9   )
register_with_versions(id="LeducHoldem-v0-long",    entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", mdp_wrappers=BOARD_MDP, max_rounds=15  )
register_with_versions(id="LeducHoldem-v0-extreme", entry_point="textarena.envs.LeducHoldem.env:LeducHoldemEnv", mdp_wrappers=BOARD_MDP, max_rounds=25  )

# LeTruc [2 Player]
register_with_versions(id="LeTruc-v0", entry_point="textarena.envs.LeTruc.env:LeTrucEnv", mdp_wrappers=BOARD_MDP)

# LinesOfAction [2 Player]
register_with_versions(id="LinesOfAction-v0", entry_point="textarena.envs.LinesOfAction.env:LinesOfActionEnv", mdp_wrappers=BOARD_MDP)

# LetterAuction [2 Player]
register_with_versions(id="LetterAuction-v0",       entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv", mdp_wrappers=BOARD_MDP, starting_coins=100)
register_with_versions(id="LetterAuction-v0-medium",entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv", mdp_wrappers=BOARD_MDP, starting_coins=50)
register_with_versions(id="LetterAuction-v0-hard",  entry_point="textarena.envs.LetterAuction.env:LetterAuctionEnv", mdp_wrappers=BOARD_MDP, starting_coins=25)

# MemoryGame [2 Player]
register_with_versions(id="MemoryGame-v0",          entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv", mdp_wrappers=BOARD_MDP, grid_size=4, max_turns=30)
register_with_versions(id="MemoryGame-v0-medium",   entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv", mdp_wrappers=BOARD_MDP, grid_size=6, max_turns=50)
register_with_versions(id="MemoryGame-v0-hard",     entry_point="textarena.envs.MemoryGame.env:MemoryGameEnv", mdp_wrappers=BOARD_MDP, grid_size=8, max_turns=80)

# Nim [2 Player]
register_with_versions(id="Nim-v0",           entry_point="textarena.envs.Nim.env:NimEnv", mdp_wrappers=BOARD_MDP, piles=[3, 4, 5]          )
register_with_versions(id="Nim-v0-medium",    entry_point="textarena.envs.Nim.env:NimEnv", mdp_wrappers=BOARD_MDP, piles=[4, 2, 3, 7]       )
register_with_versions(id="Nim-v0-large",     entry_point="textarena.envs.Nim.env:NimEnv", mdp_wrappers=BOARD_MDP, piles=[5, 7, 9, 11, 2]   )

# Othello [2 Player]
register_with_versions(id="Othello-v0-tiny",  entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=4,  show_valid=True     )
register_with_versions(id="Othello-v0-small", entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=6,  show_valid=True     )
register_with_versions(id="Othello-v0",       entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=8,  show_valid=True     )
register_with_versions(id="Othello-v0-big",   entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=10, show_valid=True     )
register_with_versions(id="Othello-v0-huge",  entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=14, show_valid=True     )
register_with_versions(id="Othello-v0-hard",  entry_point="textarena.envs.Othello.env:OthelloEnv", mdp_wrappers=BOARD_MDP, board_size=8,  show_valid=False    )

# Pig [2 Player]
register_with_versions(id="PigDice-v0",       entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=100, max_turns=100   )
register_with_versions(id="PigDice-v0-short", entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=50,  max_turns=25    )
register_with_versions(id="PigDice-v0-long",  entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=500, max_turns=500   )
register_with_versions(id="PigDice-v0-50",    entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=50,  max_turns=50    )
register_with_versions(id="PigDice-v0-100",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=100, max_turns=100   )
register_with_versions(id="PigDice-v0-150",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=150, max_turns=150   )
register_with_versions(id="PigDice-v0-200",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=200, max_turns=200   )
register_with_versions(id="PigDice-v0-250",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=250, max_turns=250   )
register_with_versions(id="PigDice-v0-300",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=300, max_turns=300   )
register_with_versions(id="PigDice-v0-350",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=350, max_turns=350   )
register_with_versions(id="PigDice-v0-400",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=400, max_turns=400   )
register_with_versions(id="PigDice-v0-450",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=450, max_turns=450   )
register_with_versions(id="PigDice-v0-500",   entry_point="textarena.envs.PigDice.env:PigDiceEnv", mdp_wrappers=BOARD_MDP, winning_score=500, max_turns=500   )

# QuantumTicTacToe [2 Player]
register_with_versions(id="QuantumTicTacToe-v0",    entry_point="textarena.envs.QuantumTicTacToe.env:QuantumTicTacToeEnv", mdp_wrappers=BOARD_MDP)

# ReverseTicTacToe [2 Player]
register_with_versions(id="ReverseTicTacToe-v0",    entry_point="textarena.envs.ReverseTicTacToe.env:ReverseTicTacToeEnv", mdp_wrappers=BOARD_MDP)

# ScenarioPlanning [2 Player]
register_with_versions(id="ScenarioPlanning-v0",    entry_point="textarena.envs.ScenarioPlanning.env:ScenarioPlanningEnv", mdp_wrappers=HISTORY_MDP, jury_class=OpenRouterJury, jury_size=11)

# SimpleBlindAunction [2 Player]
register_with_versions(id="SimpleBlindAuction-v0-quick",  entry_point="textarena.envs.SimpleBlindAuction.env:SimpleBlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=750,    num_items=3, conversation_rounds=1)
register_with_versions(id="SimpleBlindAuction-v0",        entry_point="textarena.envs.SimpleBlindAuction.env:SimpleBlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=1000,   num_items=5, conversation_rounds=3)
register_with_versions(id="SimpleBlindAuction-v0-rich",   entry_point="textarena.envs.SimpleBlindAuction.env:SimpleBlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=2000,   num_items=5, conversation_rounds=5)

# SimpleNegotiation [2 Player]
register_with_versions(id="SimpleNegotiation-v0-short",   entry_point="textarena.envs.SimpleNegotiation.env:SimpleNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_turns=6)
register_with_versions(id="SimpleNegotiation-v0",         entry_point="textarena.envs.SimpleNegotiation.env:SimpleNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_turns=10)
register_with_versions(id="SimpleNegotiation-v0-long",    entry_point="textarena.envs.SimpleNegotiation.env:SimpleNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_turns=30)

# SimpleTak [2 Player]
register_with_versions(id="SimpleTak-v0",         entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", mdp_wrappers=BOARD_MDP, board_size=4)
register_with_versions(id="SimpleTak-v0-medium",  entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", mdp_wrappers=BOARD_MDP, board_size=5)
register_with_versions(id="SimpleTak-v0-large",   entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", mdp_wrappers=BOARD_MDP, board_size=6)
register_with_versions(id="SimpleTak-v0-extreme", entry_point="textarena.envs.SimpleTak.env:SimpleTakEnv", mdp_wrappers=BOARD_MDP, board_size=8)

# SpellingBee [2 Player]
register_with_versions(id="SpellingBee-v0-small", entry_point="textarena.envs.SpellingBee.env:SpellingBeeEnv", mdp_wrappers=BOARD_MDP, num_letters=4   )
register_with_versions(id="SpellingBee-v0",       entry_point="textarena.envs.SpellingBee.env:SpellingBeeEnv", mdp_wrappers=BOARD_MDP, num_letters=7   )
register_with_versions(id="SpellingBee-v0-large", entry_point="textarena.envs.SpellingBee.env:SpellingBeeEnv", mdp_wrappers=BOARD_MDP, num_letters=10  )

# SpiteAndMalice [2 Player]
register_with_versions(id="SpiteAndMalice-v0", entry_point="textarena.envs.SpiteAndMalice.env:SpiteAndMaliceEnv", mdp_wrappers=BOARD_MDP)

# Stratego [2 Player]
register_with_versions(id="Stratego-v0", entry_point="textarena.envs.Stratego.env:StrategoEnv", mdp_wrappers=BOARD_MDP)

# Tak [2 Player]
register_with_versions(id="Tak-v0",         entry_point="textarena.envs.Tak.env:TakEnv", mdp_wrappers=BOARD_MDP, board_size=4, stones=15, capstones=1, max_turns=100)
register_with_versions(id="Tak-v0-medium",  entry_point="textarena.envs.Tak.env:TakEnv", mdp_wrappers=BOARD_MDP, board_size=5, stones=21, capstones=1, max_turns=150)
register_with_versions(id="Tak-v0-hard",    entry_point="textarena.envs.Tak.env:TakEnv", mdp_wrappers=BOARD_MDP, board_size=6, stones=30, capstones=1, max_turns=200)

# TicTacToe [2 Player]
register_with_versions(id="TicTacToe-v0", entry_point="textarena.envs.TicTacToe.env:TicTacToeEnv", mdp_wrappers=BOARD_MDP)

# TruthAndDeception [2 Player]
register_with_versions(id="TruthAndDeception-v0",         entry_point="textarena.envs.TruthAndDeception.env:TruthAndDeceptionEnv", mdp_wrappers=HISTORY_MDP, max_turns=6    )
register_with_versions(id="TruthAndDeception-v0-long",    entry_point="textarena.envs.TruthAndDeception.env:TruthAndDeceptionEnv", mdp_wrappers=HISTORY_MDP, max_turns=12   )
register_with_versions(id="TruthAndDeception-v0-extreme", entry_point="textarena.envs.TruthAndDeception.env:TruthAndDeceptionEnv", mdp_wrappers=HISTORY_MDP, max_turns=50   )

# TwoDollar [2 Player]
register_with_versions(id="TwoDollar-v0", entry_point="textarena.envs.TwoDollar.env:TwoDollarEnv", mdp_wrappers=HISTORY_MDP)

# VendorNegotiation [2 Player]
register_with_versions(id="VendorNegotiation-v0",       entry_point="textarena.envs.VendorNegotiation.env:VendorNegotiationEnv", mdp_wrappers=HISTORY_MDP, num_products=5, max_rounds=20)
register_with_versions(id="VendorNegotiation-v0-lite",  entry_point="textarena.envs.VendorNegotiation.env:VendorNegotiationEnv", mdp_wrappers=HISTORY_MDP, num_products=3, max_rounds=10)
register_with_versions(id="VendorNegotiation-v0-heavy", entry_point="textarena.envs.VendorNegotiation.env:VendorNegotiationEnv", mdp_wrappers=HISTORY_MDP, num_products=8, max_rounds=30)

# UltimateTicTacToe [2 Player]
register_with_versions(id="UltimateTicTacToe-v0", entry_point="textarena.envs.UltimateTicTacToe.env:UltimateTicTacToeEnv", mdp_wrappers=BOARD_MDP)

# UltimatumGame [2 Player]
register_with_versions(id="IteratedUltimatumGame-v0",           entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv", mdp_wrappers=HISTORY_MDP, pool=50, max_turns=10, alternate_roles=False)
register_with_versions(id="IteratedUltimatumGame-v0-alternate", entry_point="textarena.envs.IteratedUltimatumGame.env:IteratedUltimatumGameEnv", mdp_wrappers=HISTORY_MDP, pool=50, max_turns=12, alternate_roles=True)

# UsedCarNegotiation [2 Player]
register_with_versions(id="UsedCarNegotiation-v0",              entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_rounds=10)
register_with_versions(id="UsedCarNegotiation-v0-strong-buyer", entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_rounds=10, batna=("strong", "weak"))
register_with_versions(id="UsedCarNegotiation-v0-strong-seller",entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_rounds=10, batna=("weak", "strong"))
register_with_versions(id="UsedCarNegotiation-v0-balanced",     entry_point="textarena.envs.UsedCarNegotiation.env:UsedCarNegotiationEnv", mdp_wrappers=HISTORY_MDP, max_rounds=10, batna=("strong", "strong"))

# WildTicTacToe [2 Player]
register_with_versions(id="WildTicTacToe-v0", entry_point="textarena.envs.WildTicTacToe.env:WildTicTacToeEnv", mdp_wrappers=BOARD_MDP)

# WordChains [2 Player]
register_with_versions(id="WordChains-v0", entry_point="textarena.envs.WordChains.env:WordChainsEnv", mdp_wrappers=BOARD_MDP)















# Hex [2 Player]
#register_with_versions(id="Hex-v0", entry_point="textarena.envs.Hex.env:HexEnv", mdp_wrappers=BOARD_MDP)

















# Snake [2-15 Players]
register_with_versions(id="Snake-v0",           entry_point="textarena.envs.Snake.env:SnakeEnv", mdp_wrappers=BOARD_MDP, width=5,   height=5,   num_apples=2, max_turns=40  )
register_with_versions(id="Snake-v0-standard",  entry_point="textarena.envs.Snake.env:SnakeEnv", mdp_wrappers=BOARD_MDP, width=10,  height=10,  num_apples=3, max_turns=100 )
register_with_versions(id="Snake-v0-large",     entry_point="textarena.envs.Snake.env:SnakeEnv", mdp_wrappers=BOARD_MDP, width=15,  height=15,  num_apples=5, max_turns=250 )

# Surround [2-15 Players]
register_with_versions(id="Surround-v0",            entry_point="textarena.envs.Surround.env:SurroundEnv", mdp_wrappers=BOARD_MDP, width=5,     height=5,   max_turns=40    )
register_with_versions(id="Surround-v0-standard",   entry_point="textarena.envs.Surround.env:SurroundEnv", mdp_wrappers=BOARD_MDP, width=10,    height=10,  max_turns=100   )
register_with_versions(id="Surround-v0-large",      entry_point="textarena.envs.Surround.env:SurroundEnv", mdp_wrappers=BOARD_MDP, width=15,    height=15,  max_turns=250   )

# Taboo [4-6 Players]
register_with_versions(id="Taboo-v0", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["things"])
register_with_versions(id="Taboo-v0-animals", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["animals"])
register_with_versions(id="Taboo-v0-cars", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["cars"])
register_with_versions(id="Taboo-v0-city/country", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["city/country"])
register_with_versions(id="Taboo-v0-food", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["food"])
register_with_versions(id="Taboo-v0-literature", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["literature"])
register_with_versions(id="Taboo-v0-people", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["people"])
register_with_versions(id="Taboo-v0-tv", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["tv"])
register_with_versions(id="Taboo-v0-long", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=12, max_attempts_per_player=6, categories=["things"])
register_with_versions(id="Taboo-v0-full", entry_point="textarena.envs.Taboo.env:TabooEnv", mdp_wrappers=HISTORY_MDP, max_rounds=4, max_attempts_per_player=6, categories=["animals", "cars", "city/country", "food", "literature", "people", "things", "tv"])

# LiarsDice [2-15 Players]
register_with_versions(id="LiarsDice-v0-small",   entry_point="textarena.envs.LiarsDice.env:LiarsDiceEnv", mdp_wrappers=BOARD_MDP, num_dice=3  )
register_with_versions(id="LiarsDice-v0",         entry_point="textarena.envs.LiarsDice.env:LiarsDiceEnv", mdp_wrappers=BOARD_MDP, num_dice=5  )
register_with_versions(id="LiarsDice-v0-large",   entry_point="textarena.envs.LiarsDice.env:LiarsDiceEnv", mdp_wrappers=BOARD_MDP, num_dice=12 )

# Poker [2-15 Players]
register_with_versions(id="Poker-v0-small",     entry_point="textarena.envs.Poker.env:PokerEnv", mdp_wrappers=BOARD_MDP, num_rounds=5,  starting_chips=1_000, small_blind=10, big_blind=20)
register_with_versions(id="Poker-v0",           entry_point="textarena.envs.Poker.env:PokerEnv", mdp_wrappers=BOARD_MDP, num_rounds=10, starting_chips=1_000, small_blind=10, big_blind=20)
register_with_versions(id="Poker-v0-long",      entry_point="textarena.envs.Poker.env:PokerEnv", mdp_wrappers=BOARD_MDP, num_rounds=15, starting_chips=1_000, small_blind=10, big_blind=20)
register_with_versions(id="Poker-v0-extreme",   entry_point="textarena.envs.Poker.env:PokerEnv", mdp_wrappers=BOARD_MDP, num_rounds=50, starting_chips=1_000, small_blind=10, big_blind=20)

# PublicGoodsGame [Multiple Players]
register_with_versions(id="PublicGoodsGame-v0", entry_point="textarena.envs.PublicGoodsGame.env:PublicGoodsGameEnv", mdp_wrappers=BOARD_MDP, num_rounds=3, communication_turns=3, endowment=20, multiplication_factor=1.5, num_players=3)

# Market Entry Game [Multiple Players]
register_with_versions(id="MarketEntryGame-v0", entry_point="textarena.envs.MarketEntryGame.env:MarketEntryGameEnv", mdp_wrappers=BOARD_MDP, num_rounds=5, communication_turns=3, market_capacity=2, entry_profit=15, overcrowding_penalty=-5, safe_payoff=5, default_num_players=4)

# ThreePlayerTicTacToe [3 Players]
register_with_versions(id="ThreePlayerTicTacToe-v0", entry_point="textarena.envs.ThreePlayerTicTacToe.env:ThreePlayerTicTacToeEnv", mdp_wrappers=BOARD_MDP)

# ThreePlayerGameOfPureStrategy [3 Player]
register_with_versions(id="ThreePlayerGOPS-v0", entry_point="textarena.envs.ThreePlayerGOPS.env:ThreePlayerGOPSEnv", mdp_wrappers=BOARD_MDP)

# ThreePlayerIPD [3 Player]
register_with_versions(id="ThreePlayerIPD-v0", entry_point="textarena.envs.ThreePlayerIPD.env:ThreePlayerIPDEnv", mdp_wrappers=HISTORY_MDP, num_rounds=5, communication_turns=1, cooperate_reward=3, defect_reward=5, sucker_reward=0, mutual_defect_reward=1)

# Character Conclave [3-15 Players]
register_with_versions(id="CharacterConclave-v0",         entry_point="textarena.envs.CharacterConclave.env:CharacterConclaveEnv", mdp_wrappers=HISTORY_MDP, character_budget=1_000     )
register_with_versions(id="CharacterConclave-v0-long",    entry_point="textarena.envs.CharacterConclave.env:CharacterConclaveEnv", mdp_wrappers=HISTORY_MDP, character_budget=5_000     )
register_with_versions(id="CharacterConclave-v0-extreme", entry_point="textarena.envs.CharacterConclave.env:CharacterConclaveEnv", mdp_wrappers=HISTORY_MDP, character_budget=10_000    )

# Codenames [4 Players]
register_with_versions(id="Codenames-v0",           entry_point="textarena.envs.Codenames.env:CodenamesEnv", mdp_wrappers=BOARD_MDP, hardcore=False )
register_with_versions(id="Codenames-v0-hardcore",  entry_point="textarena.envs.Codenames.env:CodenamesEnv", mdp_wrappers=BOARD_MDP, hardcore=True  )

# Hanabi [2-5 Players]
register_with_versions(id="Hanabi-v0", entry_point="textarena.envs.Hanabi.env:HanabiEnv", mdp_wrappers=BOARD_MDP)

# SettlersOfCatan [3-4 Players]
register_with_versions(id="SettlersOfCatan-v0", entry_point="textarena.envs.SettlersOfCatan.env:SettlersOfCatanEnv", mdp_wrappers=HISTORY_MDP)

# Bohnanza [3-5 Players]
register_with_versions(id="Bohnanza-v0",        entry_point="textarena.envs.Bohnanza.env:BohnanzaEnv", mdp_wrappers=HISTORY_MDP, deck_cycles=3, max_trade_rounds=None, max_turns=3000)
register_with_versions(id="Bohnanza-v0-short",  entry_point="textarena.envs.Bohnanza.env:BohnanzaEnv", mdp_wrappers=HISTORY_MDP, deck_cycles=1, max_trade_rounds=3,    max_turns=1000)

# SecretMafia [6-15 Players]
register_with_versions(id="SecretMafia-v0", entry_point="textarena.envs.SecretMafia.env:SecretMafiaEnv", mdp_wrappers=HISTORY_MDP, mafia_ratio=0.25, discussion_rounds=3)

# WinAsMuchAsYouCanEnv [4 Players]
register_with_versions(id="WinAsMuchAsYouCan-v0", entry_point="textarena.envs.WinAsMuchAsYouCan.env:WinAsMuchAsYouCanEnv", mdp_wrappers=BOARD_MDP)



















# Negotiation (2-15 players)
register_with_versions(id="Negotiation-v0", entry_point="textarena.envs.Negotiation.env:NegotiationEnv", mdp_wrappers=HISTORY_MDP, turn_multiple=8)
register_with_versions(id="Negotiation-v0-long", entry_point="textarena.envs.Negotiation.env:NegotiationEnv", mdp_wrappers=HISTORY_MDP, turn_multiple=15)


# BlindAuction (3-15 players)
register_with_versions(id="BlindAuction-v0", entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=1000, num_items=5, conversation_rounds=3)
register_with_versions(id="BlindAuction-v0-high", entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=2500, num_items=8, conversation_rounds=5)
register_with_versions(id="BlindAuction-v0-fast", entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=750,  num_items=3, conversation_rounds=1)
register_with_versions(id="BlindAuction-v0-complex", entry_point="textarena.envs.BlindAuction.env:BlindAuctionEnv", mdp_wrappers=HISTORY_MDP, starting_capital=1500, num_items=12, conversation_rounds=8)


# Diplomacy (3-7 players)
register_with_versions(id="Diplomacy-v0", entry_point="textarena.envs.Diplomacy.env:DiplomacyEnv", mdp_wrappers=HISTORY_MDP, max_turns=30)


# TwoRoomsAndABoom (6-20 players)
register_with_versions(id="TwoRoomsAndABoom-v0", entry_point="textarena.envs.TwoRoomsAndABoom.env:TwoRoomsAndABoomEnv", mdp_wrappers=HISTORY_MDP, num_rounds=3, cards_per_room=3, discussion_rounds=2)


# TabMWP - Tabular Math Word Problems
# register(id="TABMWP-v0", entry_point="textarena.envs.ClassicalReasoningEvals.env:ClassicalReasoningEvalsEnv", file_name="tabmwp/test.jsonl", n_samples=None)

# Santorini Base Version with Fixed Worker Placement 
register_with_versions(id="SantoriniBaseFixed-v0", entry_point="textarena.envs.Santorini.env:SantoriniBaseFixedWorkerEnv", mdp_wrappers=HISTORY_MDP)

# New Recruit
register_with_versions(id="NewRecruit-v0", entry_point="textarena.envs.NewRecruit.env:NewRecruitEnv", mdp_wrappers=HISTORY_MDP)

# ScorableGames [2-15 Players] - Multi-issue negotiation based on LLM-Deliberation
register_with_versions(id="ScorableGames-v0",               entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="base", max_rounds=120, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-conservative",  entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="base", max_rounds=120, invalid_move_default="Reject")
register_with_versions(id="ScorableGames-v0-game1",         entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="game1", max_rounds=120, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-game2",         entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="game2", max_rounds=120, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-game3",         entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="game3", max_rounds=120, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-7players",      entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="base_7players", max_rounds=140, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-medicalethics", entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="medical_ethics", max_rounds=80, invalid_move_default="Accept")
register_with_versions(id="ScorableGames-v0-vendorretailer",entry_point="textarena.envs.ScorableGames.env:ScorableGamesEnv", mdp_wrappers=HISTORY_MDP, game_config="vendor_retailer", max_rounds=40, invalid_move_default="Accept")

# Bomberman [2 Player]
register_with_versions(id="Bomberman-v0", entry_point="textarena.envs.Bomberman.env:TwoPlayerBombermanEnv", mdp_wrappers=BOARD_MDP, grid_size=10, max_turns=100)

# RetroSpaceDuel [2 Player]
register_with_versions(id="RetroSpaceDuel-v0", entry_point="textarena.envs.RetroSpaceDuel.env:RetroSpaceDuelEnv", mdp_wrappers=BOARD_MDP, max_turns=100)

# JoJoJoin [2 Player]
register_with_versions(id="JoJoJoin-v0", entry_point="textarena.envs.JoJoJoin.env:JoJoJoinEnv", mdp_wrappers=BOARD_MDP)

# UltimateTexasHoldem [1 Player]
register_with_versions(id="UltimateTexasHoldem-v0", entry_point="textarena.envs.UltimateTexasHoldem.env:UltimateTexasHoldemEnv", mdp_wrappers=BOARD_MDP, max_turns = 1000, start_chips = 1000, ante_amount = 25)
