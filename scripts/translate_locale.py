#!/usr/bin/env python3
"""Translate a game's en.json into the other TextArena locale languages via an LLM.

The point of this tool is that adding a language is "send en.json to an LLM with
the right instructions", not a bespoke process. It builds a strict translation
prompt from a game's English locale (optionally anchored to an already-translated
sibling game so terminology stays consistent across the corpus), then either
prints the prompt for you to paste into any assistant, or calls an LLM to produce
the <lang>.json files directly.

Whatever produces the files, `scripts/check_locales.py <Game>` is the gate: it
verifies key parity, slot parity, no duplicate keys, and that every value renders.
An LLM translation is NOT trusted until it passes that check (and ideally a human
or second-model review — the checker validates structure, not meaning).

Usage:
    # 1. Print the prompt(s) — no API key needed; paste into any LLM:
    python3 scripts/translate_locale.py WildTicTacToe --langs ar,de,es,fr,he,ms,zh

    # 2. Anchor terminology to an already-translated sibling game:
    python3 scripts/translate_locale.py WildTicTacToe --reference TicTacToe

    # 3. Call an LLM to write the files directly (requires the provider SDK + key):
    python3 scripts/translate_locale.py WildTicTacToe --provider anthropic
    python3 scripts/translate_locale.py WildTicTacToe --provider openai

    # then always:
    python3 scripts/check_locales.py WildTicTacToe
"""
import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENVS_DIR = os.path.join(REPO_ROOT, "textarena", "envs")
DEFAULT_LANGS = ["ar", "de", "es", "fr", "he", "ms", "zh", "kn", "be", "gu", "pa", "mr", "ps", "te", "sd", "ne", "lo", "uz", "ml", "zu", "as", "km", "hy", "cy", "si", "kk", "or", "my", "so", "mg", "ky", "ka", "ha", "ig", "mn", "eu", "yo", "am", "ceb", "bjn", "ars", "arz", "acq", "crh", "apc", "ajp", "bho", "ace", "acm", "ary", "ckb", "aeb", "ast", "bug", "ayr", "bam", "bem", "cjk", "ban", "awa", "bak"]  # en is the source
LANG_NAMES = {
    "ar": "Arabic", "de": "German", "es": "Spanish", "fr": "French",
    "he": "Hebrew", "ms": "Malay", "zh": "Simplified Chinese",
    "kn": "Kannada",
    "be": "Belarusian",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "mr": "Marathi",
    "ps": "Pashto",
    "te": "Telugu",
    "sd": "Sindhi",
    "ne": "Nepali",
    "lo": "Lao",
    "uz": "Uzbek",
    "ml": "Malayalam",
    "zu": "Zulu",
    "as": "Assamese",
    "km": "Khmer",
    "hy": "Armenian",
    "cy": "Welsh",
    "si": "Sinhala",
    "kk": "Kazakh",
    "or": "Odia",
    "my": "Burmese",
    "so": "Somali",
    "mg": "Malagasy",
    "ky": "Kyrgyz",
    "ka": "Georgian",
    "ha": "Hausa",
    "ig": "Igbo",
    "mn": "Mongolian",
    "eu": "Basque",
    "yo": "Yoruba",
    "am": "Amharic",
    "ceb": "ceb",
    "bjn": "Banjar",
    "ars": "Najdi Arabic",
    "arz": "Egyptian Arabic",
    "acq": "Taizzi-Adeni Arabic",
    "crh": "Crimean Tatar",
    "apc": "North Levantine Arabic",
    "ajp": "South Levantine Arabic",
    "bho": "Bhojpuri",
    "ace": "Acehnese",
    "acm": "Mesopotamian Arabic",
    "ary": "Moroccan Arabic",
    "ckb": "Central Kurdish",
    "aeb": "Tunisian Arabic",
    "ast": "Asturian",
    "bug": "Buginese",
    "ayr": "Central Aymara",
    "bam": "Bambara",
    "bem": "Bemba",
    "cjk": "Chokwe",
    "ban": "Balinese",
    "awa": "Awadhi",
    "bak": "Bashkir",
}

SYSTEM = (
    "You are a professional game-localization translator for the TextArena project. "
    "You translate JSON locale files for text-based games with total fidelity to meaning "
    "and to the technical constraints below."
)

