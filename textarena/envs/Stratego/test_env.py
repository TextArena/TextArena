"""Offline, deterministic tests for the Stratego environment.

The board is populated randomly (pinned via ``seed=42``). Because a full game is
impractical to script, we compute legal moves by inspecting ``env.board`` and we
set up a guaranteed flag-capture by placing a piece next to the opponent's flag.
Manipulating the runtime board/state from a test is fine; we never edit env code.
"""

import re
from collections import Counter

from textarena.envs.Stratego.env import StrategoEnv


def _fresh():
    env = StrategoEnv()
    env.reset(num_players=2, seed=42)
    return env


def _coord(r, c):
    return f"{chr(r + 65)}{c}"


def _find_move_to_empty(env, player_id):
    """Return (sr, sc, dr, dc) for a movable piece stepping onto an empty cell."""
    for r in range(10):
        for c in range(10):
            piece = env.board[r][c]
            if isinstance(piece, dict) and piece["player"] == player_id and piece["rank"].lower() not in ("bomb", "flag"):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 10 and 0 <= nc < 10 and (nr, nc) not in env.lakes and env.board[nr][nc] is None:
                        return (r, c, nr, nc)
    return None


def _clear(env):
    for r in range(10):
        for c in range(10):
            env.board[r][c] = "~" if (r, c) in env.lakes else None
    env.player_pieces[0].clear()
    env.player_pieces[1].clear()


def _place(env, player, rank, position, piece_id):
    r, c = position
    env.board[r][c] = {"rank": rank, "player": player, "id": piece_id}
    env.player_pieces[player].append(position)


def test_reset_board_dimensions():
    env = _fresh()
    assert len(env.board) == 10 and all(len(row) == 10 for row in env.board)
    # Both players have their full set of pieces placed.
    total = sum(env.piece_counts.values())
    assert len(env.player_pieces[0]) == total
    assert len(env.player_pieces[1]) == total
    assert env.state.current_player_id == 0


def test_reset_has_exact_piece_inventory_and_is_seeded():
    first = _fresh()
    second = _fresh()
    for player in (0, 1):
        ranks = Counter(
            first.board[r][c]["rank"]
            for r, c in first.player_pieces[player]
        )
        assert ranks == Counter(first.piece_counts)
    assert first.board == second.board
    assert first.player_pieces == second.player_pieces


def test_cached_and_opponent_views_do_not_leak_hidden_ranks():
    env = _fresh()
    abbreviations = ("FL", "BM", "SP", "SC", "MN", "SG", "LT", "CP", "MJ", "CL", "GN", "MS")
    assert not any(token in env.state.game_state["rendered_board"].upper() for token in abbreviations)

    opponent_flag = next(
        (r, c)
        for r, c in env.player_pieces[1]
        if env.board[r][c]["rank"] == "Flag"
    )
    rendered = env._render_board(player_id=0, full_board=False).splitlines()
    row_text = rendered[opponent_flag[0] + 1]
    cell = row_text[3 + opponent_flag[1] * 4: 7 + opponent_flag[1] * 4]
    assert "?" in cell and "FL" not in cell


def test_generated_moves_are_parser_accepted():
    env = _fresh()
    moves = env._available_moves(0)
    assert moves
    assert all(re.search(env.action_pattern, move) is not None for move in moves)


def test_bad_format_is_invalid():
    env = _fresh()
    done = env.step("move my piece forward")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_format_error_describes_expected_action():
    env = _fresh()
    env.step("move my piece forward")
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice

    example = re.search(r"for example '([^']+)'", env.action_format).group(1)
    assert re.search(env.action_pattern, example)
    # The random setup fills both A0 and B0 with Player 0's pieces, so stage a position where the example is legal.
    staged = _fresh()
    _clear(staged)
    _place(staged, 0, "Captain", (0, 0), "captain-0")
    _place(staged, 1, "Captain", (9, 9), "captain-1")
    done = staged.step(example)
    assert not done and staged.state.turn == 1 and staged.state.error_count == 0


def test_moving_empty_or_enemy_source_rejected():
    # Find a cell owned by the opponent (player 1) and try to move it as player 0.
    env = _fresh()
    src = None
    for r in range(10):
        for c in range(10):
            p = env.board[r][c]
            if isinstance(p, dict) and p["player"] == 1 and p["rank"].lower() not in ("bomb", "flag"):
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 10 and 0 <= nc < 10 and (nr, nc) not in env.lakes and env.board[nr][nc] is None:
                        src = (r, c, nr, nc)
                        break
            if src:
                break
        if src:
            break
    assert src is not None
    r, c, nr, nc = src
    done = env.step(f"{_coord(r, c)} {_coord(nr, nc)}")
    assert not done
    assert env.state.error_count == 1


