import pytest

import textarena as ta
from textarena.envs.Countdown.env import CountdownEnv


@pytest.mark.parametrize("env_id", ["Countdown-v0", "Countdown-v0-train", "Countdown-v0-raw"])
def test_registered_countdown_draws_a_seeded_puzzle(env_id):
    puzzles = []
    for seed in (0, 1, 0):
        env = ta.make(env_id)
        env.reset(num_players=1, seed=seed)
        puzzles.append((env.numbers[:], env.target))
    assert puzzles[0] != puzzles[1]
    assert puzzles[0] == puzzles[2]


def test_reset_redraws_the_puzzle_and_replays_the_seed():
    env = CountdownEnv()
    puzzles = []
    for seed in (0, None, 0):
        env.reset(num_players=1, seed=seed, lang_mapping={0: "en"})
        puzzles.append((env.numbers[:], env.target))
        env.step("[0 1 +]")
    assert puzzles[0] != puzzles[1]
    assert puzzles[0] == puzzles[2]
    assert len(puzzles[2][0]) == 6


@pytest.mark.parametrize("fixed", ["numbers", "target"])
def test_only_unspecified_puzzle_parts_are_redrawn(fixed):
    value = [100, 75, 6, 4, 3, 2] if fixed == "numbers" else 532
    env = CountdownEnv(**{fixed: value})
    puzzles = []
    for seed in (0, 1, 0):
        env.reset(num_players=1, seed=seed, lang_mapping={0: "en"})
        assert getattr(env, fixed) == value
        puzzles.append((env.numbers[:], env.target))
    assert puzzles[0] != puzzles[1]
    assert puzzles[0] == puzzles[2]


def test_explicit_puzzle_can_be_played_and_reset_without_changing_the_input():
    numbers = [100, 75, 6, 4, 3, 2]
    env = ta.make("Countdown-v0", numbers=numbers, target=532)
    for seed in (0, 1):
        env.reset(num_players=1, seed=seed, lang_mapping={0: "en"})
        assert env.numbers == numbers
        assert env.target == 532
        for action in ("[0 2 *]", "[4 0 -]", "[3 0 +]", "[2 0 +]"):
            done, _ = env.step(action)
        assert done
        assert env.state.rewards == {0: 1.0}
        assert numbers == [100, 75, 6, 4, 3, 2]