RULES = """\
Translate the JSON below from English into {lang_name} ({lang_code}).

HARD RULES (a violation breaks the game at runtime):
1. Translate ONLY the string VALUES. Never translate or change any KEY (the left-hand side).
2. Keep every {{placeholder}} EXACTLY as-is (same spelling, same braces). Do not add,
   remove, reorder-into-different-tokens, or translate placeholders. Every placeholder
   that appears in an English value MUST appear in your translation.
3. Do NOT translate move tokens or format examples like '[4]', '[X 4]', '[macro micro]',
   backticks, or ASCII art — copy them verbatim.
4. Preserve the JSON structure exactly (same nesting, same keys). Output VALID JSON only.
5. Translate the values under "_comment" and "_slots" too (they are human guidance),
   but keep any {{placeholder}} inside them literal.
6. Use natural, fluent {lang_name} a native player would find idiomatic — match the
   register of a concise game UI.{rtl}

Output ONLY the translated JSON object, no code fences, no commentary.
"""

RTL_NOTE = " {lang_name} is right-to-left: write natural RTL prose, but keep the Latin move tokens and placeholders left-to-right as-is."

GLOSSARY_NOTE = """\
TERMINOLOGY ANCHOR — an already-approved {lang_name} translation of a related game is
shown below. Reuse its terminology for shared concepts (board, cell, player, draw,
symbol, etc.) so the games read consistently. Do NOT copy its keys or structure —
only borrow word choices where the same concept appears.

<<REFERENCE {lang_code}.json>>
{reference}
<<END REFERENCE>>
"""


def load(game, lang):
    path = os.path.join(ENVS_DIR, game, "locales", f"{lang}.json")
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_prompt(game, lang, reference_game=None):
    en = load(game, "en")
    rtl = RTL_NOTE.format(lang_name=LANG_NAMES[lang]) if lang in ("ar", "he") else ""
    parts = [RULES.format(lang_name=LANG_NAMES[lang], lang_code=lang, rtl=rtl)]
    if reference_game:
        ref_path = os.path.join(ENVS_DIR, reference_game, "locales", f"{lang}.json")
        if os.path.exists(ref_path):
            parts.append(GLOSSARY_NOTE.format(
                lang_name=LANG_NAMES[lang], lang_code=lang, reference=load(reference_game, lang)))
    parts.append("<<SOURCE en.json>>\n" + en + "\n<<END SOURCE>>")
    return "\n\n".join(parts)


def strip_fences(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def call_anthropic(prompt):
    import anthropic  # noqa: E402
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=8000,
        thinking={"type": "adaptive"},
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def call_openai(prompt):
    import openai  # noqa: E402
    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game", help="game directory name under textarena/envs/")
    ap.add_argument("--langs", default=",".join(DEFAULT_LANGS), help="comma-separated target languages")
    ap.add_argument("--reference", help="an already-translated sibling game to anchor terminology to")
    ap.add_argument("--provider", choices=["print", "anthropic", "openai"], default="print",
                    help="'print' emits the prompt (default, no API needed); others call the LLM and write files")
    args = ap.parse_args()

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    en_path = os.path.join(ENVS_DIR, args.game, "locales", "en.json")
    if not os.path.exists(en_path):
        print(f"error: {en_path} not found — create en.json first", file=sys.stderr)
        return 2

    loc_dir = os.path.join(ENVS_DIR, args.game, "locales")
    callers = {"anthropic": call_anthropic, "openai": call_openai}

    for lang in langs:
        prompt = build_prompt(args.game, lang, args.reference)
        if args.provider == "print":
            print(f"\n{'='*80}\n# PROMPT for {args.game} -> {lang} ({LANG_NAMES[lang]})\n{'='*80}")
            print(prompt)
            continue
        print(f"translating {args.game} -> {lang} via {args.provider} ...", file=sys.stderr)
        raw = callers[args.provider](prompt)
        try:
            data = json.loads(strip_fences(raw))
        except json.JSONDecodeError as e:
            print(f"  FAILED to parse JSON for {lang}: {e}. Raw output left unwritten.", file=sys.stderr)
            continue
        out = os.path.join(loc_dir, f"{lang}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  wrote {out}", file=sys.stderr)

    if args.provider != "print":
        print(f"\nNow VALIDATE (mandatory gate):\n  python3 scripts/check_locales.py {args.game}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
