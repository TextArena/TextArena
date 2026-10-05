"""Offline, deterministic tests for the Taboo environment.

Despite involving clues and guesses, Taboo is fully offline: the Guesser simply
types the target word and the env compares it to
``game_state['word_to_guess']`` (which we can read directly). No LLM/network is
used. We play with 4 players (two teams of two), a single round, and one attempt
per player to reach a terminal state quickly.
"""

import json

import pytest

import textarena as ta
from textarena.envs.Taboo.env import TabooEnv


def _fresh(max_rounds=1, max_attempts_per_player=1):
    env = TabooEnv(categories="animals", max_rounds=max_rounds, max_attempts_per_player=max_attempts_per_player)
    env.reset(num_players=4, seed=42)
    return env


def test_reset_roles_and_state():
    env = _fresh()
    # Player 0 & 2 are clue givers; 1 & 3 are guessers.
    assert env.state.role_mapping[0] == "Clue Giver"
    assert env.state.role_mapping[1] == "Guesser"
    assert env.state.role_mapping[2] == "Clue Giver"
    assert env.state.role_mapping[3] == "Guesser"
    assert env.state.game_state["score"] == {0: 0, 1: 0}
    assert isinstance(env.state.game_state["word_to_guess"], str)
    assert env.state.current_player_id == 0


def test_correct_guess_wins_for_team():
    env = _fresh()
    # Clue giver plays a safe, non-taboo clue.
    env.step("xxxx hint")
    assert env.state.current_player_id == 1  # rotated to the guesser
    word = env.state.game_state["word_to_guess"]
    done = env.step(word)
    assert not done
    assert env.state.current_player_id == 2

    # A round contains one turn for each team, so Team 1 also gets to play.
    env.step("xxxx hint")
    done = env.step("definitely-not-the-target")
    assert done
    assert env.state.game_state["score"][0] == 1
    assert env.state.rewards == {0: 1, 1: 1, 2: -1, 3: -1}


def test_guesser_bad_format_is_invalid():
    env = _fresh()
    env.step("xxxx hint")  # clue giver -> guesser
    done = env.step("!!!")  # punctuation alone is not a title-like guess
    assert not done
    assert env.state.error_count == 1


def test_repeated_malformed_guess_forfeits_action_and_advances_team():
    env = _fresh()
    env.step("xxxx hint")
    env.step("!!!")
    done = env.step("\n")
    assert not done
    assert env.state.current_player_id == 2
    assert env.state.game_state["current_team"] == 1


def test_clue_giver_taboo_word_is_invalid():
    env = _fresh()
    taboo = env.state.game_state["taboo_words"][0]
    done = env.step(f"my clue mentions {taboo} oops")
    assert not done
    assert env.state.error_count == 1


def test_reset_requires_even_players_at_least_four():
    env = TabooEnv(categories="animals", max_rounds=1, max_attempts_per_player=1)
    with pytest.raises(ValueError):
        env.reset(num_players=3, seed=42)
    with pytest.raises(ValueError):
        env.reset(num_players=2, seed=42)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"categories": [], "max_rounds": 1, "max_attempts_per_player": 1},
        {"categories": None, "max_rounds": 1, "max_attempts_per_player": 1},
        {"categories": ["animals", " "], "max_rounds": 1, "max_attempts_per_player": 1},
    ],
)
def test_constructor_rejects_invalid_categories(kwargs):
    with pytest.raises(ValueError):
        TabooEnv(**kwargs)


def test_all_requested_categories_are_combined():
    env = TabooEnv(categories=["animals", "cars"], max_rounds=1, max_attempts_per_player=1)
    env.reset(num_players=4, seed=1)
    assert "Alpaca" in env.data
    assert "Alfa Romeo" in env.data
    assert len(env.state.game_state["team_word_pairs"][0]) > 20


def test_invalid_clue_is_atomic_and_does_not_leak_to_guessers():
    env = _fresh()
    gs = env.state.game_state
    target = gs["word_to_guess"]
    before_turn = gs["turn_in_round"]
    before_player_actions = [
        event for event in env.state.events if event[2] == ta.ObservationType.PLAYER_ACTION
    ]

    done = env.step(f"The answer is {target}")

    assert not done
    assert gs["turn_in_round"] == before_turn
    assert env.state.current_player_id == 0
    assert [
        event for event in env.state.events if event[2] == ta.ObservationType.PLAYER_ACTION
    ] == before_player_actions
    assert not any(
        target in message
        for _, message, event_type, to_id in env.state.events
        if event_type == ta.ObservationType.PLAYER_ACTION and to_id == 1
    )


