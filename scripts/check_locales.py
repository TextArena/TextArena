#!/usr/bin/env python3
"""Locale integrity checker for TextArena multilingual envs.

For every game that has a `locales/` folder, verify:

  1. LANG PARITY     - every game defines the required language set
                       (default: ar de en es fr he ms zh).
  2. NO DUP KEYS     - each JSON file has no duplicate keys (json silently keeps
                       the last one, so a hand-edit dupe would be invisible).
  3. KEY PARITY      - every language file has exactly en.json's leaf keys.
  4. SLOT PARITY     - every value has the same {placeholders} as en.json (catches
                       a translator dropping/renaming a {slot} -> runtime crash).
  5. RENDER SMOKE    - every value survives str.format (malformed braces caught).
  6. CODE COVERAGE   - every self.m()/self.t() key used in env.py exists in
                       en.json (missing = ERROR), and every en.json key is used
                       (unused = WARN). Keys built dynamically (non-literal args)
                       are reported so coverage is known to be partial.
  7. SAME-AS-EN      - a non-English value byte-identical to English is flagged
                       (WARN) as a likely untranslated leftover. Values with no
                       alphabetic content (pure slots/punctuation) are skipped.

Top-level keys beginning with '_' (_comment, _slots) are metadata: excluded from
key/slot/coverage parity, but still render-smoke tested.

Exit code 0 = no errors (warnings allowed), 1 = at least one error. Intended as
the CI gate that must pass before a translation is committed.

Usage:
    python3 scripts/check_locales.py                 # all localized games
    python3 scripts/check_locales.py WildTicTacToe   # specific game(s)
    python3 scripts/check_locales.py --langs ar,en   # override required langs
    python3 scripts/check_locales.py --strict         # treat warnings as errors
"""
import argparse
import ast
import json
import os
import re
import string
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENVS_DIR = os.path.join(REPO_ROOT, "textarena", "envs")
DEFAULT_LANGS = ["ar", "de", "en", "es", "fr", "he", "ms", "zh", "kn", "be", "gu", "pa", "mr", "ps", "te", "sd", "ne", "lo", "uz", "ml", "zu", "as", "km", "hy", "cy", "si", "kk", "or", "my", "so", "mg", "ky", "ka", "ha", "ig", "mn", "eu", "yo", "am", "ceb", "bjn", "ars", "arz", "acq", "crh", "apc", "ajp", "bho", "ace", "acm", "ary"]

SLOT_RE = re.compile(r"{[^{}]*}")
ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)  # any unicode letter


# ---------------------------------------------------------------- json loading
def _no_dupes(pairs):
    seen, dupes = {}, []
    for k, v in pairs:
        if k in seen:
            dupes.append(k)
        seen[k] = v
    if dupes:
        raise ValueError("duplicate keys: " + ", ".join(sorted(set(dupes))))
    return seen


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=_no_dupes)


# ---------------------------------------------------------------- flattening
def flatten(data, prefix=()):
    """Leaf (key_tuple, value) pairs, skipping top-level _metadata keys."""
    for k, v in data.items():
        if not prefix and k.startswith("_"):
            continue
        path = prefix + (k,)
        if isinstance(v, dict):
            yield from flatten(v, path)
        elif isinstance(v, str):
            yield path, v


def all_strings(data, prefix=()):
    """Every (path, value) including metadata, for render smoke."""
    for k, v in data.items():
        path = prefix + (k,)
        if isinstance(v, dict):
            yield from all_strings(v, path)
        elif isinstance(v, str):
            yield path, v


def slots_of(value):
    return sorted(SLOT_RE.findall(value))


class SafeDict(dict):
    def __missing__(self, key):
        return "<%s>" % key


def render_smoke(value):
    try:
        string.Formatter().vformat(value, (), SafeDict())
        return None
    except (ValueError, IndexError, KeyError) as e:
        return f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- code coverage
def code_keys(env_path):
    """Parse env.py, return (literal_keys:set[str], has_dynamic:bool).

    A key is the dotted path of the leading *string-constant* positional args to
    self.m(...) / self.t(...). If any leading positional arg is not a string
    constant, the call is counted as dynamic (partial coverage)."""
    with open(env_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=env_path)
    literal, dynamic = set(), False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr in ("m", "t")):
            continue
        if not (isinstance(fn.value, ast.Name) and fn.value.id == "self"):
            continue
        parts, is_dynamic = [], False
        for arg in node.args:  # positional args form the key path
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                parts.append(arg.value)
            else:
                is_dynamic = True
                break
        # Only a fully-literal call yields a complete, checkable key. A call with
        # a dynamic segment (e.g. self.m("results", var)) has an unknown full path,
        # so record it as dynamic rather than erroring on the partial prefix.
        if is_dynamic or not parts:
            dynamic = dynamic or (is_dynamic and bool(node.args))
        else:
            literal.add(".".join(parts))
    return literal, dynamic


