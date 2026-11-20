import textarena as ta
from textarena.envs.PegJump.env import PegJumpEnv


def _hole(row, col):
    # holes are numbered row by row: 1 / 2 3 / 4 5 6 / 7 8 9 10 / 11 12 13 14 15
    return row * (row + 1) // 2 + col + 1


def _real_jumps():
    jumps = set()
    for row in range(5):
        for col in range(row + 1):
            for d_row, d_col in ((0, 1), (1, 0), (1, 1)):  # along a row, and down both diagonals
                if col + 2 * d_col <= row + 2 * d_row <= 4:
                    a = _hole(row, col)
                    b = _hole(row + d_row, col + d_col)
                    c = _hole(row + 2 * d_row, col + 2 * d_col)
                    jumps.update({(a, b, c), (c, b, a)})
    return jumps


def _new_game():
    env = ta.make("PegJump-v0")  # hole 5 starts empty
    env.reset(num_players=1, seed=0)
    return env


def test_allowed_moves_are_the_straight_line_jumps():
    assert set(PegJumpEnv().ALLOWED_MOVES) == _real_jumps()
    assert len(_real_jumps()) == 36


def test_jump_that_is_not_a_straight_line_is_rejected():
    env = _new_game()
    env.step("[14 5]")  # 14 over 9 into 5
    board = list(env.state.game_state["board"])
    done, _ = env.step("[8 14]")  # 8, 12 and 14 are not in a line
    assert not done
    assert env.state.game_state["board"] == board
    assert env.state.error_count == 1


def test_bottom_row_jump_is_allowed():
    env = _new_game()
    env.step("[14 5]")
    done, _ = env.step("[12 14]")  # 12 over 13 into 14, along the bottom row
    assert not done
    board = env.state.game_state["board"]
    assert not board[12] and not board[13] and board[14]
    assert env.state.error_count == 0


def test_game_does_not_end_while_a_bottom_row_jump_is_left():
    env = _new_game()
    board = [False] * 16
    board[4] = board[7] = board[12] = True
    env.state.game_state["board"] = board
    done, _ = env.step("[4 11]")  # leaves pegs on 11 and 12, so 11 over 12 into 13 is still possible
    assert not done
    done, _ = env.step("[11 13]")
    assert done
    rewards, _ = env.close()
    assert rewards == {0: 1.0}
