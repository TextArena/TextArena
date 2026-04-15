# textarena/utils/locales/__init__.py

import os
import json
import inspect
from typing import Any, Dict, Optional, Tuple


class LocaleLoader:
    def __init__(self, locales_dir: str, lang: str = "en"):
        self._locales_dir = locales_dir
        self._lang = lang
        self._data: Dict[str, Any] = self._load(lang)

    def t(self, *keys: str, **kwargs: Any) -> str:
        result = self._fetch(self._data, keys)
        if result is None:
            available = ", ".join(f for f in os.listdir(self._locales_dir) if f.endswith(".json"))
            raise KeyError(
                f"Locale key {'.'.join(keys)!r} not found in lang={self._lang!r} "
                f"(locales_dir={self._locales_dir!r}, available files: {available})"
            )
        return result.format(**kwargs) if kwargs else result

    def _load(self, lang: str) -> Dict[str, Any]:
        path = os.path.join(self._locales_dir, f"{lang}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No locale file for lang='{lang}' at {path}. "
                f"Available: {[f for f in os.listdir(self._locales_dir) if f.endswith('.json')]}"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _fetch(data: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
        node = data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node if isinstance(node, str) else None


def build_locale(cls=None, lang: str = "en") -> Optional[LocaleLoader]:
    """
    Resolve a locale directory and build a loader.

    Resolution order:
      1. If cls is a class, look for locales/ next to its source file.
         If that doesn't exist, fall back to this package's directory.
      2. If cls is a string, treat it as an explicit path.
      3. If cls is None, use this package's directory (the common locales).
    """
    if cls is None:
        locales_dir = os.path.dirname(__file__)
    elif isinstance(cls, str):
        locales_dir = cls
    else:
        class_locales = os.path.join(os.path.dirname(inspect.getfile(cls)), "locales")
        if not os.path.isdir(class_locales):
            return None
        locales_dir = class_locales

    if not os.path.isdir(locales_dir):
        if lang == "en":
            return None
        raise FileNotFoundError(f"No locales directory at {locales_dir} for lang={lang!r}.")

    return LocaleLoader(locales_dir, lang=lang)