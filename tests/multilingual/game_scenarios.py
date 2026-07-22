"""Per-game deterministic action scripts for golden verification.

Each game's scenarios are hand-authored to exercise every localized message
branch (prompt, board, each invalid-move reason, win, draw). When adding a game,
design scenarios so that every self.m()/self.t() key is reachable — otherwise a
per-language slot bug in an unexercised branch would go unseen by the golden
(check_locales.py still catches structural problems statically).
"""

GAMES = {
    "WildTicTacToe": {
        "entry": "textarena.envs.WildTicTacToe.env:WildTicTacToeEnv",
        "num_players": 2,
        "seed": 42,
        "scenarios": {
            "win_top_row":      ["[X 0]", "[O 3]", "[X 1]", "[O 4]", "[X 2]"],
            "draw":             ["[X 0]", "[O 1]", "[X 2]", "[X 3]", "[O 4]",
                                 "[O 5]", "[O 6]", "[X 7]", "[X 8]"],
            "wrong_format":     ["not a move", "[X 0]", "[O 3]", "[X 1]", "[O 4]", "[X 2]"],
            "out_of_range":     ["[X 99]", "[X 0]", "[O 3]", "[X 1]", "[O 4]", "[X 2]"],
            "already_occupied": ["[X 0]", "[O 0]", "[O 3]", "[X 1]", "[O 4]", "[X 2]"],
        },
    },
    "ReverseTicTacToe": {
        "entry": "textarena.envs.ReverseTicTacToe.env:ReverseTicTacToeEnv",
        "num_players": 2,
        "seed": 42,
        "scenarios": {
            # P0='O', P1='X'. In misere play, completing a line loses.
            "lose_by_line":     ["[0]", "[3]", "[1]", "[4]", "[2]"],
            "draw":             ["[0]", "[2]", "[1]", "[3]", "[5]", "[4]", "[6]", "[7]", "[8]"],
            "wrong_format":     ["bad", "[0]", "[3]", "[1]", "[4]", "[2]"],
            "invalid_cell":     ["[99]", "[0]", "[3]", "[1]", "[4]", "[2]"],
            "already_occupied": ["[0]", "[0]", "[3]", "[1]", "[4]", "[2]"],
        },
    },
    "ThreePlayerTicTacToe": {
        "entry": "textarena.envs.ThreePlayerTicTacToe.env:ThreePlayerTicTacToeEnv",
        "num_players": 3,
        "seed": 42,
        # 5x5 board (cells 0-24), symbols A=P0 B=P1 C=P2, win = 4 in a row.
        # error_allowance=1 -> a player must err twice in a row to be eliminated.
        # NOTE: no natural 25-cell draw scenario (too error-prone to hand-build
        # for 3 symbols / win-4); the 'draw' key is covered by check_locales only.
        "scenarios": {
            "win_row":          ["[0]", "[10]", "[20]", "[1]", "[11]", "[21]",
                                 "[2]", "[12]", "[22]", "[3]"],
            "out_of_range":     ["[99]", "[0]", "[10]", "[20]", "[1]", "[11]", "[21]",
                                 "[2]", "[12]", "[22]", "[3]"],
            "already_occupied": ["[0]", "[0]", "[10]", "[20]", "[1]", "[11]", "[21]",
                                 "[2]", "[12]", "[22]", "[3]"],
            "invalid_twice_eliminated": ["bad", "also bad"],
        },
    },
    "UltimateTicTacToe": {
        "entry": "textarena.envs.UltimateTicTacToe.env:UltimateTicTacToeEnv",
        "num_players": 2,
        "seed": 42,
        # P0='O', P1='X'. Move = [macro micro]; each move forces the opponent's
        # next micro-board. Win/draw require conquering aligned micro-boards and
        # are impractical to hand-script here; those keys (+ the unreachable
        # in-range recheck and the 'any micro board' free-move phrasing) are
        # covered structurally by check_locales.
        "scenarios": {
            "valid_play":       ["[4 0]", "[0 4]", "[4 8]", "[8 4]"],
            "wrong_format":     ["bad", "[4 0]"],
            "indices_out_of_range": ["[9 0]", "[4 0]"],
            "must_play_next":   ["[4 0]", "[1 0]", "[0 0]"],
            "already_occupied": ["[4 0]", "[0 0]", "[0 0]"],
        },
    },
    "IteratedMatchingPennies": {
        "entry": "textarena.envs.IteratedMatchingPennies.env:IteratedMatchingPenniesEnv",
        "num_players": 2,
        "seed": 42,
        # 5 rounds (odd) -> a numeric draw is impossible; 'outcome.draw' is covered
        # by check_locales only. Each round: P0 then P1 submit.
        "scenarios": {
            "p0_sweep_match": ["[heads]", "[heads]"] * 5,
            "p1_sweep_mismatch_with_invalid":
                ["bad"] + ["[heads]", "[tails]"] * 5,
        },
    },
}
