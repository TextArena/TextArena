"""Deterministic offline tests for the MemoryGame environment."""
import copy
from collections import Counter, defaultdict

import pytest

import textarena as ta
from textarena.envs.MemoryGame.env import MemoryGameEnv


def _fresh(grid_size=2):
    env = MemoryGameEnv(grid_size=grid_size)
    env.reset(num_players=2, seed=42)
    return env


def _pairs(env):
    """Map each symbol -> its two (row, col) positions from the hidden board."""
    pos = defaultdict(list)
    board = env.state.game_state["board"]
    for r in range(env.grid_size):
        for c in range(env.grid_size):
            pos[board[r][c]].append((r, c))
    return pos


def test_single_player_wins_all_pairs():
    env = _fresh(grid_size=2)  # 2x2 -> exactly two pairs
    pairs = list(_pairs(env).values())
    done = False
    for (r1, c1), (r2, c2) in pairs:
        # Matching keeps the same player on turn (rotate_player=False).
        assert env.state.current_player_id == 0
        done, _ = env.step(f"{r1} {c1} {r2} {c2}")
    assert done
    assert env.state.game_state["score"] == {0: 2, 1: 0}
    assert env.state.rewards == {0: 1, 1: -1}


def test_mismatch_rotates_player():
    env = _fresh(grid_size=2)
    board = env.state.game_state["board"]
    s0 = board[0][0]
    # Find a differently-symboled cell to guarantee a mismatch.
    target = next(
        (r, c)
        for r in range(2)
        for c in range(2)
        if (r, c) != (0, 0) and board[r][c] != s0
    )
    done, _ = env.step(f"0 0 {target[0]} {target[1]}")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["score"] == {0: 0, 1: 0}


def test_invalid_format_increments_error():
    env = _fresh()
    done, _ = env.step("flip some cards")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


def test_out_of_bounds_rejected():
    env = _fresh(grid_size=2)
    done, _ = env.step("0 0 5 5")
    assert not done
    assert env.state.error_count == 1


def test_same_card_twice_rejected():
    env = _fresh(grid_size=2)
    done, _ = env.step("0 0 0 0")
    assert not done
    assert env.state.error_count == 1


@pytest.mark.parametrize("grid_size", (0, 1, 3, -2, 2.0, True, None))
def test_invalid_grid_sizes_are_rejected(grid_size):
    with pytest.raises(ValueError):
        MemoryGameEnv(grid_size=grid_size)


def test_grid_size_resource_limit_is_enforced():
    env = MemoryGameEnv(grid_size=MemoryGameEnv.MAX_GRID_SIZE)
    env.reset(num_players=2, seed=42)
    assert len(env.state.game_state["board"]) == MemoryGameEnv.MAX_GRID_SIZE

    with pytest.raises(ValueError, match="cannot exceed"):
        MemoryGameEnv(grid_size=MemoryGameEnv.MAX_GRID_SIZE + 2)


@pytest.mark.parametrize("max_turns", (0, -1, 1.5, True))
def test_invalid_turn_limits_are_rejected(max_turns):
    with pytest.raises(ValueError):
        MemoryGameEnv(grid_size=2, max_turns=max_turns)


@pytest.mark.parametrize("action", ("[0 0 0 1", "0 0 0 1]"))
def test_unbalanced_brackets_are_atomic_invalid_moves(action):
    env = _fresh(grid_size=2)
    before = copy.deepcopy(env.state.game_state)

    done, _ = env.step(action)

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


def test_huge_coordinate_is_rejected_without_integer_conversion(monkeypatch):
    import textarena.envs.MemoryGame.env as memory_module

    env = _fresh(grid_size=2)
    before = copy.deepcopy(env.state.game_state)
    real_int = int

    def guarded_int(text):
        if isinstance(text, str) and len(text) > 1:
            pytest.fail("attempted to convert an unbounded coordinate")
        return real_int(text)

    monkeypatch.setattr(memory_module, "int", guarded_int, raising=False)

    done, _ = env.step(f"{'9' * 100_000} 0 0 1")

    assert not done
    assert env.state.error_count == 1
    assert env.state.game_state == before


def test_hard_configuration_uses_readable_pair_labels():
    env = _fresh(grid_size=8)
    counts = Counter(cell for row in env.state.game_state["board"] for cell in row)

    assert len(counts) == 32
    assert set(counts.values()) == {2}
    assert all(label.isascii() and label.isalpha() for label in counts)
    assert "AA" in counts


