# Multilingual verification

Tooling to convert a game to multilingual **reliably**, and to keep it correct.

## The per-game recipe

1. **Capture the English golden from the ORIGINAL env** (before touching code):
   add the game to `game_scenarios.py` with action scripts that reach every
   message branch, then `python3 tests/multilingual/test_multilingual.py --update`.
2. **Externalize strings** into `textarena/envs/<Game>/locales/en.json`
   (nested keys, a `_slots` block documenting every `{placeholder}`).
3. **Rewrite `env.py`** to replace each string literal with `self.m(...)`.
   Leave board renderers and move tokens (`[X 4]`) untouched.
4. **Prove it's behaviour-preserving**: `python3 tests/multilingual/test_multilingual.py`
   — the English transcript must byte-match the committed golden.
5. **Translate** the 7 other files (`ar de es fr he ms zh`) with the LLM helper —
   values only, every `{placeholder}` preserved, terminology anchored to a sibling
   game for consistency:
   ```
   # print the prompt to paste into any assistant (no API key needed):
   python3 scripts/translate_locale.py <Game> --reference TicTacToe
   # or call an LLM directly to write the files:
   python3 scripts/translate_locale.py <Game> --reference TicTacToe --provider anthropic
   ```
6. **Gate it**: `python3 scripts/check_locales.py <Game>` must pass. An LLM
   translation is not trusted until it passes this (and ideally a human / second-model
   review — the checker validates structure, not meaning).

## What each tool guarantees

- `scripts/check_locales.py` — static integrity: language parity, no duplicate
  JSON keys, key parity vs en.json, `{slot}` parity, `str.format` render-smoke,
  code↔key coverage (every `self.m()` key exists; unused keys warned; dynamic
  keys reported as partial coverage), and an "identical to English" warning for
  likely-untranslated values.
- `test_multilingual.py` — dynamic behaviour: English golden identity + a
  cross-lingual smoke run (every language + a mixed mapping) that must not raise.

## Limits (read before trusting a green run)

- Neither tool judges **translation *meaning***. A fluent-but-wrong translation
  passes. A human/second-model review is still required.
- Golden coverage is only as good as the scenarios: a branch you don't script is
  not exercised. `check_locales` still covers it structurally.
- **RTL** (`ar`, `he`): strings are validated, but visual ordering of prose mixed
  with the LTR ASCII board is not — eyeball it in a real terminal.
