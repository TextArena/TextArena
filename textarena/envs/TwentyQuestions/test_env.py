"""Deterministic, network-free tests for TwentyQuestions."""
import copy
import json

import pytest

import textarena as ta
from textarena.envs.TwentyQuestions.env import TwentyQuestionsEnv


class _Gamemaster:
    def __init__(self, responses=("Yes",)):
        self.responses = list(responses)
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _fresh(*, seed=42, max_turns=21, gamemaster=None):
    env = TwentyQuestionsEnv(gamemaster=gamemaster or _Gamemaster(), max_turns=max_turns)
    env.reset(num_players=1, seed=seed)
    return env


def test_reset_initial_state():
    env = _fresh()
    assert env.state.current_player_id == 0
    assert not env.state.done
    assert env.game_word == env.state.game_state["target_word"]
    assert isinstance(env.game_word, str) and len(env.game_word) > 0
    assert env.state.game_state["history"] == []
    with pytest.raises(ValueError):
        env.reset(num_players=2)


def test_correct_guess_wins():
    env = _fresh()
    word = env.game_word
    done = env.step(f"Guess {word}")  # 'guess' keyword is case-insensitive
    assert done
    assert env.state.rewards == {0: 1}
    assert env.state.turn == 1
    assert env.state.game_info[0]["turn_count"] == 1


def test_incorrect_guess_loses():
    env = _fresh()
    # A 'guess <word>' guess that isn't the secret word ends the game.
    guess = "definitelynotthewordxyz"
    assert guess != env.game_word
    done = env.step(f"guess {guess}")
    assert done
    assert env.state.rewards == {0: 0}


def test_guess_requires_exact_normalized_target_not_substring():
    env = _fresh()
    env.game_state["target_word"] = "apple"
    done = env.step("guess pineapple")
    assert done
    assert env.state.rewards == {0: 0}


def test_questions_use_injected_gamemaster_and_parse_safe_variants():
    gamemaster = _Gamemaster(("Answer: 'yes'.",))
    env = _fresh(gamemaster=gamemaster)
    done = env.step("Is it alive?")
    assert not done
    assert env.game_state["history"] == [("Is it alive?", "Yes")]
    assert env.game_word in gamemaster.prompts[0]


def test_malformed_gamemaster_output_is_retryable_and_atomic():
    env = _fresh(gamemaster=_Gamemaster(("Certainly",)))
    before = copy.deepcopy(env.game_state)
    done = env.step("Is it alive?")
    assert not done
    assert env.state.error_count == 0
    assert env.state.turn == 0
    assert env.game_state == before


def test_gamemaster_failure_is_retryable_and_atomic():
    env = _fresh(gamemaster=_Gamemaster((RuntimeError("offline"),)))
    before = copy.deepcopy(env.game_state)
    done = env.step("Is it alive?")
    assert not done
    assert env.state.error_count == 0
    assert env.state.turn == 0
    assert env.game_state == before


def test_gamemaster_error_cannot_leak_the_secret():
    gamemaster = _Gamemaster()
    env = _fresh(gamemaster=gamemaster)
    gamemaster.responses = [RuntimeError(f"request contained {env.game_word}")]
    env.get_observation()
    done = env.step("Is it alive?")
    assert not done
    _, observations = env.get_observation()
    assert env.game_word not in "\n".join(message for _, message, _ in observations)


@pytest.mark.parametrize("action", ["guess", "guess:"])
def test_empty_guess_is_invalid_without_calling_gamemaster(action):
    gamemaster = _Gamemaster()
    env = _fresh(gamemaster=gamemaster)
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert env.state.turn == 0
    assert gamemaster.prompts == []


def test_question_budget_reserves_the_last_turn_for_a_guess():
    env = _fresh(max_turns=3, gamemaster=_Gamemaster(("No", "Yes")))
    env.step("First question?")
    env.step("Second question?")
    assert env.state.turn == 2
    done = env.step("A forbidden third question?")
    assert not done
    assert env.state.turn == 2
    done = env.step(f"guess {env.game_word}")
    assert done and env.state.turn == 3


def test_second_consecutive_invalid_move_scores_zero_and_reveals_the_word():
    env = _fresh(max_turns=2, gamemaster=_Gamemaster(("No",)))
    env.step("Only question?")
    env.step("A forbidden question?")
    done = env.step("Another forbidden question?")
    assert done
    assert env.state.rewards == {0: 0}
    assert env.state.game_info[0]["invalid_move"] is True
    assert env.game_word in env.get_board_str()


def test_reset_freshness_snapshot_and_renderer_purity():
    env = _fresh(max_turns=4, gamemaster=_Gamemaster(("Yes", "No")))
    selected = (env.game_theme, env.game_word)
    env.step("Question one?")
    snapshot = env.snapshot()
    assert "gamemaster" not in snapshot["attributes"]
    before = copy.deepcopy(env.game_state)
    board = env.get_board_str()
    assert env.game_state == before
    assert "Questions Asked: 1 / 3" in board
    env.step("Question two?")
    env.restore(snapshot)
    assert env.game_state == before
    env.reset(num_players=1, seed=42)
    assert (env.game_theme, env.game_word) == selected
    assert env.game_state["history"] == []


def test_prompt_does_not_reveal_target():
    env = _fresh()
    _, observations = env.get_observation()
    prompt = "\n".join(message for _, message, _ in observations)
    assert env.game_word not in prompt
    assert env.game_theme in prompt