# ---------------------------------------------------------------- per-game check
def check_game(game_dir, required_langs):
    errors, warnings = [], []
    loc_dir = os.path.join(game_dir, "locales")
    # Files starting with "_" are metadata (e.g. _supported_langs.json), not locales.
    present = sorted(
        f[:-5] for f in os.listdir(loc_dir)
        if f.endswith(".json") and not f.startswith("_")
    )

    # A game may support only a subset of the 8 languages (e.g. per-letter games
    # exclude logographic zh). An optional locales/_supported_langs.json (JSON
    # list) narrows the required set for this game.
    supported_path = os.path.join(loc_dir, "_supported_langs.json")
    if os.path.exists(supported_path):
        try:
            declared = load_json(supported_path)
            required_langs = [l for l in required_langs if l in declared]
        except (json.JSONDecodeError, ValueError) as e:
            errors.append(f"_supported_langs.json: {e}")

    missing_langs = [l for l in required_langs if l not in present]
    extra_langs = [l for l in present if l not in required_langs]
    if missing_langs:
        errors.append(f"missing language files: {', '.join(missing_langs)}")
    if extra_langs:
        warnings.append(f"extra (non-standard) language files: {', '.join(extra_langs)}")

    # load every file (dupe-checked)
    data = {}
    for lang in present:
        try:
            data[lang] = load_json(os.path.join(loc_dir, f"{lang}.json"))
        except (json.JSONDecodeError, ValueError) as e:
            errors.append(f"{lang}.json: {e}")

    if "en" not in data:
        errors.append("no valid en.json (needed as reference); skipping content checks")
        return errors, warnings

    en_leaves = dict(flatten(data["en"]))
    en_keys = set(en_leaves)
    en_slots = {k: slots_of(v) for k, v in en_leaves.items()}

    # render smoke on en (incl. metadata)
    for path, val in all_strings(data["en"]):
        err = render_smoke(val)
        if err:
            errors.append(f"en.json {'.'.join(path)}: render error: {err}")

    # per-language parity
    for lang in present:
        if lang == "en" or lang not in data:
            continue
        leaves = dict(flatten(data[lang]))
        keys = set(leaves)
        for k in sorted(en_keys - keys):
            errors.append(f"{lang}.json: missing key '{'.'.join(k)}'")
        for k in sorted(keys - en_keys):
            errors.append(f"{lang}.json: extra key '{'.'.join(k)}' not in en.json")
        for k in sorted(en_keys & keys):
            if slots_of(leaves[k]) != en_slots[k]:
                errors.append(
                    f"{lang}.json: slot mismatch at '{'.'.join(k)}': "
                    f"en={en_slots[k]} {lang}={slots_of(leaves[k])}"
                )
            elif leaves[k] == en_leaves[k] and ALPHA_RE.search(SLOT_RE.sub('', en_leaves[k])):
                warnings.append(f"{lang}.json: value identical to English at '{'.'.join(k)}' (untranslated?)")
        for path, val in all_strings(data[lang]):
            err = render_smoke(val)
            if err:
                errors.append(f"{lang}.json {'.'.join(path)}: render error: {err}")

    # code <-> key coverage (compare dotted-string forms)
    env_path = os.path.join(game_dir, "env.py")
    if os.path.isfile(env_path):
        used, dynamic = code_keys(env_path)
        en_keys_dotted = {".".join(k) for k in en_keys}
        for k in sorted(used - en_keys_dotted):
            errors.append(f"env.py uses key '{k}' missing from en.json")
        # dead-key check is unreliable when keys are built dynamically
        if not dynamic:
            for k in sorted(en_keys_dotted - used):
                warnings.append(f"en.json key '{k}' is never used in env.py (dead key?)")
        if dynamic:
            warnings.append("env.py builds some locale keys dynamically; code coverage is partial")
    else:
        warnings.append("no env.py found next to locales/; skipped code coverage")

    return errors, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("games", nargs="*", help="specific game names (default: all localized games)")
    ap.add_argument("--langs", default=",".join(DEFAULT_LANGS), help="comma-separated required languages")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()
    required_langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    games = args.games or sorted(
        d for d in os.listdir(ENVS_DIR)
        if os.path.isdir(os.path.join(ENVS_DIR, d, "locales"))
    )

    total_err = total_warn = 0
    for game in games:
        loc_dir = os.path.join(ENVS_DIR, game, "locales")
        if not os.path.isdir(loc_dir):
            print(f"SKIP {game}: no locales/ folder")
            continue
        errors, warnings = check_game(os.path.join(ENVS_DIR, game), required_langs)
        if args.strict:
            errors = errors + warnings
            warnings = []
        if not errors and not warnings:
            print(f"OK   {game}")
        else:
            print(f"{'FAIL' if errors else 'WARN'} {game}")
            for w in warnings:
                print(f"       warn: {w}")
            for e in errors:
                print(f"       err:  {e}")
        total_err += len(errors)
        total_warn += len(warnings)

    print()
    if total_err:
        print(f"FAILED: {total_err} error(s), {total_warn} warning(s) across {len(games)} game(s).")
        return 1
    print(f"PASSED: {len(games)} game(s), 0 errors, {total_warn} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
