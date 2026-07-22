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
    "IteratedTwoThirdsAverage": {
        "entry": "textarena.envs.IteratedTwoThirdsAverage.env:IteratedTwoThirdsAverageEnv",
        "num_players": 2,
        "seed": 42,
        "scenarios": {
            "mixed_with_invalids": ["abc", "[0]", "[150]", "[60]", "[60]", "[60]",
                                    "[60]", "[0]", "[0]", "[60]", "[60]", "[60]"],
            "overall_draw": ["[0]", "[60]", "[60]", "[0]", "[60]", "[60]",
                             "[60]", "[60]", "[60]", "[60]"],
        },
    },
    "Cryptarithm": {
        "entry": "textarena.envs.Cryptarithm.env:CryptarithmEnv",
        "num_players": 1,
        "seed": 42,
        # Default puzzle SEND + MORE = MONEY. error_allowance=1: interleave each
        # invalid with a valid move so the episode doesn't end on a 2nd error.
        "scenarios": {
            "solve":              ["[S 9]", "[E 5]", "[N 6]", "[D 7]", "[M 1]", "[O 0]", "[R 8]", "[Y 2]"],
            "incorrect_complete": ["[S 1]", "[E 2]", "[N 3]", "[D 4]", "[M 5]", "[O 6]", "[R 7]", "[Y 8]"],
            "invalids":           ["garbage", "[S 9]", "[Z 1]", "[E 5]", "[M 0]", "[N 6]", "[E 9]"],
        },
    },
    "IteratedRockPaperScissors": {
        "entry": "textarena.envs.IteratedRockPaperScissors.env:IteratedRockPaperScissorsEnv",
        "num_players": 2,
        "seed": 42,
        "scenarios": {
            # R1 P0 win, R2 draw, R3 P1 win, R4 P0 win, R5 draw -> P0 wins overall.
            "mixed_with_invalid": ["bad", "[rock]", "[scissors]", "[rock]", "[rock]",
                                   "[scissors]", "[rock]", "[rock]", "[scissors]", "[rock]", "[rock]"],
            # 1 P0 win, 1 P1 win, 3 draws -> overall draw.
            "overall_draw": ["[rock]", "[scissors]", "[scissors]", "[rock]",
                             "[rock]", "[rock]", "[rock]", "[rock]", "[rock]", "[rock]"],
        },
    },
    "HighSociety": {
        "entry": "textarena.envs.HighSociety.env:HighSocietyEnv",
        "num_players": 2,
        "seed": 42,
        # First bidder alternates each auction (P0,P1,P0,...). Loser keeps their
        # money card, so P1 can bid [1] every auction and P0 wins with distinct
        # cards 2..11. Draw is unreachable deterministically -> check_locales only.
        "scenarios": {
            "p0_sweeps_10_auctions": ["[2]", "[1]", "[1]", "[3]", "[4]", "[1]", "[1]", "[5]",
                                      "[6]", "[1]", "[1]", "[7]", "[8]", "[1]", "[1]", "[9]",
                                      "[10]", "[1]", "[1]", "[11]"],
            "tie_and_invalids": ["bad", "[5]", "[5]", "[6]", "[3]", "[1]", "[6]", "[7]"],
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
