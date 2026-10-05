"""Deterministic game-logic tests for Codenames-v1 (2v2 word deduction).

Players: 0 = Red spymaster, 1 = Red operative, 2 = Blue spymaster, 3 = Blue operative.
The board assignment is read from ``env.board`` so outcomes are scripted deterministically.
"""
from collections import Counter
import re

import pytest
import textarena as ta
import textarena.envs.Codenames.env as codenames_module
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
    with pytest.raises(ValueError):
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


@pytest.mark.parametrize("hardcore", [False, True])
def test_board_words_never_include_blocked_words(hardcore):
    from textarena.utils.word_lists import get_blocked_words

    assert not set(CodenamesEnv(hardcore=hardcore).word_list) & get_blocked_words()


@pytest.mark.parametrize("level", ["basic", "hardcore"])
def test_bundled_word_lists_hold_valid_board_words(level):
    words = codenames_module._bundled_word_lists()[level]
    assert len(words) == len(set(words)) >= 25
    assert "pass" not in words
    assert all(re.fullmatch(r"[a-z]{1,7}", word) for word in words)
    assert CodenamesEnv(hardcore=level == "hardcore").word_list == list(words)


def test_prompt_states_the_full_clue_rule_and_turn_limit():
    env = CodenamesEnv(max_turns=30)
    env.reset(num_players=4, seed=42)
    for player_id in range(4):
        prompt = env.prompt(player_id)
        assert "contain one, or be contained in one" in prompt
        assert "loses the game immediately" in prompt
        assert "a Neutral or opposing word ends the turn" in prompt
        assert "After 30 moves in total" in prompt


def test_board_shows_active_clue_and_guesses_left():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")
    assert f"Current clue: '{SAFE_CLUE} 2' (3 guesses left this turn)" in env.render(1)
    env.step(_words(env, "R")[0])
    assert f"Current clue: '{SAFE_CLUE} 2' (2 guesses left this turn)" in env.render(1)
    assert "Moves played: 2 of 80" in env.render(1)
    env.step("pass")
    assert "Current clue" not in env.render(2)


def test_spymaster_clue_rotates_to_operative():
    env = _fresh()
    done = env.step(f"{SAFE_CLUE} 2")
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
    done = env.step(action)
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
        done = env.step(word)
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
        done = env.step(word)
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_guessing_assassin_loses_the_game():
    env = _fresh()
    assassin = _words(env, "A")[0]
    env.step(f"{SAFE_CLUE} 1")
    done = env.step(assassin)
    assert done
    # Red picked the assassin -> Blue wins.
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_spymaster_clue_that_is_a_board_word_forfeits():
    env = _fresh()
    board_word = next(iter(env.board.keys()))
    done = env.step(f"{board_word} 1")  # illegal clue: matches a board word
    assert done
    # Red spymaster cheated -> Blue team wins.
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_case_variant_of_board_word_cannot_bypass_clue_rule():
    env = _fresh()
    board_word = next(iter(env.board))
    done = env.step(f"{board_word.upper()} 1")
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


@pytest.mark.parametrize(
    "make_clue, relation",
    [(lambda word: word, "is"), (lambda word: "x" + word, "contains"), (lambda word: word[:-1], "is part of")],
)
def test_board_word_clue_reason_names_the_overlapping_word(make_clue, relation):
    env = _fresh()
    board_word = next(iter(env.board))
    clue = make_clue(board_word)
    env.step(f"{clue} 1")
    assert env.state.game_info[0]["reason"] == (
        f"Player 0's clue '{clue}' {relation} the board word '{board_word}', which loses the game."
    )


def test_win_reason_is_accurate_when_the_other_team_revealed_some_words():
    env = _fresh()
    red = _words(env, "R")
    env.step(f"{SAFE_CLUE} 1")
    env.step("pass")
    env.step(f"{SAFE_CLUE} 1")
    env.step(red[0])  # Blue reveals a Red word
    env.step(f"{SAFE_CLUE} 8")
    for word in red[1:]:
        done = env.step(word)
    assert done
    assert env.state.rewards == {0: 1, 1: 1, 2: -1, 3: -1}
    assert env.state.game_info[0]["reason"] == f"Player 1 guessed '{red[-1]}', their team's last word!"


def test_invalid_operative_guess_is_atomic_and_retriable():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")
    before = env.state.game_state["guessed_words"].copy()
    done = env.step("notontheboard")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["guessed_words"] == before
    assert env.state.game_state["remaining_guesses"] == 3
    assert env.state.error_count == 1


def test_operative_pass_hands_turn_to_other_team():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")  # player 0 -> rotates to player 1
    done = env.step("pass")   # operative passes
    assert not done
    assert env.state.current_player_id == 2  # blue spymaster now


def test_repeated_invalid_action_forfeits_for_fixed_role_team():
    env = _fresh()
    env.step("bad")
    done = env.step("still bad")
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}
    assert env.state.eliminated == []


def test_turn_limit_reason_uses_configured_limit():
    env = CodenamesEnv(max_turns=2)
    env.reset(num_players=4, seed=42)
    env.step(f"{SAFE_CLUE} 1")
    done = env.step("pass")
    assert done
    assert env.state.rewards == {0: 0, 1: 0, 2: 0, 3: 0}
    assert all("(2)" in info["reason"] for info in env.state.game_info.values())