def test_valid_move_updates_board_and_rotates():
    env = _fresh()
    mv = _find_move_to_empty(env, 0)
    assert mv is not None
    r, c, nr, nc = mv
    done = env.step(f"{_coord(r, c)} {_coord(nr, nc)}")
    assert not done
    assert env.board[r][c] is None
    assert isinstance(env.board[nr][nc], dict) and env.board[nr][nc]["player"] == 0
    assert env.state.current_player_id == 1


def test_capturing_flag_wins():
    env = _fresh()
    # Locate the opponent's flag.
    flag = None
    for r in range(10):
        for c in range(10):
            p = env.board[r][c]
            if isinstance(p, dict) and p["player"] == 1 and p["rank"] == "Flag":
                flag = (r, c)
    assert flag is not None
    fr, fc = flag
    # Choose an adjacent, in-bounds, non-lake cell to launch the attack from.
    adj = None
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ar, ac = fr + dr, fc + dc
        if 0 <= ar < 10 and 0 <= ac < 10 and (ar, ac) not in env.lakes:
            adj = (ar, ac)
            break
    assert adj is not None
    ar, ac = adj
    # Place a player-0 Miner adjacent to the flag (clean up any existing piece there).
    for pid in (0, 1):
        if (ar, ac) in env.player_pieces[pid]:
            env.player_pieces[pid].remove((ar, ac))
    env.board[ar][ac] = {"rank": "Miner", "player": 0}
    env.player_pieces[0].append((ar, ac))

    done = env.step(f"{_coord(ar, ac)} {_coord(fr, fc)}")
    assert done
    assert env.state.rewards == {0: 1, 1: -1}
    assert "?" not in env.render(1)
    assert env.render(1).endswith("Available Moves: ")


def test_miner_defuses_bomb_and_piece_lists_stay_synchronised():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Miner", (3, 0), "miner")
    _place(env, 1, "Bomb", (3, 1), "bomb")
    done = env.step("D0 D1")
    assert done
    assert env.board[3][0] is None
    assert env.board[3][1]["rank"] == "Miner"
    assert env.player_pieces[0] == [(3, 1)]
    assert env.player_pieces[1] == []


def test_spy_beats_attacking_marshal_but_equal_ranks_remove_both():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Spy", (3, 0), "spy")
    _place(env, 1, "Marshal", (3, 1), "marshal")
    done = env.step("D0 D1")
    assert done
    assert env.board[3][1]["rank"] == "Spy"
    battle = {to: m for _, m, _, to in env.state.events if "The attacking piece was Spy" in m}
    assert battle[0].endswith("As the attacker is a spy and the destination is a marshal, you won the battle.")
    assert battle[1].endswith("As the attacker is a spy and the destination is a marshal, you lost the battle.")

    env = _fresh()
    _clear(env)
    _place(env, 0, "Captain", (3, 0), "captain-0")
    _place(env, 1, "Captain", (3, 1), "captain-1")
    done = env.step("D0 D1")
    assert done
    assert env.board[3][0] is None and env.board[3][1] is None
    assert env.player_pieces == {0: [], 1: []}


def test_scout_cannot_jump_a_piece_or_lake():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Scout", (3, 0), "scout")
    _place(env, 0, "Miner", (3, 2), "blocker")
    assert env._validate_move(0, 3, 0, 3, 3) is not None
    assert env._validate_move(0, 3, 0, 4, 2) is not None  # diagonal/lake


def test_invalid_move_reasons_name_the_rule_that_was_broken():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Flag", (1, 0), "flag")
    _place(env, 0, "Bomb", (2, 0), "bomb")
    _place(env, 0, "Scout", (4, 0), "scout")
    _place(env, 0, "Scout", (3, 6), "scout-2")
    _place(env, 0, "Captain", (2, 8), "captain")
    # Only Scouts move further than one square, and nothing moves diagonally.
    one_step = "Pieces move one square up, down, left or right; only scouts may move further, in a straight line."
    assert env._validate_move(0, 2, 8, 3, 9) == one_step
    assert env._validate_move(0, 2, 8, 4, 8) == one_step
    # Bombs and Flags never move, whatever the destination.
    assert env._validate_move(0, 2, 0, 2, 2) == "Player 0 cannot move a bomb or flag."
    assert env._validate_move(0, 2, 0, 1, 0) == "Player 0 cannot move a bomb or flag."
    assert env._validate_move(0, 1, 0, 3, 0) == "Player 0 cannot move a bomb or flag."
    # A Scout run across a lake is blocked by the lake, not by a piece.
    assert env._validate_move(0, 4, 0, 4, 3) == "Player 0 cannot move into the lake."
    assert env._validate_move(0, 3, 6, 6, 6) == "Player 0 cannot move into the lake."
    assert env._validate_move(0, 4, 0, 4, 9) == "Player 0 cannot move into the lake."
    assert env._validate_move(0, 3, 6, 3, 4) is None
    _place(env, 0, "Miner", (3, 5), "blocker-2")
    assert env._validate_move(0, 3, 6, 3, 4) == "Player 0 cannot move a scout through other pieces."


