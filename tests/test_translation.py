"""TranslationWrapper: observation-level translation driven by per-env line catalogs.

Most tests run a small counting game written to a temporary folder, with catalogs
extracted from its source by `scripts/locales.py` and hand-written translations, so
they do not depend on the wording of the real envs.
"""
import importlib.util
import json
import random
import re
import sys
import warnings
from pathlib import Path

import pytest

import textarena as ta
from textarena.wrappers import MDPObservationWrapper, CurrentTurnObservationWrapper, TranslationWrapper
from textarena.wrappers.translation import SHARED_CATALOG, Catalog, template_id

ROOT = Path(__file__).resolve().parents[1]


def _load_tool():
    spec = importlib.util.spec_from_file_location("textarena_locales_tool", ROOT / "scripts" / "locales.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tool = _load_tool()

COUNTING_GAME = r'''
import textarena as ta


class CountingEnv(ta.GameEnv):
    min_players = 2
    max_players = 2
    action_pattern = r"^\s*(\d+)\s*$"

    def roles(self):
        return {0: "Red", 1: "Blue"}

    def setup(self):
        return {"total": 0}

    def prompt(self, player_id):
        return (
            f"You are Player {player_id} in the counting game.\n"
            "Reply with a number from 1 to 5, e.g. '3'.\n"
            "This rule has no translation."
        )

    def render(self, player_id):
        return f"Total: {self.game_state['total']}"

    def apply(self, player_id, move):
        value = int(move.group(1))
        if not 1 <= value <= 5:
            return self.invalid(f"{value} is not between 1 and 5.")
        self.game_state["total"] += value
        self.broadcast(f"Player {player_id} added {value}.", ta.ObservationType.GAME_ACTION_DESCRIPTION)
        self.broadcast(f"Player {player_id} added {value} to the pile.", ta.ObservationType.GAME_MESSAGE, from_id=player_id)
        if self.game_state["total"] >= 10:
            return self.winner(player_id, reason=f"Player {player_id} reached ten.")
        return None
'''

GERMAN = {
    "Red": "Rot",
    "You are Player {player_id} in the counting game.": "Du bist Spieler {player_id} im Zählspiel.",
    "Reply with a number from 1 to 5, e.g. '3'.": "Antworte mit einer Zahl von 1 bis 5, z. B. '3'.",
    "Total: {total}": "Summe: {total}",
    "{value} is not between 1 and 5.": "{value} liegt nicht zwischen 1 und 5.",
    "Player {player_id} added {value}.": "Spieler {player_id} hat {value} hinzugefügt.",
    "Player {player_id} added {value} to the pile.": "Spieler {player_id} legt {value} auf den Stapel.",
    "Player {player_id} reached ten.": "Spieler {player_id} hat zehn erreicht.",
}


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _set_section(path: Path, lang: str, entries: dict):
    """Replace one language section of a ``locales.json``, keeping the others."""
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data[lang] = entries
    _write(path, data)


def _translations(english: dict, wanted: dict) -> dict:
    """``{id: translation}`` for English templates, asserting each one was extracted."""
    ids = {text: tid for tid, text in english.items()}
    missing = [text for text in wanted if text not in ids]
    assert not missing, f"templates not extracted: {missing}"
    return {ids[text]: translation for text, translation in wanted.items()}


def _shared_catalog(path: Path) -> Path:
    """Shared catalog extracted from the real engine, with a few German strings."""
    english = tool.build_catalog(tool.source_files(tool.SHARED))
    player = next(t for t in english.values() if re.fullmatch(r"Player \{\w+\}", t))
    notice = next(t for t in english.values() if "attempted an invalid move. Reason: {reason}" in t)
    who = re.match(r"Player \{(\w+)\}", notice).group(1)
    german = {
        "GAME": "SPIEL",
        player: "Spieler {" + player[8:-1] + "}",
        notice: "Spieler {" + who + "} hat einen ungültigen Zug versucht. Grund: {reason} Bitte erneut versuchen.",
        "The submitted move does not follow the correct format.": "Der Zug hat nicht das richtige Format.",
    }
    _write(path, {
        "en": english,
        "de": _translations(english, german),
        "fr": _translations(english, {"GAME": "JEU"}),
    })
    return path


def _make_game(folder: Path, source: str = COUNTING_GAME, module_name: str = "counting_game_env"):
    """Write the game to ``folder``, import it and extract its English templates (other languages are kept)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "env.py").write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(module_name, folder / "env.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # inspect.getfile needs the module registered
    spec.loader.exec_module(module)
    english = tool.build_catalog([str(folder / "env.py")])
    _set_section(folder / "locales.json", "en", english)
    return module.CountingEnv, english


@pytest.fixture
def game(tmp_path):
    cls, english = _make_game(tmp_path / "CountingGame")
    _set_section(tmp_path / "CountingGame" / "locales.json", "de", _translations(english, GERMAN))
    shared = _shared_catalog(tmp_path / "shared" / "locales.json")

    def make(lang="de", wrapper=CurrentTurnObservationWrapper):
        env = TranslationWrapper(wrapper(cls()), lang=lang, shared_locales_file=str(shared))
        env.reset(num_players=2, seed=0)
        return env

    return make


def _play(env, actions):
    """Observations ``(player_id, text)`` seen while playing ``actions``, plus the final ones."""
    seen = []
    for action in actions:
        seen.append(env.get_observation())
        done = env.step(action)
        if done:
            break
    seen.append(env.get_observation())
    return seen


# --------------------------------------------------------------------------- runtime

def test_without_the_locales_package_only_english_is_available(monkeypatch):
    from textarena.wrappers import translation

    monkeypatch.setattr(translation, "PACKAGE_DIR", None)
    monkeypatch.setattr(translation, "SHARED_CATALOG", None)
    env = TranslationWrapper(ta.make("TicTacToe-v1"), lang="en")
    env.reset(num_players=2, seed=0)
    assert env.get_observation()[1].startswith("[GAME] You are Player 0")
    with pytest.raises(ImportError, match="textarena-locales"):
        TranslationWrapper(ta.make("TicTacToe-v1"), lang={1: "de"})


def test_english_is_an_exact_passthrough():
    actions = ["4", "0", "nonsense", "8", "1", "2", "6", "3", "5", "7"]
    plain, wrapped = ta.make("TicTacToe-v1"), TranslationWrapper(ta.make("TicTacToe-v1"), lang="en")
    plain.reset(num_players=2, seed=3)
    wrapped.reset(num_players=2, seed=3)
    assert _play(wrapped, actions) == _play(plain, actions)
    assert wrapped.close() == plain.close()


def test_prompt_board_action_and_invalid_notice_are_translated(game):
    env = game()
    _, first = env.get_observation()
    assert first.splitlines() == [
        "[SPIEL] Du bist Spieler 0 im Zählspiel.",
        "Antworte mit einer Zahl von 1 bis 5, z. B. '3'.",
        "This rule has no translation.",  # no translation: stays English
        "[SPIEL] Summe: 0",
    ]
    env.step("9")  # out of range: the engine notice wraps the env's reason
    _, notice = env.get_observation()
    assert notice.splitlines() == [
        "[Rot] 9",  # role label translated, typed action untouched
        "[SPIEL] Spieler 0 hat einen ungültigen Zug versucht. Grund: 9 liegt nicht zwischen 1 und 5. Bitte erneut versuchen.",
        "[SPIEL] Summe: 0",
    ]
    env.step("3")
    env.get_observation()
    env.step("2")
    _, after = env.get_observation()
    assert after.splitlines() == [
        "[Rot] 3",
        "[SPIEL] Spieler 0 hat 3 hinzugefügt.",
        "[Rot] Spieler 0 legt 3 auf den Stapel.",  # game-authored text under a player label
        "[Blue] 2",  # no translation for this role name
        "[SPIEL] Spieler 1 hat 2 hinzugefügt.",
        "[Blue] Spieler 1 legt 2 auf den Stapel.",
        "[SPIEL] Summe: 5",
    ]


def test_per_player_languages(game):
    env = game(lang={0: "de"})
    env.step("2")
    _, second = env.get_observation()
    assert second.startswith("[GAME] You are Player 1 in the counting game.")
    assert "[Red] 2" in second and "[GAME] Player 0 added 2." in second
    env.step("1")
    _, first = env.get_observation()
    assert first.startswith("[SPIEL] Du bist Spieler 0 im Zählspiel.")
    assert "[Blue] 1" in first and "[SPIEL] Spieler 1 hat 1 hinzugefügt." in first
    assert env.language(0) == "de" and env.language(1) == "en"


def test_typed_text_is_never_translated(game):
    env = game(lang="de", wrapper=MDPObservationWrapper)
    env.step("3")
    env.get_observation()
    env.step("Reply with a number from 1 to 5, e.g. '3'.")  # invalid, echoed verbatim
    lines = env.get_observation()[1].splitlines()
    assert "[Blue] Reply with a number from 1 to 5, e.g. '3'." in lines
    assert "Antworte mit einer Zahl von 1 bis 5, z. B. '3'." in lines  # the prompt's copy is translated
    assert ("[SPIEL] Spieler 1 hat einen ungültigen Zug versucht. Grund: Der Zug hat nicht das richtige Format. "
            "Bitte erneut versuchen.") in lines
    assert "[Rot] Spieler 0 legt 3 auf den Stapel." in lines
    # once a player types a sentence the game also sent under a player's name, neither copy is translated
    env.step("Player 0 added 3 to the pile.")
    lines = env.get_observation()[1].splitlines()
    assert "[Blue] Player 0 added 3 to the pile." in lines and "[Rot] Player 0 added 3 to the pile." in lines


def test_mdp_history_is_translated_every_turn(game):
    env = game(wrapper=MDPObservationWrapper)
    for action in ["1", "2", "3"]:
        env.get_observation()
        env.step(action)
    player, history = env.get_observation()
    assert player == 1
    lines = history.splitlines()
    assert lines[0] == "[SPIEL] Du bist Spieler 1 im Zählspiel."
    assert "[Rot] 1" in lines and "[Blue] 2" in lines and "[SPIEL] Spieler 1 hat 2 hinzugefügt." in lines
    assert sum(line.startswith("[SPIEL] Summe:") for line in lines) == 1  # only the latest board


def test_close_translates_each_players_reason(game):
    env = game(lang={0: "de", 1: "en"})
    for action in ["5", "1", "5"]:
        env.get_observation()
        done = env.step(action)
    assert done
    rewards, info = env.close()
    assert rewards == {0: 1, 1: -1}
    assert info[0]["reason"] == "Spieler 0 hat zehn erreicht."
    assert info[1]["reason"] == "Player 0 reached ten."
    assert env.env.env.state.game_info[0]["reason"] == "Player 0 reached ten."  # env state untouched


def test_missing_language_file_is_an_exact_passthrough(game):
    env = game(lang="fr")  # the shared catalog has French, the game does not
    _, obs = env.get_observation()
    assert obs.startswith("[GAME] You are Player 0 in the counting game.")
    assert env.available_languages == ["en", "de"]


def test_unknown_language_lists_available_ones(game):
    with pytest.raises(ValueError, match=r"Unknown language 'xx' for CountingGame; available: en, de"):
        game(lang="xx")


def test_translations_do_not_change_game_behavior():
    for env_id, players in [("TicTacToe-v1", 2), ("LiarsDice-v1", 3), ("Hanabi-v1-mdp", 2)]:
        outcomes = []
        for lang in ("en", "de"):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                env = TranslationWrapper(ta.make(env_id), lang=lang)
            env.reset(num_players=players, seed=7)
            rng = random.Random(7)
            for _ in range(60):
                env.get_observation()
                done = env.step(rng.choice(["0", "1", "4", "Bid: 2, 3", "call", "play 0", "discard 1", "x"]))
                if done:
                    break
            rewards, _ = env.close()
            outcomes.append((rewards, env.env.env.state.events, env.env.env.state.game_info))
        assert outcomes[0] == outcomes[1], env_id


def test_real_catalogs_translate_the_mdp_variant():
    game_label = json.loads(Path(SHARED_CATALOG).read_text(encoding="utf-8"))["de"][template_id("GAME")]
    observations = []
    for lang in ("en", "de"):
        env = TranslationWrapper(ta.make("TicTacToe-v1-mdp"), lang=lang)
        env.reset(num_players=2, seed=0)
        env.step("4")
        observations.append(env.get_observation()[1])
    english, german = observations
    assert german.startswith(f"[{game_label}] ") and "[GAME]" not in german
    assert len(german.splitlines()) == len(english.splitlines()) and german != english


def test_construction_warns_for_machine_verified_languages(tmp_path):
    cls, english = _make_game(tmp_path / "CountingGame", module_name="counting_game_env_kn")
    _set_section(tmp_path / "CountingGame" / "locales.json", "kn", _translations(english, {"Red": "ಕೆಂಪು"}))
    _set_section(tmp_path / "CountingGame" / "locales.json", "de", _translations(english, {"Red": "Rot"}))
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        TranslationWrapper(CurrentTurnObservationWrapper(cls()), lang="kn")
        assert [str(w.message) for w in caught if w.category is UserWarning and "Kannada" in str(w.message)]
        caught.clear()
        TranslationWrapper(CurrentTurnObservationWrapper(cls()), lang="de")
        assert not [w for w in caught if w.category is UserWarning]


def test_changed_english_line_no_longer_uses_the_old_translation(tmp_path):
    folder = tmp_path / "CountingGame"
    cls, english = _make_game(folder, module_name="counting_game_env_v1")
    _set_section(folder / "locales.json", "de", _translations(english, {"Total: {total}": "Summe: {total}"}))
    env = TranslationWrapper(CurrentTurnObservationWrapper(cls()), lang="de")
    env.reset(num_players=2, seed=0)
    assert env.get_observation()[1].endswith("Summe: 0")

    # The old template "Total: {total}" would still match the new line, but re-extracting
    # gives the new line a new id, so the orphaned translation cannot be used.
    changed = COUNTING_GAME.replace('f"Total: {self.game_state[\'total\']}"', 'f"Total: {self.game_state[\'total\']} points"')
    assert changed != COUNTING_GAME
    cls, english = _make_game(folder, changed, module_name="counting_game_env_v2")
    assert "Total: {total} points" in english.values() and "Total: {total}" not in english.values()
    env = TranslationWrapper(CurrentTurnObservationWrapper(cls()), lang="de")
    env.reset(num_players=2, seed=0)
    assert env.get_observation()[1].endswith("Total: 0 points")


# --------------------------------------------------------------------------- matching

@pytest.fixture
def catalog(tmp_path):
    def build(english_to_german: dict, extra_english=()):
        english = {template_id(t): t for t in list(english_to_german) + list(extra_english)}
        german = {template_id(t): g for t, g in english_to_german.items() if g is not None}
        _write(tmp_path / "locales.json", {"en": english, "de": german})
        return Catalog([str(tmp_path / "locales.json")])
    return build


def test_most_specific_template_wins(catalog):
    # both match "Player 0 added 3."; the more specific one decides
    cat = catalog({"Player {p} added {v}.": "Spieler {p} addierte {v}.", "{who} added {v}.": "{who} hat {v} addiert."})
    assert cat.translate_line("Player 0 added 3.", "de") == ("Spieler 0 addierte 3.", True)
    assert cat.translate_line("Alice added 3.", "de") == ("Alice hat 3 addiert.", True)
    # without a translation for the specific template the line stays English
    cat = catalog({"Player {p} added {v}.": None, "{who} added {v}.": "{who} hat {v} addiert."})
    assert cat.translate_line("Player 0 added 3.", "de") == ("Player 0 added 3.", False)


def test_recursive_slots_are_limited_in_depth(catalog):
    cat = catalog({"Outer: {x}": "Außen: {x}", "Reason: {r} Retry.": "Grund: {r} Nochmal.", "Cell {c} is taken.": "Feld {c} ist besetzt."})
    assert cat.translate_line("Reason: Cell 4 is taken. Retry.", "de")[0] == "Grund: Feld 4 ist besetzt. Nochmal."
    nested = cat.translate_line("Outer: Outer: Outer: Outer: Outer: end", "de")[0]
    assert nested == "Außen: Außen: Außen: Außen: Outer: end"


def test_whitespace_columns_and_unmatched_lines(catalog):
    cat = catalog({"Red team": "Rotes Team", "Blue team": "Blaues Team", "Score: {n}": "Punkte: {n}"})
    assert cat.translate_line("   Score: 5  ", "de") == ("   Punkte: 5  ", True)
    assert cat.translate_line("Red team    Blue team\tGreen team", "de") == ("Rotes Team    Blaues Team\tGreen team", True)
    assert cat.translate_line("Nothing matches here", "de") == ("Nothing matches here", False)
    assert cat.translate_line("Score:", "de") == ("Punkte:", True)  # empty slot at the end


def test_lines_starting_with_brackets_are_not_labels(game):
    env = game()
    text = "[GAME] Total: 1\n[0] Total: 2\n[Unknown] Total: 3"
    assert env.observation(0, text) == "[SPIEL] Summe: 1\n[0] Total: 2\n[Unknown] Total: 3"


# --------------------------------------------------------------------------- tooling

def test_committed_catalogs_are_fresh_and_valid(capsys):
    assert tool.main(["extract", "--check"]) == 0, capsys.readouterr().out
    assert tool.main(["check"]) == 0, capsys.readouterr().out


def test_extract_drops_translations_of_removed_lines_and_is_idempotent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tool, "ENVS_DIR", str(tmp_path / "envs"))
    monkeypatch.setattr(tool, "LOCALES_DIR", str(tmp_path / "locales"))
    game = tmp_path / "envs" / "Game"
    game.mkdir(parents=True)
    (game / "__init__.py").write_text("", encoding="utf-8")
    (game / "env.py").write_text('def a(x):\n    return f"Kept {x}."\n\n\ndef b():\n    return "New line."\n', encoding="utf-8")
    old, kept, new = template_id("Old line."), template_id("Kept {x}."), template_id("New line.")
    catalog = tmp_path / "locales" / "envs" / "Game.json"
    _write(catalog, {
        "fr": {old: "Ancienne ligne."},
        "en": {old: "Old line.", kept: "Kept {x}."},
        "de": {old: "Alte Zeile.", kept: "Bleibt {x}."},
    })
    assert tool.main(["extract", "--check", "Game"]) == 1
    assert tool.main(["extract", "Game"]) == 0
    text = catalog.read_text(encoding="utf-8")
    data = json.loads(text)
    assert list(data) == ["en", "de"]
    assert data["en"] == dict(sorted({kept: "Kept {x}.", new: "New line."}.items()))
    assert list(data["en"]) == sorted(data["en"]) and data["de"] == {kept: "Bleibt {x}."}
    capsys.readouterr()
    assert tool.main(["extract", "Game"]) == 0 and tool.main(["extract", "--check", "Game"]) == 0
    assert "updated" not in capsys.readouterr().out
    assert catalog.read_text(encoding="utf-8") == text


def test_extraction_rules(tmp_path):
    source = tmp_path / "env.py"
    source.write_text(r'''
import re
"""Module docstring is not UI text."""
PATTERN = r"^\s*(\d+) apples$"
NAMES = ["Alpha", "Beta"]


class Env:
    def roles(self):
        return {i: NAMES[i] for i in range(2)}

    def prompt(self, player_id, n, cards):
        """Docstring."""
        lookup = {"dict key text": 1}
        if self.mode == "compare text here":
            pass
        intro = "Hello Player " + str(player_id) + "!\nYou hold " + f"{n} card{'s' if n != 1 else ''}."
        side = f"You play {'first' if player_id == 0 else 'second'} this round."
        word = "Win!" if n else "Lose."
        prompt = "<NAME> joined the table."
        return prompt.replace("<NAME>", "x") + re.sub(r"some regex text", "", intro) + lookup.get("other key text", "Default fallback text.")
''', encoding="utf-8")
    assert tool.extract_templates([str(source)]) == [
        "Alpha", "Beta",  # single-word role names, looked up from a constant
        "Hello Player {player_id}!", "You hold {n} cards.", "Hello Player {player_id}!", "You hold {n} card.",
        "You play {v0} this round.",
        "Win!", "Lose.",
        "{name} joined the table.",
        "Default fallback text.",
    ]


def test_migration_rewrites_bracketed_actions_and_remaps_slots():
    convert = tool.convert
    variants = dict(tool.unbracket_variants("For example, '[4]' places it."))
    assert ("For example, '4' places it.") in variants
    text, why = convert("For example, '[4]' places it.", "Zum Beispiel setzt '[4]' es.", "For example, '4' places it.", (("[4]", "4"),))
    assert (text, why) == ("Zum Beispiel setzt '4' es.", None)
    text, why = convert("Use [coup x] now.", "Nutze [coup x] jetzt.", "Use 'coup x' now.", (("[coup x]", "'coup x'"),))
    assert text == "Nutze 'coup x' jetzt."
    assert convert("Use [coup x].", "Nutze [Putsch x].", "Use 'coup x'.", (("[coup x]", "'coup x'"),)) == (None, "bracket_token_missing")
    assert convert("Cell {cell} taken by {who}.", "{who} hat Feld {cell}.", "Cell {c} taken by {player}.") == ("{player} hat Feld {c}.", None)
    assert convert("Cell {cell}.", "Feld.", "Cell {c}.") == (None, "slot_mismatch")
    assert convert("Reply 'call'.", "Antworte 'rufen'.", "Reply 'call'.") == (None, "command_token_changed")
    assert tool.pair_lines("A\nB\n", "A'\nB'") == [("A", "A'"), ("B", "B'")]
    assert tool.pair_lines("A\nB", "A' B'") is None


def test_migration_plan_tiers():
    upstream = {
        "Game": {"en": {"a": "You win!\n{board}\nTotal: {n}", "b": "Use [roll] now."},
                 "de": {"a": "Du gewinnst!\n{board}\nSumme: {n}", "b": "Nutze [roll] jetzt."}},
        "Other": {"en": {"x": "Current Board:"}, "de": {"x": "Aktuelles Brett:"}},
        tool.SHARED: {"en": {"g": "GAME"}, "de": {"g": "SPIEL"}},
    }
    catalogs = {
        "Game": {template_id(t): t for t in ["You win!", "Total: {total}", "Use 'roll' now.", "Current Board:"]},
        tool.SHARED: {template_id("GAME"): "GAME"},
    }
    chosen, stats = tool.plan_migration(upstream, catalogs)
    assert chosen[("Game", "de", template_id("You win!"))] == ("Du gewinnst!", 0)
    assert chosen[("Game", "de", template_id("Total: {total}"))] == ("Summe: {total}", 0)
    assert chosen[("Game", "de", template_id("Use 'roll' now."))] == ("Nutze 'roll' jetzt.", 0)
    assert chosen[("Game", "de", template_id("Current Board:"))] == ("Aktuelles Brett:", 2)
    assert chosen[(tool.SHARED, "de", template_id("GAME"))] == ("SPIEL", 0)
    assert stats["carried"] == 4 and stats["game_removed"] == 1  # "Other" does not exist here