def test_many_seeds_are_reproducible_and_well_formed():
    layouts = set()
    for seed in range(32):
        first = MemoryGameEnv(grid_size=8)
        second = MemoryGameEnv(grid_size=8)
        first.reset(num_players=2, seed=seed)
        second.reset(num_players=2, seed=seed)

        first_board = first.state.game_state["board"]
        assert first_board == second.state.game_state["board"]
        counts = Counter(cell for row in first_board for cell in row)
        assert len(counts) == 32
        assert set(counts.values()) == {2}
        layouts.add(tuple(cell for row in first_board for cell in row))

    assert len(layouts) == 32


def test_public_renderers_keep_unmatched_cards_secret():
    env = _fresh(grid_size=2)
    symbols = set(cell for row in env.state.game_state["board"] for cell in row)

    text_board = env._render_board()
    rich_board = env.get_board_str()

    assert all(symbol not in text_board for symbol in symbols)
    assert all(symbol not in rich_board for symbol in symbols)
    assert rich_board.count("🔲") == 4


def test_rich_renderer_reveals_only_matched_cards():
    env = _fresh(grid_size=2)
    (r1, c1), (r2, c2) = next(iter(_pairs(env).values()))
    symbol = env.state.game_state["board"][r1][c1]

    done, _ = env.step(f"[{r1} {c1} {r2} {c2}]")
    rich_board = env.get_board_str()

    assert not done
    assert rich_board.count("🔲") == 2
    assert rich_board.count(symbol) == 2


def test_selecting_a_matched_card_is_atomic():
    env = _fresh(grid_size=2)
    pairs = list(_pairs(env).values())
    (r1, c1), (r2, c2) = pairs[0]
    env.step(f"{r1} {c1} {r2} {c2}")
    before = copy.deepcopy(env.state.game_state)
    other = pairs[1][0]

    done, _ = env.step(f"{r1} {c1} {other[0]} {other[1]}")

    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0
    assert env.state.game_state == before


def test_completion_can_end_in_a_draw_and_renders_all_cards():
    env = MemoryGameEnv(grid_size=4)
    env.reset(num_players=2, seed=42)
    pairs = list(_pairs(env).values())
    final_pair = pairs[-1]
    gs = env.state.game_state
    gs["matched_positions"] = {
        position
        for pair in pairs[:-1]
        for position in pair
    }
    gs["score"] = {0: 4, 1: 3}
    gs["scores"] = {0: {"Score": 4}, 1: {"Score": 3}}
    env.state.current_player_id = 1
    (r1, c1), (r2, c2) = final_pair

    done, _ = env.step(f"{r1} {c1} {r2} {c2}")

    assert done
    assert env.state.rewards == {0: 0, 1: 0}
    assert gs["score"] == {0: 4, 1: 4}
    final_board = [
        message
        for _, message, event_type, _ in env.state.events
        if event_type == ta.ObservationType.GAME_BOARD
    ][-1]
    assert "." not in final_board.split("Current board:\n", 1)[1]


def test_exact_turn_limit_scores_a_win():
    env = MemoryGameEnv(grid_size=2, max_turns=1)
    env.reset(num_players=2, seed=42)
    board = env.state.game_state["board"]
    mismatch = next(
        (r, c)
        for r in range(2)
        for c in range(2)
        if board[r][c] != board[0][0]
    )
    env.state.game_state["score"] = {0: 1, 1: 0}

    done, _ = env.step(f"0 0 {mismatch[0]} {mismatch[1]}")

    assert done
    assert env.state.turn == 1
    assert env.state.rewards == {0: 1, 1: -1}


def test_exact_turn_limit_draws_tied_scores():
    env = MemoryGameEnv(grid_size=2, max_turns=1)
    env.reset(num_players=2, seed=42)
    board = env.state.game_state["board"]
    mismatch = next(
        (r, c)
        for r in range(2)
        for c in range(2)
        if board[r][c] != board[0][0]
    )

    done, _ = env.step(f"0 0 {mismatch[0]} {mismatch[1]}")

    assert done
    assert env.state.turn == 1
    assert env.state.rewards == {0: 0, 1: 0}


def test_seeded_reset_and_snapshot_restore_hidden_state():
    env = MemoryGameEnv(grid_size=4)
    env.reset(num_players=2, seed=17)
    first_board = copy.deepcopy(env.state.game_state["board"])
    snapshot = env.snapshot()
    pair = next(iter(_pairs(env).values()))
    env.step(f"{pair[0][0]} {pair[0][1]} {pair[1][0]} {pair[1][1]}")

    env.restore(snapshot)

    assert env.state.game_state["board"] == first_board
    assert env.state.game_state["matched_positions"] == set()
    assert env.state.current_player_id == 0
    env.reset(num_players=2, seed=17)
    assert env.state.game_state["board"] == first_board