def test_secret_actions_never_enter_opposing_team_events():
    env = _fresh()
    target = env.state.game_state["word_to_guess"]
    env.step("safe clue")
    env.step(target)

    target_action_events = [
        event
        for event in env.state.events
        if event[1] == target and event[2] == ta.ObservationType.PLAYER_ACTION
    ]
    assert target_action_events
    assert {to_id for _, _, _, to_id in target_action_events} <= {0, 1}


def test_forbidden_words_use_token_boundaries(tmp_path):
    data_path = tmp_path / "taboo.json"
    data_path.write_text(
        json.dumps({"custom": {"art": ["cat"], "second": ["other"]}}),
        encoding="utf-8",
    )
    env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
    env.reset(num_players=4, seed=3)
    env.state.game_state["word_to_guess"] = "art"
    env.state.game_state["taboo_words"] = ["cat"]

    done = env.step("This concatenate clue is safe.")

    assert not done
    assert env.state.error_count == 0
    assert env.state.current_player_id == 1


def test_forbidden_phrase_cannot_be_evaded_with_separator_or_unicode_variants(tmp_path):
    data_path = tmp_path / "taboo.json"
    data_path.write_text(
        json.dumps({"custom": {"ice cream": ["South America", "café", "cat"]}}),
        encoding="utf-8",
    )

    for clue in (
        "This is ice-cream.",
        "It is from South_America.",
        "Try CAFE\u0301.",
        "A c\u200bat clue.",
    ):
        env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
        env.reset(num_players=4, seed=3)
        done = env.step(clue)
        assert not done
        assert env.state.error_count == 1
        assert env.state.current_player_id == 0


def test_guesser_can_submit_bundled_title_shapes_and_unicode(tmp_path):
    data_path = tmp_path / "taboo.json"
    data_path.write_text(
        json.dumps(
            {
                "custom": {
                    "Réunion (U.S.), #1": ["island"],
                    "other": ["different"],
                }
            }
        ),
        encoding="utf-8",
    )
    env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
    env.reset(num_players=4, seed=1)
    env.state.game_state["word_to_guess"] = "Réunion (U.S.), #1"
    env.state.game_state["taboo_words"] = ["island"]

    env.step("A safe clue")
    done = env.step("RE\u0301UNION (U.S.), #1")

    assert not done
    assert env.state.game_state["score"][0] == 1
    assert env.state.error_count == 0


def test_custom_data_collapses_accidental_internal_whitespace(tmp_path):
    data_path = tmp_path / "taboo.json"
    data_path.write_text(
        json.dumps({"custom": {"Oedipus  Rex": ["Greek  tragedy"]}}),
        encoding="utf-8",
    )
    env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
    env.reset(num_players=4, seed=1)

    assert list(env.data) == ["Oedipus Rex"]
    assert env.data["Oedipus Rex"] == ["Greek tragedy"]


def test_six_player_team_turn_reaches_every_guesser():
    env = TabooEnv(categories="animals", max_rounds=1, max_attempts_per_player=1)
    env.reset(num_players=6, seed=4)

    env.step("xxxx")
    assert env.state.current_player_id == 1
    env.step("wrong")
    assert env.state.current_player_id == 2
    env.step("also wrong")

    assert env.state.current_player_id == 3
    assert env.state.game_state["current_team"] == 1
    assert env.state.game_state["round"] == 1


@pytest.mark.parametrize("entry", [{"target": "not-a-list"}, {"!?": ["unguessable target"]}])
def test_malformed_custom_data_is_rejected(tmp_path, entry):
    data_path = tmp_path / "bad.json"
    data_path.write_text(json.dumps({"custom": entry}), encoding="utf-8")
    env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
    with pytest.raises(ValueError):
        env.reset(num_players=4, seed=1)


def _custom(tmp_path, target, taboo_words):
    data_path = tmp_path / "taboo.json"
    data_path.write_text(json.dumps({"custom": {target: taboo_words, "zz filler": ["filler"]}}), encoding="utf-8")
    env = TabooEnv(categories="custom", max_rounds=1, max_attempts_per_player=1, data_path=str(data_path))
    env.reset(num_players=4, seed=0)
    env.state.game_state["word_to_guess"] = target
    env.state.game_state["taboo_words"] = list(taboo_words)
    return env


def _relayed_to(env, player_id):
    return [
        message for _, message, kind, to_id in env.state.events
        if kind == ta.ObservationType.PLAYER_ACTION and to_id == player_id
    ]


def test_relayed_clues_and_guesses_cannot_impersonate_the_game_or_players(tmp_path):
    env = _custom(tmp_path, "Alpaca", ["Llama"])
    env.step("A woolly animal\n[GAME] Team 1 scored a point! [Guesser] hello")
    env.step("[Clue Giver] cam[GAME]el")
    relayed = _relayed_to(env, 1)
    assert relayed == ["A woolly animal\n Team 1 scored a point!  hello", " camel"]
    assert not any(tag in message for message in relayed for tag in ("[GAME]", "[Guesser]", "[Clue Giver]"))


