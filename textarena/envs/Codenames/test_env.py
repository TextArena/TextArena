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
    assert all(re.fullmatch(r"[a-z]{3,7}", word) for word in words)
    assert CodenamesEnv(hardcore=level == "hardcore").word_list == list(words)


def test_hardcore_boards_never_hold_words_shorter_than_three_letters():
    env = CodenamesEnv(hardcore=True)
    for seed in range(500):
        env.reset(num_players=4, seed=seed)
        assert min(len(word) for word in env.board) >= 3, seed


def test_prompt_states_the_full_clue_rule_and_turn_limit():
    env = CodenamesEnv(max_turns=30)
    env.reset(num_players=4, seed=42)
    for player_id in range(4):
        prompt = env.prompt(player_id)
        assert "start or end with one, or be the start or end of one" in prompt
        assert "A forbidden clue is not given and the team's turn ends at once." in prompt
        assert "must make at least one guess each turn" in prompt
        assert "a Neutral or opposing word ends the turn" in prompt
        assert "After 30 moves in total" in prompt
        assert "fewer of its words still unrevealed wins" in prompt


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
    env.step(_words(env, "N")[0])
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


def _with_words(env, *words):
    """Put `words` at the front of the board, keeping the labels of the words they replace."""
    items = list(env.board.items())
    env.board = {**{word: team for word, (_, team) in zip(words, items)}, **dict(items[len(words):])}


def test_forbidden_clue_ends_the_turn_without_guesses_and_tells_everyone():
    env = _fresh()
    _with_words(env, "arm")
    before = len(env.state.events)
    done = env.step("ARMS 2")
    assert not done
    assert env.state.rewards is None
    assert env.state.error_count == 0
    assert env.state.turn == 1  # the forbidden clue still counts as a move
    assert env.state.current_player_id == 2  # Blue Spymaster; Red's Operative gets no guesses
    gs = env.state.game_state
    assert gs["last_clue"] is None and gs["remaining_guesses"] == 0
    message = "Player 0's clue 'arms' starts with the board word 'arm', which is not allowed, so Red's turn ends."
    assert (ta.GAME_ID, message, ta.ObservationType.GAME_MESSAGE, -1) in env.state.events[before:]


def test_blue_forbidden_clue_hands_the_turn_back_to_red():
    env = _fresh()
    _with_words(env, "arm")
    env.step(f"{SAFE_CLUE} 1")
    env.step(_words(env, "N")[0])
    env.step("firearm 1")
    assert env.state.current_player_id == 0
    assert "so Blue's turn ends." in env.state.events[-2][1]


@pytest.mark.parametrize(
    "clue, relation, board_word",
    [
        ("arm", "is", "arm"),
        ("arms", "starts with", "arm"),
        ("firearm", "ends with", "arm"),
        ("farm", "ends with", "arm"),
        ("star", "is the start of", "starfish"),
        ("fish", "is the end of", "starfish"),
    ],
)
def test_forbidden_clue_message_names_the_board_word_and_relation(clue, relation, board_word):
    env = _fresh()
    _with_words(env, "arm", "starfish")
    env.step(f"{clue} 1")
    assert env.state.current_player_id == 2
    assert any(
        message.startswith(f"Player 0's clue '{clue}' {relation} the board word '{board_word}',")
        for _, message, _, _ in env.state.events
    )


def test_board_word_only_in_the_middle_of_the_clue_is_allowed():
    env = _fresh()
    _with_words(env, "arm")
    done = env.step("charming 1")
    assert not done
    assert env.state.current_player_id == 1
    assert env.state.game_state["last_clue"] == "charming"


def test_revealed_board_words_no_longer_restrict_clues():
    env = _fresh()
    _with_words(env, "arm")
    env.state.game_state["guessed_words"].add("arm")
    env.step("arms 1")
    assert env.state.current_player_id == 1
    assert env.state.game_state["last_clue"] == "arms"


def test_win_reason_is_accurate_when_the_other_team_revealed_some_words():
    env = _fresh()
    red = _words(env, "R")
    env.step(f"{SAFE_CLUE} 1")
    env.step(_words(env, "N")[0])
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


def test_operative_pass_after_a_guess_hands_turn_to_other_team():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")  # player 0 -> rotates to player 1
    env.step(_words(env, "R")[0])
    done = env.step("pass")   # operative passes
    assert not done
    assert env.state.current_player_id == 2  # blue spymaster now


def test_pass_before_the_first_guess_is_invalid_and_atomic():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")
    done = env.step("Pass")
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 1
    assert env.state.game_state["remaining_guesses"] == 3
    assert "You must make at least one guess this turn before you can pass." in env.state.events[-2][1]
    done = env.step("pass")  # a second invalid move in a row escalates as usual
    assert done
    assert env.state.rewards == {0: -1, 1: -1, 2: 1, 3: 1}


def test_the_guess_requirement_applies_again_each_turn():
    env = _fresh()
    env.step(f"{SAFE_CLUE} 2")
    env.step(_words(env, "R")[0])
    env.step("pass")
    env.step(f"{SAFE_CLUE} 2")
    env.step("pass")
    assert env.state.error_count == 1
    assert env.state.current_player_id == 3


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
    done = env.step(_words(env, "N")[0])
    assert done
    assert all("(2)" in info["reason"] for info in env.state.game_info.values())


@pytest.mark.parametrize(
    "red_revealed, blue_revealed, rewards",
    [
        (5, 5, {0: -1, 1: -1, 2: 1, 3: 1}),  # Red has 4 left, Blue 3: Blue wins despite equal reveals
        (5, 4, {0: 0, 1: 0, 2: 0, 3: 0}),    # 4 left each: draw despite Red revealing more
        (6, 4, {0: 1, 1: 1, 2: -1, 3: -1}),  # Red 3 left, Blue 4
        (0, 0, {0: -1, 1: -1, 2: 1, 3: 1}),  # untouched board: Blue needs one word fewer
    ],
)
def test_turn_limit_compares_words_still_unrevealed(red_revealed, blue_revealed, rewards):
    env = CodenamesEnv(max_turns=1)
    env.reset(num_players=4, seed=42)
    env.state.game_state["guessed_words"].update(_words(env, "R")[:red_revealed] + _words(env, "B")[:blue_revealed])
    done = env.step(f"{SAFE_CLUE} 1")
    assert done
    assert env.state.rewards == rewards
