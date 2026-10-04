"""Deterministic game-logic tests for Crosswords (single player).

The puzzle/board is random per seed, so we read the hidden solution out of
``env.state.game_state`` to script guaranteed-correct guesses.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

import textarena as ta
from textarena.envs.Crosswords.env import CrosswordsEnv

GENERATOR_PATH = Path(__file__).resolve().parents[3] / "scripts" / "crosswords_clues.py"
needs_generator = pytest.mark.skipif(not GENERATOR_PATH.exists(), reason="scripts/ only exists in a source checkout")


def _load_generator():
    spec = importlib.util.spec_from_file_location("crosswords_clues", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh(num_words=3, hardcore=False, max_turns=100):
    env = CrosswordsEnv(num_words=num_words, hardcore=hardcore, max_turns=max_turns)
    env.reset(num_players=1, seed=42)
    return env


def _all_correct_actions(env):
    board = env.state.game_state["board"]
    solution = env.state.game_state["solution"]
    actions = []
    for r in range(len(board)):
        for c in range(len(board[0])):
            if board[r][c] == "_":
                actions.append(f"{r} {c} {solution[r][c]}")
    return actions


def _first_empty_cell(env):
    board = env.state.game_state["board"]
    for r in range(len(board)):
        for c in range(len(board[0])):
            if board[r][c] == "_":
                return r, c
    raise AssertionError("no empty cell found")


def test_completing_puzzle_wins():
    env = _fresh()
    done = False
    for action in _all_correct_actions(env):
        done, _ = env.step(action)
    assert done and env.state.rewards == {0: 1}
    assert env.state.turn == len(_all_correct_actions(_fresh()))


def test_single_correct_letter_fills_cell():
    env = _fresh()
    r, c = _first_empty_cell(env)
    letter = env.state.game_state["solution"][r][c]
    done, _ = env.step(f"{r} {c} {letter}")
    assert not done and env.state.game_state["board"][r][c] == letter.upper()


def test_invalid_format_increments_error_count():
    env = _fresh()
    done, _ = env.step("no valid guess here")
    assert not done and env.state.error_count == 1


def test_wrong_letter_rejected():
    env = _fresh()
    r, c = _first_empty_cell(env)
    correct = env.state.game_state["solution"][r][c].upper()
    wrong = "Z" if correct != "Z" else "Y"
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(f"{r} {c} {wrong}")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_out_of_bounds_cell_rejected():
    env = _fresh()
    done, _ = env.step("99 99 a")
    assert not done and env.state.error_count == 1


def test_oversized_coordinate_is_atomic_invalid():
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(f"{'9' * 1000} 0 A")
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_two_consecutive_invalid_moves_end_game():
    env = _fresh()
    env.step("garbage")
    done, _ = env.step("still garbage")
    assert done and env.state.game_info[0]["invalid_move"] is True


@pytest.mark.parametrize("action", ["[0 0 A", "0 0 A]", "0, 0, A", "0 0 AB", "0 0 A trailing"])
def test_parser_rejects_noncanonical_actions_atomically(action):
    env = _fresh()
    before = copy.deepcopy(env.state.game_state)
    done, _ = env.step(action)
    assert not done and env.state.error_count == 1
    assert env.state.game_state == before


def test_many_seeded_hardcore_boards_fit_turn_budget_and_place_every_word():
    for seed in range(100):
        env = CrosswordsEnv(hardcore=True, max_turns=30, num_words=3)
        env.reset(num_players=1, seed=seed)
        gs = env.state.game_state
        letter_cells = sum(cell != "." for row in gs["solution"] for cell in row)
        assert letter_cells <= env.max_turns
        assert len(gs["placed_words"]) == env.num_words
        assert set(gs["clues"]) == set(gs["placed_words"])


@pytest.mark.parametrize("env_id", ["Crosswords-v1", "Crosswords-v1-hardcore"])
def test_games_finish_within_max_turns_guesses(env_id):
    env = ta.make(env_id)
    env.reset(num_players=1, seed=5)
    game = env.unwrapped if hasattr(env, "unwrapped") else env
    while hasattr(game, "env"):
        game = game.env
    assert game.max_turns == game.state.max_turns == 30

    actions = _all_correct_actions(game)
    done = False
    for action in actions:
        assert not done
        done, _ = env.step("not a guess")  # an invalid move in between never counts as a turn
        assert not done
        done, _ = env.step(action)
    assert done and game.state.rewards == {0: 1}
    assert game.state.turn == len(actions) <= game.max_turns


@pytest.mark.parametrize(
    ("hardcore", "num_words", "seed"),
    [(False, 3, 4), (False, 5, 0), (True, 5, 309)],
)
def test_edge_budget_generation_always_places_unique_words(hardcore, num_words, seed):
    probe = CrosswordsEnv(hardcore=hardcore, num_words=1, max_turns=100)
    budget = sum(sorted(len(entry["word"]) for entry in probe.word_data)[:num_words])
    env = CrosswordsEnv(hardcore=hardcore, num_words=num_words, max_turns=budget)
    env.reset(num_players=1, seed=seed)

    gs = env.state.game_state
    letter_cells = sum(cell != "." for row in gs["solution"] for cell in row)
    assert len(gs["placed_words"]) == num_words
    assert len(set(gs["placed_words"])) == num_words
    assert letter_cells <= budget


def test_helpers_reject_bad_bounds_and_clues_match_placements():
    env = _fresh()
    grid = [["."] * 5 for _ in range(5)]
    assert not env._can_place_word(grid, "DOG", "across", -1, 0)
    assert not env._can_place_word(grid, "DOG", "down", 0, -1)
    assert not env._can_place_word(grid, "DOG", "diagonal", 0, 0)
    assert not env._can_place_word(grid, "DOG", "across", 0, 3)

    clue_lines = env._clue_generator(string_format=False)
    for index, (word, position) in enumerate(env.state.game_state["placed_words"].items()):
        assert env.state.game_state["clues"][word] in clue_lines[index]
        assert str(position) in clue_lines[index]


def test_renderer_shows_filled_letter_at_clue_start():
    env = _fresh()
    word, (row, col, _) = next(iter(env.state.game_state["placed_words"].items()))
    letter = env.state.game_state["solution"][row][col]
    env.step(f"{row} {col} {letter}")
    board_render = env.get_board_str()
    assert f" {letter} " in board_render
    assert word in env.state.game_state["clues"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"num_words": 1000},
        {"hardcore": True, "num_words": 3, "max_turns": 10},
    ],
)
def test_invalid_or_unplayable_configuration_rejected(kwargs):
    with pytest.raises(ValueError):
        CrosswordsEnv(**kwargs)


@needs_generator
def test_dataset_generator_is_seeded_offline_and_writes_expected_schema(monkeypatch, tmp_path):
    generator = _load_generator()

    pools = {
        False: ["alpha", "beta", "gamma", "delta"],
        True: ["epsilon", "zeta", "eta", "theta"],
    }
    monkeypatch.setattr(generator, "_usable_words", lambda hardcore: pools[hardcore])
    monkeypatch.setattr(
        generator,
        "get_clue_examples",
        lambda word, model: {"1": f"Clue for {word}"},
    )

    first_path = generator.main(num_words=2, output_path=tmp_path / "first.jsonl", seed=7)
    second_path = generator.main(num_words=2, output_path=tmp_path / "second.jsonl", seed=7)
    assert first_path.read_text(encoding="utf-8") == second_path.read_text(encoding="utf-8")

    records = [json.loads(line) for line in first_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 4
    assert [record["hardcore"] for record in records] == [False, False, True, True]
    assert all(record["clues"] == {"1": f"Clue for {record['word']}"} for record in records)
    assert generator.DEFAULT_OUTPUT_PATH.name == "words_clues.jsonl"
    assert generator.DEFAULT_OUTPUT_PATH.parent.name == "Crosswords"


@needs_generator
def test_dataset_generator_draws_from_basic_english_and_headwords():
    from textarena.utils.word_lists import get_basic_english_words, get_headwords

    generator = _load_generator()
    assert generator._usable_words(hardcore=False) == sorted(get_basic_english_words())
    assert generator._usable_words(hardcore=True) == sorted(get_headwords())


@needs_generator
def test_dataset_generator_does_not_replace_output_after_clue_failure(monkeypatch, tmp_path):
    generator = _load_generator()

    monkeypatch.setattr(generator, "_usable_words", lambda hardcore: ["alpha", "beta"])

    def fail_clues(word, model):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(generator, "get_clue_examples", fail_clues)
    destination = tmp_path / "words.jsonl"
    destination.write_text("existing data\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        generator.main(num_words=1, output_path=destination, seed=1)
    assert destination.read_text(encoding="utf-8") == "existing data\n"
