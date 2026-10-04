"""Deterministic offline tests for Logic Puzzle.

Single-player grid deduction game. The puzzle is chosen randomly, but the full
solution is stored on the env (``game_board_solution``). We read it and submit
the correct marks to solve the puzzle (reward 1). Marks use the bare format
``row col X|O`` and several may be submitted in one action.
"""
import copy
import importlib.resources
import itertools
import json
import random
import re

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


@pytest.mark.parametrize("action", ["I have no idea", "[alice home O", "alice home O,"])
def test_format_error_describes_expected_action(action):
    env = _fresh()
    env.step(action)
    notice = next(message for _, message in env.state.logs if "attempted an invalid move" in message)
    assert f"Expected {env.action_format}." in notice

    example = re.search(r"for example '([^']+)'", env.action_format).group(1)
    fresh = _fresh()
    fresh.step(example)
    assert fresh.state.turn == 1 and fresh.state.error_count == 0


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


def _packaged_records():
    resource = importlib.resources.files("textarena.envs.LogicPuzzle").joinpath("game_board_clues.jsonl")
    with resource.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def _holds(formula, owner):
    operator, *args = formula
    if operator == "not":
        return not _holds(args[0], owner)
    if operator == "and":
        return all(_holds(arg, owner) for arg in args)
    if operator == "or":
        return any(_holds(arg, owner) for arg in args)
    if operator == "if":
        return not _holds(args[0], owner) or _holds(args[1], owner)
    if operator == "iff":
        return _holds(args[0], owner) == _holds(args[1], owner)
    return owner[operator] == owner[args[0]]


@pytest.mark.parametrize("index", range(len(_packaged_records())))
def test_packaged_clues_have_exactly_one_solution_and_it_is_the_answer_key(index):
    record = _packaged_records()[index]
    unencoded = [clue for clue in record["clue"] if clue not in CLUE_LOGIC]
    assert not unencoded, f"add a formal reading to CLUE_LOGIC for {unencoded}"
    categories = [[item.lower() for item in items] for items in record["solution"].values()]
    anchor, others = categories[0], categories[1:]
    solutions = []
    for permutations in itertools.product(itertools.permutations(range(len(anchor))), repeat=len(others)):
        owner = {item: person for person, item in enumerate(anchor)}
        for items, permutation in zip(others, permutations):
            owner.update({item: permutation[position] for position, item in enumerate(items)})
        if all(_holds(CLUE_LOGIC[clue], owner) for clue in record["clue"]):
            solutions.append(permutations)
    identity = tuple(range(len(anchor)))
    assert solutions == [(identity,) * len(others)], f"puzzle {index + 1} has {len(solutions)} solutions"


@pytest.mark.parametrize("difficulty", ["easy", "hard"])
@pytest.mark.parametrize("seed", range(8))
def test_prompt_example_marks_a_real_cell(difficulty, seed):
    env = LogicPuzzleEnv(difficulty=difficulty)
    env.reset(num_players=1, seed=seed)
    _, observation = env.get_observation()
    prompt = observation[0][1]
    example = re.search(r"enter '(\w+ \w+ X)'", prompt).group(1)
    env.step(example)
    assert env.state.error_count == 0 and env.state.turn == 1


def test_prompt_states_win_condition_and_turn_limit():
    env = LogicPuzzleEnv(difficulty="easy", max_turns=30)
    env.reset(num_players=1, seed=1)
    _, observation = env.get_observation()
    prompt = observation[0][1]
    assert "including an 'X' in every non-matching cell" in prompt
    assert "30 turns" in prompt


def test_accepted_marks_are_confirmed_without_implying_correctness():
    env = _fresh()
    row, col, expected = _solution_tokens(env)[0].split()
    wrong = "X" if expected == "O" else "O"
    env.get_observation()
    env.step(f"{row} {col} {wrong}")
    _, observation = env.get_observation()
    messages = [message for _, message, _ in observation]
    assert f"Marked '{row} {col} {wrong}'." in messages
    assert not any("valid" in message for message in messages)


def test_swapped_row_and_column_labels_get_a_corrective_hint():
    env = _fresh()
    grid = next(iter(env.game_board.values()))
    row = next(iter(grid))
    col = next(iter(grid[row]))
    env.get_observation()
    env.step(f"{col} {row} X")
    _, observation = env.get_observation()
    assert any(f"give the row first: '{row} {col} X'" in message for _, message, _ in observation)
    assert env.state.error_count == 1


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


