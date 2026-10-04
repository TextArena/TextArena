"""Translations of TextArena games, used by `textarena.wrappers.TranslationWrapper`.

- ``envs/<Game>.json`` holds one game's catalog: ``{"en": {id: template}, "<lang>": {id: translation}}``.
- ``shared.json`` holds the strings shared by all games (engine messages, sender labels).
- ``confidence.json`` holds the verification tier of each machine-translated language.

The catalogs are generated and validated with ``scripts/locales.py`` in the TextArena repository.
"""
