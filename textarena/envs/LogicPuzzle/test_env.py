"""Deterministic offline tests for Logic Puzzle.

Single-player grid deduction game. The puzzle is chosen randomly, but the full
solution is stored on the env (``game_board_solution``). We read it and submit
the correct marks to solve the puzzle (reward 1). Marks use the bare format
``row col X|O`` and several may be submitted in one action.
"""
import copy
import random

import pytest

from textarena.envs.LogicPuzzle.env import LogicPuzzleEnv


def _fresh():
    env = LogicPuzzleEnv(difficulty="easy", max_turns=30)
    env.reset(num_players=1, seed=42)
    return env


def _solution_tokens(env):
    tokens = []
    for grid in env.game_board_solution.values():
        for row, cols in grid.items():
            for col, mark in cols.items():
                tokens.append(f"{row} {col} {mark}")
    return tokens


def test_reset_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert env.state.game_state["board"] is not None
    assert env.game_board_solution


def test_solve_in_one_action():
    env = _fresh()
    action = ", ".join(_solution_tokens(env))
    done, _ = env.step(action)
    assert done is True
    assert env.state.rewards == {0: 1}


def test_invalid_format():
    env = _fresh()
    done, _ = env.step("I have no idea")
    assert done is False
    assert env.state.error_count == 1


def test_out_of_bounds_rejected():
    env = _fresh()
    done, _ = env.step("nobody nowhere O")
    assert done is False
    assert env.state.error_count == 1


def test_repeated_mark_rejected():
    env = _fresh()
    token = _solution_tokens(env)[0]
    done, _ = env.step(token)  # first mark: valid
    assert done is False
    done, _ = env.step(token)  # same mark again: repeated -> invalid
    assert done is False
    assert env.state.error_count == 1


def test_single_valid_mark_progresses():
    env = _fresh()
    token = _solution_tokens(env)[0]
    done, _ = env.step(token)
    assert done is False
    assert env.state.error_count == 0


@pytest.mark.parametrize("seed", range(20))
def test_seeded_puzzle_boards_are_well_formed_and_deterministic(seed):
    first = LogicPuzzleEnv(difficulty="easy")
    second = LogicPuzzleEnv(difficulty="easy")
    first.reset(num_players=1, seed=seed)
    second.reset(num_players=1, seed=seed)
    assert first.game_state == second.game_state
    assert first.game_board.keys() == first.game_board_solution.keys()
    for grid_name, grid in first.game_board_solution.items():
        assert grid
        columns = None
        for row in grid.values():
            columns = set(row) if columns is None else columns
            assert set(row) == columns
            assert list(row.values()).count("O") == 1


def test_packaged_clues_match_their_declared_solutions():
    easy_records = LogicPuzzleEnv(difficulty="easy").game_board_data
    hard_records = LogicPuzzleEnv(difficulty="hard").game_board_data
    all_clues = {
        clue
        for record in easy_records + hard_records
        for clue in record["clue"]
    }
    assert "The green car uses electric fuel." in all_clues
    assert "If Alice does not drink soda, then Charlie must eat a salad." in all_clues
    assert "If Wednesday is Alice's day, then Charlie plays on Tuesday." in all_clues
    assert "Charlie plays on Tuesday only if Alice is playing soccer." in all_clues
    assert "The green car uses diesel fuel." not in all_clues
    assert "If Alice does not drink soda, then Charlie cannot eat a salad." not in all_clues
    assert "If Wednesday is Alice's day, then Charlie does not play on Tuesday." not in all_clues
    assert "Charlie plays on Tuesday only if Alice is not playing soccer." not in all_clues


def test_reset_does_not_consume_global_rng():
    random.seed(818)
    expected = random.getstate()
    env = LogicPuzzleEnv()
    env.reset(num_players=1, seed=99)
    assert random.getstate() == expected


def test_invalid_later_batch_mark_is_atomic():
    env = _fresh()
    before = copy.deepcopy(env.game_board)
    valid = _solution_tokens(env)[0]
    done, _ = env.step(f"{valid}, nobody nowhere X")
    assert not done
    assert env.state.error_count == 1
    assert env.game_board == before
    assert env.state.turn == 0


@pytest.mark.parametrize(
    "action",
    [
        "please alice home O",
        "alice home O thanks",
        "[alice home O",
        "alice home O]",
        "alice home O,",
        "alice home OO",
        "",
    ],
)
def test_exact_parser_rejects_malformed_input_without_marks(action):
    env = _fresh()
    before = copy.deepcopy(env.game_board)
    done, _ = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.game_board == before


def test_duplicate_within_batch_is_atomic():
    env = _fresh()
    token = _solution_tokens(env)[0]
    before = copy.deepcopy(env.game_board)
    done, _ = env.step(f"{token}, {token}")
    assert not done
    assert env.state.error_count == 1
    assert env.game_board == before


def test_oversized_action_is_invalid_without_marks():
    env = _fresh()
    before = copy.deepcopy(env.game_board)
    done, _ = env.step("x" * (env.max_action_chars + 1))
    assert not done
    assert env.state.error_count == 1
    assert env.game_board == before


def test_turn_limit_scores_only_correct_marks():
    env = LogicPuzzleEnv(difficulty="easy", max_turns=1)
    env.reset(num_players=1, seed=42)
    row, col, expected = _solution_tokens(env)[0].split()
    wrong = "X" if expected == "O" else "O"
    done, _ = env.step(f"{row} {col} {wrong}")
    assert done
    assert env.state.rewards == {0: 0.0}
    assert "turn limit" in env.state.game_info[0]["reason"].lower()


def test_snapshot_restore_recovers_board_alias_and_marks():
    env = _fresh()
    snapshot = env.snapshot()
    token = _solution_tokens(env)[0]
    env.step(token)
    assert env._get_percentage_completion() > 0
    env.restore(snapshot)
    assert env._get_percentage_completion() == 0.0
    assert env.game_board is env.game_state["board"]


def test_current_and_terminal_render_include_board_and_clues():
    env = _fresh()
    current = env.render(0)
    assert "Current Board" in current
    assert "Available Clues" in current
    done, _ = env.step(", ".join(_solution_tokens(env)))
    assert done
    terminal = env.render(0)
    assert "O" in terminal and "X" in terminal
    assert env.get_board_str()


def test_loader_preserves_value_errors_for_bad_data(tmp_path):
    bad_json = tmp_path / "bad.jsonl"
    bad_json.write_text("{bad json}\n", encoding="utf-8")
    env = LogicPuzzleEnv()
    with pytest.raises(ValueError, match="Invalid JSON"):
        env._load_puzzle_data(str(bad_json))

    no_match = tmp_path / "no-match.jsonl"
    no_match.write_text(
        '{"difficulty": "other", "solution": {}, "clue": []}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="No puzzles"):
        env._load_puzzle_data(str(no_match))

    malformed_puzzle = tmp_path / "malformed-puzzle.jsonl"
    malformed_puzzle.write_text(
        '{"difficulty":"easy","solution":{"people":["Alice","Bob"],'
        '"places":["new york","park"]},"clue":["A clue."]}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="parser-incompatible"):
        env._load_puzzle_data(str(malformed_puzzle))


@pytest.mark.parametrize(
    "kwargs",
    [{"difficulty": "unknown"}, {"difficulty": ""}, {"max_turns": 0}],
)
def test_invalid_configuration_or_difficulty_rejected(kwargs):
    with pytest.raises(ValueError):
        LogicPuzzleEnv(**kwargs)
