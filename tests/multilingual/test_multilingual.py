#!/usr/bin/env python3
"""Multilingual regression + smoke test for localized envs.

For every game in game_scenarios.GAMES that ships a `locales/` folder (games
without one are not multilingual targets and are skipped, matching
scripts/check_locales.py):
  * GOLDEN IDENTITY - the English transcript must byte-match the committed
    goldens/<Game>.en.json (proves later edits don't silently change output).
  * CROSS-LINGUAL SMOKE - the game runs to completion under a mixed-language
    mapping and every non-English language without raising (catches format/slot
    crashes the English path can't reveal).

Run:
    python3 tests/multilingual/test_multilingual.py            # verify
    python3 tests/multilingual/test_multilingual.py --update   # (re)write goldens

Exit code 0 = pass. No third-party deps.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO_ROOT)   # so `import textarena` resolves
sys.path.insert(0, HERE)        # so sibling test modules resolve

from golden_runner import run_game, canonical, load_env, run_scenario  # noqa: E402
from game_scenarios import GAMES  # noqa: E402

GOLDEN_DIR = os.path.join(HERE, "goldens")
LANGS = ["ar", "de", "en", "es", "fr", "he", "ms", "zh", "kn", "be", "gu", "pa", "mr", "ps", "te", "sd", "ne", "lo", "uz", "ml", "zu", "as", "km", "hy", "cy", "si", "kk", "or", "my", "so", "mg", "ky", "ka", "ha", "ig", "mn", "eu", "yo", "am", "ceb", "bjn", "ars", "arz", "acq", "crh", "apc", "ajp"]


def golden_path(game):
    return os.path.join(GOLDEN_DIR, f"{game}.en.json")


def has_locales(game):
    """A game is a multilingual target iff it ships a `locales/` folder.

    Mirrors scripts/check_locales.py, which only validates games with a
    locales/ folder. Games without one (e.g. de-scoped from the multilingual
    effort, their env.py reverted to a monolingual state) are not localized and
    are skipped here too, so this suite stays consistent with the locale gate
    instead of crashing on an env that never opted in.
    """
    return os.path.isdir(os.path.join(REPO_ROOT, "textarena", "envs", game, "locales"))


def langs_for(game):
    """Languages to smoke-test for a game.

    A game may support a subset of the 8 (e.g. per-letter games exclude
    logographic zh). textarena/envs/<game>/locales/_supported_langs.json (a JSON
    list) narrows the set; absent -> all 8.
    """
    supported = os.path.join(REPO_ROOT, "textarena", "envs", game, "locales", "_supported_langs.json")
    if os.path.exists(supported):
        import json
        with open(supported, encoding="utf-8") as f:
            declared = json.load(f)
        return [l for l in LANGS if l in declared]
    return LANGS


def _selected(games):
    if not games:
        return sorted(GAMES)
    missing = [g for g in games if g not in GAMES]
    if missing:
        raise SystemExit(f"unknown game(s): {', '.join(missing)}")
    return list(games)


def update_goldens(games=None):
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    for game in _selected(games):
        if not has_locales(game):
            print(f"SKIP {game}: no locales/ folder (not a multilingual target)")
            continue
        text = canonical(run_game(GAMES[game], "en"))
        with open(golden_path(game), "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {golden_path(game)}")


def verify(games=None):
    failures = 0
    skipped = 0
    for game in _selected(games):
        if not has_locales(game):
            print(f"SKIP {game}: no locales/ folder (not a multilingual target)")
            skipped += 1
            continue
        spec = GAMES[game]
        # 1. English golden identity
        path = golden_path(game)
        if not os.path.exists(path):
            print(f"FAIL {game}: no committed golden ({path}); run --update")
            failures += 1
            continue
        with open(path, encoding="utf-8") as f:
            committed = f.read().rstrip("\n")
        produced = canonical(run_game(spec, "en"))
        if produced == committed:
            print(f"OK   {game}: english golden identical")
        else:
            print(f"FAIL {game}: english transcript differs from committed golden")
            failures += 1

        # 2. Cross-lingual smoke: mixed mapping + every non-en language
        n = spec.get("num_players", 2)
        game_langs = langs_for(game)
        mixed = {i: game_langs[i % len(game_langs)] for i in range(n)}
        try:
            for lang in game_langs:
                run_game(spec, lang)
            EnvCls = load_env(spec["entry"])
            for name, actions in spec["scenarios"].items():
                run_scenario(EnvCls, actions, dict(mixed), num_players=n, seed=spec.get("seed", 42))
            print(f"OK   {game}: cross-lingual smoke ({len(game_langs)} langs + mixed) no errors")
        except RuntimeError as e:  # optional word-data backend not installed
            if "wordfreq" in str(e):
                # English golden identity above still validated the en path; only
                # the non-English smoke needs the optional extra. Skip, don't fail.
                print(f"SKIP {game}: cross-lingual smoke (optional 'wordfreq' not installed)")
            else:
                print(f"FAIL {game}: cross-lingual smoke raised {type(e).__name__}: {e}")
                failures += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {game}: cross-lingual smoke raised {type(e).__name__}: {e}")
            failures += 1

    print()
    if failures:
        print(f"FAILED: {failures} check(s) failed.")
        return 1
    tested = len(_selected(games)) - skipped
    suffix = f" ({skipped} skipped: no locales/)" if skipped else ""
    print(f"PASSED: {tested} game(s){suffix}.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="regenerate committed goldens")
    ap.add_argument("games", nargs="*", help="restrict to these game names (default: all)")
    args = ap.parse_args()
    if args.update:
        update_goldens(args.games)
        return 0
    return verify(args.games)


if __name__ == "__main__":
    sys.exit(main())
