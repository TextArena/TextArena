"""Deterministic game-logic tests for Codenames-v0 (2v2 word deduction).

Players: 0 = Red spymaster, 1 = Red operative, 2 = Blue spymaster, 3 = Blue operative.
The board assignment is read from ``env.board`` so outcomes are scripted deterministically.
"""
from collections import Counter
import pytest
import textarena as ta
from textarena.envs.Codenames.env import CodenamesEnv


def _fresh():
    env = CodenamesEnv(max_turns=80)
    env.reset(num_players=4, seed=42)
    return env


def _words(env, team):
    return [w for w, t in env.board.items() if t == team]


# A clue word guaranteed not to be a subset/superset of any board word.
SAFE_CLUE = "qqqqqq"


def test_reset_board_composition():
    env = _fresh()
    assert len(env.board) == 25
    assert Counter(env.board.values()) == {"R": 9, "B": 8, "N": 7, "A": 1}
    assert "pass" not in env.board
    assert env.state.current_player_id == 0


@pytest.mark.parametrize("num_players", [3, 5])
def test_reset_requires_exactly_four_players(num_players):
    with pytest.raises(AssertionError):
        CodenamesEnv().reset(num_players=num_players, seed=42)


def test_roles_and_operative_board_privacy():
    env = _fresh()
    assert env.state.game_info[0]["role"] == "Red Spymaster"
    assert env.state.game_info[3]["role"] == "Blue Operative"
    operative_view = env.render(1)
    spymaster_view = env.render(0)
    for word, team in env.board.items():
        operative_line = next(line for line in operative_view.splitlines() if line.startswith(word))
        spymaster_line = next(line for line in spymaster_view.splitlines() if line.startswith(word))
        assert operative_line.strip() == word
        assert spymaster_line.split()[1] == team


@pytest.mark.parametrize(
    "kwargs",
    [
        {"hardcore": None},
        {"max_turns": 0},
        {"max_turns": True},
    ],
)
def test_constructor_rejects_invalid_options(kwargs):
    with pytest.raises(ValueError):
        CodenamesEnv(**kwargs)


def test_missing_nltk_data_uses_offline_fallback(monkeypatch):
    def unavailable(*args, **kwargs):
        raise LookupError("corpus unavailable")

    monkeypatch.setattr("textarena.envs.Codenames.env.words.words", unavailable)
    env = CodenamesEnv()
    env.reset(num_players=4, seed=42)
    assert len(env.board) == 25


def test_spymaster_clue_rotates_to_operative():
    env = _fresh()
    done, _ = env.step(f"{SAFE_CLUE} 2")
    assert not done
    assert env.state.current_player_id == 1  # red operative's turn
    assert env.state.game_state["last_clue"] == SAFE_CLUE


def test_clue_is_public_but_raw_action_echo_is_private():
    env = _fresh()
    before = len(env.state.events)
    env.step(f"{SAFE_CLUE} 2")
    new_events = env.state.events[before:]
    raw = [event for event in new_events if event[2] == ta.ObservationType.PLAYER_ACTION]
    assert raw == [(0, f"{SAFE_CLUE} 2", ta.ObservationType.PLAYER_ACTION, 0)]
    assert any(
        kind == ta.ObservationType.GAME_ACTION_DESCRIPTION and target == -1 and SAFE_CLUE in message
        for _, message, kind, target in new_events
    )


@pytest.mark.parametrize("action", ["bad-format", "clue 0", "clue 26", "clue 999999999999999999999"])
def test_invalid_clue_is_atomic_and_retriable(action):
    env = _fresh()
    done, _ = env.step(action)
    assert not done
    assert env.state.current_player_id == 0
    assert env.state.game_state["last_clue"] is None
    assert env.state.game_state["remaining_guesses"] == 0
    assert env.state.error_count == 1


def test_red_team_guesses_all_words_and_wins():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 9")  # up to 10 guesses allowed
    done = False
    for word in _words(env, "R"):
        done, _ = env.step(word)
        if done:
            break
    assert done
    assert env.state.rewards == {0: 1, 1: 1, 2: -1, 3: -1}


def test_blue_team_can_complete_a_deterministic_game():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 1")
    env.step("pass")
    env.step(f"{SAFE_CLUE} 8")
    for word in _words(env, "B"):
        done, _ = env.step(word)
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_guessing_assassin_loses_the_game():
    env = _fresh()
    assassin = _words(env, "A")[0]
    env.step(f"{SAFE_CLUE} 1")
    done, _ = env.step(assassin)
    assert done
    # Red picked the assassin -> Blue wins.
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_spymaster_clue_that_is_a_board_word_forfeits():
    env = _fresh()
    board_word = next(iter(env.board.keys()))
    done, _ = env.step(f"{board_word} 1")  # illegal clue: matches a board word
    assert done
    # Red spymaster cheated -> Blue team wins.
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_case_variant_of_board_word_cannot_bypass_clue_rule():
    env = _fresh()
    board_word = next(iter(env.board))
    done, _ = env.step(f"{board_word.upper()} 1")
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_invalid_operative_guess_is_atomic_and_retriable():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")
    before = env.state.game_state["guessed_words"].copy()
    done, _ = env.step("notontheboard")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["guessed_words"] == before
    assert env.state.game_state["remaining_guesses"] == 3
    assert env.state.error_count == 1


def test_operative_pass_hands_turn_to_other_team():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")  # player 0 -> rotates to player 1
    done, _ = env.step("pass")   # operative passes
    assert not done
    assert env.state.current_player_id == 2  # blue spymaster now


def test_repeated_invalid_action_forfeits_for_fixed_role_team():
    env = _fresh()
    env.step("bad")
    done, _ = env.step("still bad")
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}
    assert env.state.eliminated == []


def test_turn_limit_reason_uses_configured_limit():
    env = CodenamesEnv(max_turns=2)
    env.reset(num_players=4, seed=42)
    env.step(f"{SAFE_CLUE} 1")
    done, _ = env.step("pass")
    assert done
    assert env.state.rewards == {0: 0, 1: 0, 2: 0, 3: 0}
    assert all("(2)" in info["reason"] for info in env.state.game_info.values())


def test_repeat_reset_and_snapshot_restore_board_and_turn():
    env = _fresh()
    first_board = env.board.copy()
    snap = env.snapshot()
    env.step(f"{SAFE_CLUE} 2")
    env.restore(snap)
    assert env.board == first_board
    assert env.state.current_player_id == 0
    assert env.state.game_state["last_clue"] is None
    env.reset(num_players=4, seed=42)
    assert env.board == first_board