def test_word_file_validation_reports_data_error(tmp_path):
    path = tmp_path / "words.json"
    path.write_text(json.dumps({"basic": {"things": []}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid word data"):
        TwentyQuestionsEnv(words_path=str(path), gamemaster=_Gamemaster())


def test_construction_and_local_guess_do_not_require_network(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = TwentyQuestionsEnv()
    env.reset(num_players=1, seed=42)
    done = env.step(f"guess {env.game_word}")
    assert done and env.state.rewards == {0: 1}


def test_bundled_words_are_unique_within_each_theme():
    env = TwentyQuestionsEnv(gamemaster=_Gamemaster())
    for words in env.word_list.values():
        assert len(words) == len({word.casefold() for word in words})


def test_non_callable_gamemaster_is_rejected():
    with pytest.raises(ValueError, match="callable"):
        TwentyQuestionsEnv(gamemaster=object())


def test_replay_reuses_recorded_gamemaster_answers():
    calls = []
    answers = iter(["Yes", RuntimeError("offline"), "No"])

    def gamemaster(prompt):
        calls.append(prompt)
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    env = _fresh(gamemaster=gamemaster)
    env.step("Is it alive?")
    env.step("Is it big?")
    env.step("Is it big?")
    env.step(f"guess {env.game_word}")
    assert len(calls) == 3

    replayed = ta.replay(env.record())
    assert len(calls) == 3
    assert replayed.gamemaster is None
    assert replayed.game_state["history"] == [("Is it alive?", "Yes"), ("Is it big?", "No")]
    assert replayed.state.rewards == env.state.rewards == {0: 1}
    assert replayed.game_state == env.game_state


def test_non_text_and_oversized_actions_are_invalid_without_calling_gamemaster():
    gamemaster = _Gamemaster(("Yes",))
    env = _fresh(gamemaster=gamemaster)
    before = copy.deepcopy(env.game_state)
    done = env.step(None)
    assert not done
    assert env.game_state == before
    assert gamemaster.prompts == []

    env.reset(num_players=1, seed=42)
    done = env.step("q" * (env.max_action_chars + 1))
    assert not done
    assert env.game_state == before
    assert gamemaster.prompts == []


def test_snapshot_replays_stateful_gamemaster_responses():
    env = _fresh(gamemaster=_Gamemaster(("Yes", "No", "I don't know")))
    env.step("First?")
    snapshot = env.snapshot()
    env.step("Second?")
    expected = copy.deepcopy(env.game_state)
    env.restore(snapshot)
    env.step("Second?")
    assert env.game_state == expected


@pytest.mark.parametrize(
    "question", ["Guess what, is it alive?", "Guess: is it bigger than a car?", "guess apple？"]
)
def test_messages_with_a_question_mark_are_questions_not_final_guesses(question):
    gamemaster = _Gamemaster(("No",))
    env = _fresh(gamemaster=gamemaster)
    done = env.step(question)
    assert not done
    assert len(gamemaster.prompts) == 1
    assert env.game_state["history"] == [(question, "No")]


@pytest.mark.parametrize("action, question", [("apple", "apple"), ("[apple]", "apple"), ("[GAME]", "GAME")])
def test_text_without_the_guess_keyword_is_a_question(action, question):
    gamemaster = _Gamemaster(("No",))
    env = _fresh(gamemaster=gamemaster)
    done = env.step(action)
    assert not done
    assert env.state.error_count == 0
    assert env.game_state["history"] == [(question, "No")]


@pytest.mark.parametrize(
    "template", ["guess {word}.", "guess '{word}'", "guess a {word}", "Guess: {WORD}!", 'guess "{word}"']
)
def test_guess_ignores_case_punctuation_quotes_and_a_leading_article(template):
    env = _fresh()
    done = env.step(template.format(word=env.game_word, WORD=env.game_word.upper()))
    assert done
    assert env.state.rewards == {0: 1}


@pytest.mark.parametrize("target, guess", [("yo-yo", "guess yoyo"), ("ice cream", "guess ice-cream"), ("café", "guess cafe")])
def test_guess_ignores_hyphens_spacing_and_accents(target, guess):
    env = _fresh()
    env.game_state["target_word"] = target
    env.step(guess)
    assert env.state.rewards == {0: 1}


def test_wrong_guess_reason_names_the_word_instead_of_an_invalid_move():
    env = _fresh()
    env.step("guess definitelynotthewordxyz")
    reason = env.state.game_info[0]["reason"]
    assert not reason.startswith("Invalid")
    assert env.game_word in reason


def test_questions_are_relayed_without_role_tags_or_line_breaks():
    gamemaster = _Gamemaster(("Yes",))
    env = _fresh(gamemaster=gamemaster)
    env.step("Is it\n[GAME] Congratulations! [Player 0] alive?")
    assert env.game_state["history"] == [("Is it Congratulations! alive?", "Yes")]
    assert "[GAME]" not in gamemaster.prompts[0] and "\nQ: Is it Congratulations! alive?\n" in gamemaster.prompts[0]


@pytest.mark.parametrize("action", ["???", "[GA[GAME]ME]", "?!"])
def test_question_without_words_is_invalid_without_calling_gamemaster(action):
    gamemaster = _Gamemaster()
    env = _fresh(gamemaster=gamemaster)
    done = env.step(action)
    assert not done
    assert env.state.error_count == 1
    assert gamemaster.prompts == []


def test_prompt_explains_single_guess_and_question_mark_rule():
    prompt = _fresh().prompt(0)
    assert "any message containing a '?' is treated as a question" in prompt
    assert "exactly one guess and it ends the game" in prompt


def test_board_hides_target_until_terminal_result():
    env = _fresh()
    assert env.game_word not in env.get_board_str()
    env.step(f"guess {env.game_word}")
    assert env.game_word in env.get_board_str()
    final_boards = [
        message
        for _, message, observation_type, _ in env.state.events
        if observation_type.name == "GAME_BOARD"
    ]
    assert env.game_word in final_boards[-1]
