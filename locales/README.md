# textarena-locales

Translations of [TextArena](https://github.com/LeonGuertler/TextArena) games into 192 languages. Install it with
`pip install "textarena[translations]"` and wrap an environment in `ta.wrappers.TranslationWrapper` to show each
player the game in their own language. English needs no translations, so the core `textarena` package works
without this one.

The catalogs are generated from the game source with `scripts/locales.py` in the TextArena repository; keep this
package's version equal to the `textarena` version it was generated for.