# Formal reading of every packaged clue, used to prove each puzzle has exactly one
# solution. An atom such as ("alice", "home") means both items belong to the same
# person; operators are "not", "and", "or", "if" (implication), and "iff".
CLUE_LOGIC = {
    'Alice is at home in the morning.': ('and', ('alice', 'home'), ('alice', 'morning')),
    'Bob works in the afternoon.': ('and', ('bob', 'work'), ('bob', 'afternoon')),
    'Charlie goes to the park in the evening.': ('and', ('charlie', 'park'), ('charlie', 'evening')),
    'The person at home is not Bob.': ('not', ('home', 'bob')),
    'The person at the park is not Alice.': ('not', ('park', 'alice')),
    'In the morning, Alice is at home.': ('and', ('alice', 'morning'), ('alice', 'home')),
    'Charlie is not at work.': ('not', ('charlie', 'work')),
    'Bob is at work in the afternoon.': ('and', ('bob', 'work'), ('bob', 'afternoon')),
    'The park is visited by Charlie.': ('park', 'charlie'),
    'Alice is not at work.': ('not', ('alice', 'work')),
    'Charlie is at the park in the evening.': ('and', ('charlie', 'park'), ('charlie', 'evening')),
    'Bob is at work during the afternoon.': ('and', ('bob', 'work'), ('bob', 'afternoon')),
    'Alice spends her time at home in the morning.': ('and', ('alice', 'home'), ('alice', 'morning')),
    'The evening is reserved for Charlie.': ('evening', 'charlie'),
    'Bob is at work, which is not during the evening.': ('and', ('bob', 'work'), ('not', ('bob', 'evening'))),
    'Alice is at home during the morning.': ('and', ('alice', 'home'), ('alice', 'morning')),
    'Charlie goes to the park after work.': ('charlie', 'park'),
    'The only person at home in the morning is Alice.': ('and', ('alice', 'home'), ('alice', 'morning')),
    'In the evening, the park is where Charlie is.': ('and', ('charlie', 'park'), ('charlie', 'evening')),
    'Alice is at home when the sun is rising.': ('and', ('alice', 'home'), ('alice', 'morning')),
    'Charlie enjoys the park in the evening.': ('and', ('charlie', 'park'), ('charlie', 'evening')),
    'The morning is when Alice stays home.': ('and', ('alice', 'morning'), ('alice', 'home')),
    "In the afternoon, it's Bob at work.": ('and', ('bob', 'afternoon'), ('bob', 'work')),
    'If Alice is home, then it must be morning.': ('if', ('alice', 'home'), ('alice', 'morning')),
    'Bob cannot be at home or at the park.': ('and', ('not', ('bob', 'home')), ('not', ('bob', 'park'))),
    'Charlie is at the location where the sun sets.': ('or', ('charlie', 'evening'), ('charlie', 'park')),
    'The person who works does not enjoy evening walks.': ('not', ('work', 'evening')),
    "If it's evening, then Charlie must be at the park.": ('if', ('charlie', 'evening'), ('charlie', 'park')),
    'If Alice is out in the morning, then Bob is not at home.': ('if', ('alice', 'morning'), ('not', ('bob', 'home'))),
    'Whoever is out in the afternoon is at work.': ('afternoon', 'work'),
    'The park is not visited in the morning.': ('not', ('park', 'morning')),
    'Charlie is out in the evening.': ('charlie', 'evening'),
    'If Bob is at home, then Charlie is at work.': ('if', ('bob', 'home'), ('charlie', 'work')),
    'If Charlie is not at work, he must be at the park.': ('if', ('not', ('charlie', 'work')), ('charlie', 'park')),
    'Bob is not out in the morning.': ('not', ('bob', 'morning')),
    'The person who works does so in the afternoon, not in the evening.': ('work', 'afternoon'),
    'When Alice is home, Bob is at work.': ('if', ('alice', 'home'), ('bob', 'work')),
    'Whoever is out in the evening is at the park.': ('evening', 'park'),
    'Whoever is at home is out in the morning.': ('home', 'morning'),
    'Bob can only be at work in the afternoon.': ('if', ('bob', 'work'), ('bob', 'afternoon')),
    'The person at work is out in the afternoon.': ('work', 'afternoon'),
    'If Bob is not at the park, he must be at work.': ('if', ('not', ('bob', 'park')), ('bob', 'work')),
    'If it’s morning, Alice is home, excluding others from that time.': ('if', ('alice', 'morning'), ('alice', 'home')),
    'When Bob is working, he cannot be at the park.': ('if', ('bob', 'work'), ('not', ('bob', 'park'))),
    'Charlie’s evening must end at the park.': ('if', ('charlie', 'evening'), ('charlie', 'park')),
    'If it’s evening, then Charlie is at the park.': ('if', ('charlie', 'evening'), ('charlie', 'park')),
    'Bob’s work hours coincide with the afternoon, leaving morning for Alice.': ('and', ('bob', 'work'), ('bob', 'afternoon'), ('alice', 'morning')),
    'Alice drives a red car.': ('alice', 'red'),
    'Bob does not drive a green car.': ('not', ('bob', 'green')),
    'Charlie uses electric fuel.': ('charlie', 'electric'),
    'The blue car is not driven by Alice.': ('not', ('blue', 'alice')),
    'The car fueled by diesel is driven by Bob.': ('diesel', 'bob'),
    'The red car is not used by Charlie.': ('not', ('red', 'charlie')),
    'Bob does not use electric fuel.': ('not', ('bob', 'electric')),
    'Bob drives a blue car.': ('bob', 'blue'),
    'Charlie drives a green car.': ('charlie', 'green'),
    'The fuel used by Alice is gasoline.': ('alice', 'gasoline'),
    'Charlie does not drive a blue car.': ('not', ('charlie', 'blue')),
    'The green car uses electric fuel.': ('green', 'electric'),
    'Alice’s car is red.': ('alice', 'red'),
    'The blue car does not use gasoline.': ('not', ('blue', 'gasoline')),
    'Alice drives a gasoline car.': ('alice', 'gasoline'),
    'Bob drives a blue diesel car.': ('and', ('bob', 'blue'), ('bob', 'diesel')),
    "The green car is not Alice's.": ('not', ('green', 'alice')),
    'The red car is driven by Alice.': ('red', 'alice'),
    "Bob's car is blue and not electric.": ('and', ('bob', 'blue'), ('not', ('bob', 'electric'))),
    "Alice's car is red.": ('alice', 'red'),
    'The fuel used by Bob is diesel.': ('bob', 'diesel'),
    'Alice uses gasoline.': ('alice', 'gasoline'),
    'If Charlie drives the green car, then Alice must drive the red car.': ('if', ('charlie', 'green'), ('alice', 'red')),
    'Bob does not drive the car that uses gasoline.': ('not', ('bob', 'gasoline')),
    'If Alice does not use electric fuel, she drives the red car.': ('if', ('not', ('alice', 'electric')), ('alice', 'red')),
    'The driver of the blue car cannot be Charlie.': ('not', ('blue', 'charlie')),
    'If Charlie does not use electric fuel, then he drives the blue car.': ('if', ('not', ('charlie', 'electric')), ('charlie', 'blue')),
    "If Alice's car is red, then Bob's car must be blue.": ('if', ('alice', 'red'), ('bob', 'blue')),
    "The car powered by diesel is not Alice's.": ('not', ('diesel', 'alice')),
    'If Charlie drives a green car, then he uses electric fuel.': ('if', ('charlie', 'green'), ('charlie', 'electric')),
    "Alice's car does not run on electric fuel.": ('not', ('alice', 'electric')),
    'Alice uses gasoline only if she drives the red car.': ('if', ('alice', 'gasoline'), ('alice', 'red')),
    'If Bob is not driving the blue car, then Alice must be driving the red car.': ('if', ('not', ('bob', 'blue')), ('alice', 'red')),
    'The driver of the green car uses electric fuel.': ('green', 'electric'),
    "If Alice drives a gasoline car, then Bob's car must be blue.": ('if', ('alice', 'gasoline'), ('bob', 'blue')),
    'The driver of the green car cannot be Alice.': ('not', ('green', 'alice')),
    'Alice does not use diesel fuel.': ('not', ('alice', 'diesel')),
    'If Alice’s fuel is gasoline, then Bob’s cannot be electric.': ('if', ('alice', 'gasoline'), ('not', ('bob', 'electric'))),
    'The color of the car driven by Charlie is green.': ('charlie', 'green'),
    'If Bob drives a blue car, then Alice does not use diesel.': ('if', ('bob', 'blue'), ('not', ('alice', 'diesel'))),
    'The red car belongs to Alice.': ('red', 'alice'),
    'If Alice uses electric fuel, then Bob drives the green car.': ('if', ('alice', 'electric'), ('bob', 'green')),
    'If Bob drives a blue car, then Alice drives a red one.': ('if', ('bob', 'blue'), ('alice', 'red')),
    'If the green car is not driven by Charlie, then he must be driving electric.': ('if', ('not', ('green', 'charlie')), ('charlie', 'electric')),
    'Alice does not drive a blue car.': ('not', ('alice', 'blue')),
    'If Bob does not use diesel, then Alice drives the green car.': ('if', ('not', ('bob', 'diesel')), ('alice', 'green')),
    'Alice is not having a burger.': ('not', ('alice', 'burger')),
    "Bob's meal is a burger.": ('bob', 'burger'),
    'Charlie is eating a salad.': ('charlie', 'salad'),
    'Alice is drinking water.': ('alice', 'water'),
    'Charlie is not drinking soda.': ('not', ('charlie', 'soda')),
    'Bob is drinking soda.': ('bob', 'soda'),
    'Bob does not eat salad.': ('not', ('bob', 'salad')),
    'Charlie is not drinking water.': ('not', ('charlie', 'water')),
    "Alice's meal is pizza.": ('alice', 'pizza'),
    'Bob is not having water.': ('not', ('bob', 'water')),
    'Charlie is the only one who has salad.': ('charlie', 'salad'),
    "Bob's drink is soda.": ('bob', 'soda'),
    'Alice is not drinking beer.': ('not', ('alice', 'beer')),
    "Pizza is Alice's meal.": ('pizza', 'alice'),
    'Bob does not drink water.': ('not', ('bob', 'water')),
    "Alice's drink is water.": ('alice', 'water'),
    'Bob is not eating pizza.': ('not', ('bob', 'pizza')),
    'Charlie is drinking beer.': ('charlie', 'beer'),
    'Alice does not eat a salad.': ('not', ('alice', 'salad')),
    'Alice eats pizza.': ('alice', 'pizza'),
    'Charlie has a salad.': ('charlie', 'salad'),
    'Charlie does not drink water.': ('not', ('charlie', 'water')),
    'If Alice is not having pizza, then Bob drinks beer.': ('if', ('not', ('alice', 'pizza')), ('bob', 'beer')),
    'If Bob is drinking soda, then Alice must be having water.': ('if', ('bob', 'soda'), ('alice', 'water')),
    'The person who is eating a burger is not the same person who drinks beer.': ('not', ('burger', 'beer')),
    'The one who drinks water must be eating pizza.': ('water', 'pizza'),
    'If Charlie is eating a salad, then he is not drinking soda.': ('if', ('charlie', 'salad'), ('not', ('charlie', 'soda'))),
    'Alice cannot drink beer or soda, but one of them must be true for Bob.': ('and', ('not', ('alice', 'beer')), ('not', ('alice', 'soda')), ('or', ('bob', 'beer'), ('bob', 'soda'))),
    'Whoever eats the salad is not drinking water.': ('not', ('salad', 'water')),
    'The drink of the person eating pizza is not soda.': ('not', ('pizza', 'soda')),
    'If Alice is drinking water, then Bob must be eating a burger.': ('if', ('alice', 'water'), ('bob', 'burger')),
    'Alice does not drink soda.': ('not', ('alice', 'soda')),
    'The one who drinks beer must not eat pizza.': ('not', ('beer', 'pizza')),
    'If Charlie is not drinking water, then he must be drinking beer.': ('if', ('not', ('charlie', 'water')), ('charlie', 'beer')),
    'The person who has a burger cannot be Alice.': ('not', ('burger', 'alice')),
    'If Alice does not drink soda, then Charlie must eat a salad.': ('if', ('not', ('alice', 'soda')), ('charlie', 'salad')),
    'If Alice is having pizza, then Charlie must be eating salad.': ('if', ('alice', 'pizza'), ('charlie', 'salad')),
    'If Bob is drinking soda, then he must be eating a burger as well.': ('if', ('bob', 'soda'), ('bob', 'burger')),
    'The one who eats a salad is drinking beer.': ('salad', 'beer'),
    'If Alice drinks soda, then Charlie drinks water.': ('if', ('alice', 'soda'), ('charlie', 'water')),
    'If Charlie is not drinking beer, then he is eating a salad.': ('if', ('not', ('charlie', 'beer')), ('charlie', 'salad')),
    'If Bob does not drink soda, then Alice is eating a salad.': ('if', ('not', ('bob', 'soda')), ('alice', 'salad')),
    'The one who eats pizza is not drinking soda.': ('not', ('pizza', 'soda')),
    'If Bob is eating a burger, then Alice must be drinking water.': ('if', ('bob', 'burger'), ('alice', 'water')),
    'If Alice is not having pizza, then Charlie is eating a salad.': ('if', ('not', ('alice', 'pizza')), ('charlie', 'salad')),
    'Alice plays soccer.': ('alice', 'soccer'),
    'Bob does not play tennis.': ('not', ('bob', 'tennis')),
    'Charlie plays tennis.': ('charlie', 'tennis'),
    "Wednesday is not Charlie's day.": ('not', ('wednesday', 'charlie')),
    'Bob plays basketball on Monday.': ('and', ('bob', 'basketball'), ('bob', 'monday')),
    'Charlie does not play soccer.': ('not', ('charlie', 'soccer')),
    'Alice does not play basketball.': ('not', ('alice', 'basketball')),
    "Wednesday is Alice's day.": ('wednesday', 'alice'),
    'The sport played on Tuesday is tennis.': ('tuesday', 'tennis'),
    'Bob plays basketball.': ('bob', 'basketball'),
    'Charlie does not play basketball.': ('not', ('charlie', 'basketball')),
    "Tuesday is not Alice's day.": ('not', ('tuesday', 'alice')),
    "Monday is Bob's day.": ('monday', 'bob'),
    "Alice's favorite sport is not basketball.": ('not', ('alice', 'basketball')),
    'Bob does not play soccer.': ('not', ('bob', 'soccer')),
    'Charlie plays tennis on Tuesday.': ('and', ('charlie', 'tennis'), ('charlie', 'tuesday')),
    'Bob plays on Monday.': ('bob', 'monday'),
    'Tuesday is tennis day.': ('tuesday', 'tennis'),
    "If Alice doesn't play basketball, then Bob plays on Monday.": ('if', ('not', ('alice', 'basketball')), ('bob', 'monday')),
    "If Wednesday is Charlie's day, then Alice plays soccer.": ('if', ('wednesday', 'charlie'), ('alice', 'soccer')),
    'Charlie plays tennis if and only if Bob plays basketball.': ('iff', ('charlie', 'tennis'), ('bob', 'basketball')),
    'Alice plays soccer on a day that is not Tuesday.': ('and', ('alice', 'soccer'), ('not', ('alice', 'tuesday'))),
    'If Charlie plays basketball, then he plays on Wednesday.': ('if', ('charlie', 'basketball'), ('charlie', 'wednesday')),
    'If Charlie plays on Tuesday, then Alice must play on Wednesday.': ('if', ('charlie', 'tuesday'), ('alice', 'wednesday')),
    "Monday is not Alice's day.": ('not', ('monday', 'alice')),
    'If Alice plays tennis, then Charlie plays on Monday.': ('if', ('alice', 'tennis'), ('charlie', 'monday')),
    'Charlie plays tennis only if his day is not Wednesday.': ('if', ('charlie', 'tennis'), ('not', ('charlie', 'wednesday'))),
    'If Alice does not play on Monday, then Bob plays basketball on Monday.': ('if', ('not', ('alice', 'monday')), ('and', ('bob', 'basketball'), ('bob', 'monday'))),
    'If Bob plays basketball, then Charlie must play tennis.': ('if', ('bob', 'basketball'), ('charlie', 'tennis')),
    'Alice plays on a day that is not Monday or Tuesday.': ('and', ('not', ('alice', 'monday')), ('not', ('alice', 'tuesday'))),
    "If Wednesday is Alice's day, then Charlie plays on Tuesday.": ('if', ('wednesday', 'alice'), ('charlie', 'tuesday')),
    'If Charlie plays on Tuesday, then Bob plays basketball.': ('if', ('charlie', 'tuesday'), ('bob', 'basketball')),
    "Alice's sport is soccer if and only if Bob's day is Monday.": ('iff', ('alice', 'soccer'), ('bob', 'monday')),
    'If Alice plays soccer, then Wednesday must be her day.': ('if', ('alice', 'soccer'), ('alice', 'wednesday')),
    'If Bob does not play basketball, then Charlie must play on Tuesday.': ('if', ('not', ('bob', 'basketball')), ('charlie', 'tuesday')),
    "Charlie plays tennis unless Alice's day is Wednesday.": ('if', ('not', ('alice', 'wednesday')), ('charlie', 'tennis')),
    'If Alice plays basketball, then Charlie plays on Wednesday.': ('if', ('alice', 'basketball'), ('charlie', 'wednesday')),
    'If Charlie does not play tennis, then Alice plays on Monday.': ('if', ('not', ('charlie', 'tennis')), ('alice', 'monday')),
    'The tennis player does not play on Monday.': ('not', ('tennis', 'monday')),
    "If Charlie plays tennis, then Wednesday is Alice's day.": ('if', ('charlie', 'tennis'), ('wednesday', 'alice')),
    'If Bob does not play soccer, then Alice plays on Wednesday.': ('if', ('not', ('bob', 'soccer')), ('alice', 'wednesday')),
    'Charlie plays on Tuesday only if Alice is playing soccer.': ('if', ('charlie', 'tuesday'), ('alice', 'soccer')),
}