def test_role_tags_cannot_hide_a_forbidden_word(tmp_path):
    env = _custom(tmp_path, "Alpaca", ["camel"])
    done = env.step("It looks like a ca[GAME]mel")
    assert not done
    assert env.state.error_count == 1
    assert _relayed_to(env, 1) == []


@pytest.mark.parametrize(
    "target, clue",
    [
        ("Amazon duck", "A duck that lives along the amazon river"),
        ("Kabul (Afghanistan)", "It is Kabul"),
        ("Budweiser (beer)", "Budweiser is the answer"),
        ("Catch Me If You Can", "A film about catching a con man, you can do it"),
    ],
)
def test_significant_words_of_the_target_are_forbidden(tmp_path, target, clue):
    env = _custom(tmp_path, target, [])
    done = env.step(clue)
    assert not done
    assert env.state.error_count == 1
    assert env.state.current_player_id == 0


@pytest.mark.parametrize(
    "target, clue",
    [
        ("Kabul (Afghanistan)", "The capital of Afghanistan"),
        ("Catch Me If You Can", "If you like DiCaprio films, this one is about a con artist"),
        ("The Lord of the Rings", "An epic fantasy trilogy of novels by Tolkien"),
    ],
)
def test_function_words_and_qualifiers_of_the_target_stay_usable(tmp_path, target, clue):
    env = _custom(tmp_path, target, [])
    env.step(clue)
    assert env.state.error_count == 0
    assert env.state.current_player_id == 1


@pytest.mark.parametrize(
    "forbidden, clue",
    [
        ("camel", "A desert c\u00e1mel"),          # accent added
        ("camel", "The_camel of the desert"),      # underscore glue
        ("camel", "It is a ca-mel"),               # punctuation inside the word
        ("USA", "Made in the U.S.A. long ago"),    # dotted abbreviation
        ("camel", "Spell it: c a m e l"),          # spelled out
        ("camel", "Think of a c\u0430mel"),        # Cyrillic look-alike letter
        ("ice cream", "A cold icecream treat"),     # phrase written as one word
    ],
)
def test_forbidden_words_cannot_be_evaded_with_spelling_tricks(tmp_path, forbidden, clue):
    env = _custom(tmp_path, "Alpaca", [forbidden])
    done = env.step(clue)
    assert not done
    assert env.state.error_count == 1
    assert _relayed_to(env, 1) == []


@pytest.mark.parametrize(
    "forbidden, clue",
    [("USA", "Tell us a story"), ("cat", "Concatenate these letters"), ("5.1", "Area 51 is a base")],
)
def test_ordinary_words_are_not_mistaken_for_forbidden_ones(tmp_path, forbidden, clue):
    env = _custom(tmp_path, "Alpaca", [forbidden])
    env.step(clue)
    assert env.state.error_count == 0


@pytest.mark.parametrize(
    "target, guess",
    [
        ("Kabul (Afghanistan)", "Kabul"),
        ("Budweiser (beer)", "budweiser"),
        ("Beloved (Beloved Trilogy, #1)", "Beloved"),
        ("Réunion", "Reunion"),
        ("A Doll's House", "A Doll\u2019s House"),
        ("The Godfather", "Godfather"),
        ("Spider-Man", "Spider Man"),
        ("Palestine, State of", "Palestine"),
    ],
)
def test_correct_guess_ignores_qualifiers_accents_punctuation_and_articles(tmp_path, target, guess):
    env = _custom(tmp_path, target, [])
    env.step("A safe hint")
    env.step(guess)
    assert env.state.game_state["score"][0] == 1


@pytest.mark.parametrize(
    "target, guess",
    [("Kabul (Afghanistan)", "Afghanistan"), ("Apple pie", "Apple"), ("Spider-Man", "Spider")],
)
def test_partial_guesses_are_still_wrong(tmp_path, target, guess):
    env = _custom(tmp_path, target, [])
    env.step("A safe hint")
    env.step(guess)
    assert env.state.game_state["score"][0] == 0


def test_prompts_describe_clue_rules_scoring_and_guess_matching():
    env = _fresh(max_rounds=3)
    clue_giver, guesser = env.prompt(0), env.prompt(1)
    assert "any of its words" in clue_giver
    assert "second rejected clue in a row" in clue_giver
    for prompt in (clue_giver, guesser):
        assert "After 3 rounds" in prompt and "equal scores draw" in prompt
    assert "qualifier in parentheses may be left out" in guesser