def test_two_square_repetition_rule_blocks_fourth_traversal():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Miner", (3, 0), "miner")
    env.state.game_state["move_history"]["miner"] = [
        ((3, 0), (4, 0)),
        ((4, 0), (3, 0)),
        ((3, 0), (4, 0)),
    ]
    assert env._validate_move(0, 3, 0, 4, 0) is not None
    assert "D0 E0" not in env._available_moves(0)


def test_moving_another_piece_interrupts_two_square_sequence():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Miner", (3, 0), "miner")
    _place(env, 0, "Miner", (3, 4), "other")
    _place(env, 1, "Miner", (6, 0), "opponent")
    env.game_state["move_history"]["miner"] = [
        ((3, 0), (4, 0)),
        ((4, 0), (3, 0)),
        ((3, 0), (4, 0)),
    ]
    env.game_state["last_moved_piece"][0] = "miner"

    done = env.step("D4 E4")
    assert not done
    assert env._validate_move(0, 3, 0, 4, 0) is None
    assert "D0 E0" in env._available_moves(0)


def test_turn_limit_draw_reveals_terminal_board():
    env = StrategoEnv(max_turns=1)
    env.reset(num_players=2, seed=42)
    done = env.step(env._available_moves(0)[0])
    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert any(token in env.state.game_state["rendered_board"].upper() for token in ("FL", "BM"))


def test_invalid_forfeit_reveals_cached_terminal_board():
    env = _fresh()
    env.step("garbage")
    done = env.step("garbage")
    assert done
    assert "?" not in env.game_state["rendered_board"]


def test_trade_of_the_last_movable_pieces_is_a_draw():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Captain", (3, 0), "captain-0")
    _place(env, 1, "Captain", (3, 1), "captain-1")
    _place(env, 0, "Flag", (0, 0), "flag-0")
    _place(env, 1, "Flag", (9, 9), "flag-1")

    done = env.step("D0 D1")

    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert "Neither player has a movable piece left" in env.state.game_info[0]["reason"]


def test_losing_your_last_movable_piece_loses_while_the_opponent_can_move():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Scout", (3, 0), "scout")
    _place(env, 1, "Bomb", (3, 1), "bomb")
    _place(env, 1, "Miner", (8, 8), "miner")
    _place(env, 0, "Flag", (0, 0), "flag-0")

    done = env.step("D0 D1")

    assert done
    assert env.state.rewards == {0: -1, 1: 1}


def test_blocked_opponent_loses_even_if_the_mover_cannot_move_again():
    env = _fresh()
    _clear(env)
    _place(env, 0, "Scout", (3, 0), "scout")
    _place(env, 1, "Bomb", (3, 1), "bomb")
    _place(env, 0, "Flag", (0, 0), "flag-0")
    # Player 1's only movable piece is boxed in by its own bombs and the board corner.
    _place(env, 1, "Miner", (9, 9), "miner")
    _place(env, 1, "Bomb", (8, 9), "bomb-2")
    _place(env, 1, "Bomb", (9, 8), "bomb-3")

    done = env.step("D0 D1")

    assert done
    assert env.state.rewards == {0: 1, 1: -1}


def test_prompt_lists_ranks_scout_movement_and_end_conditions():
    env = StrategoEnv(max_turns=321)
    env.reset(num_players=2, seed=0)

    prompt = env.prompt(1)

    for entry in ("MS Marshal (10) x1", "CP Captain (6) x4", "SC Scout (2) x8", "SP Spy (1) x1", "BM Bomb x6", "FL Flag x1"):
        assert entry in prompt
    assert "Scouts may instead move any number of empty squares in a straight line" in prompt
    assert "more than three turns in a row" in prompt
    assert "draw after 321 turns" in prompt
    assert not prompt.rstrip().endswith("board state:")
