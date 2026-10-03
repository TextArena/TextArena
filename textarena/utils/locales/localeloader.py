# textarena/utils/locales/__init__.py

import os
import json
import inspect
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass, field

@dataclass(frozen=True)
class LocalizedMessage:
    key: Tuple[str, ...]
    kwargs: Dict[str, Any] = field(default_factory=dict)
    loader: Optional["LocaleLoader"] = None

    def render(self, _pid: Optional[int] = None) -> str:
        assert self.loader is not None, "LocalizedMessage has no loader bound."
        return self.loader.t(*self.key, _pid=_pid, **self.kwargs)


class LocaleLoader:
    def __init__(self, locales_dir: str, langs = "en"):
        self._locales_dir = locales_dir
        if isinstance(langs, str):
            self._default_lang = langs
            self._id_to_lang = None
        elif isinstance(langs, dict):
            assert all(isinstance(k, int) and isinstance(v, str) for k, v in langs.items()), "langs dict must be Dict[int, str]"
            self._id_to_lang = dict(langs)
            self._default_lang = "en"  # Pick one of the languages as default for loading
        else:
            raise TypeError(f"langs must be str or Dict[int, str], got {type(langs)}")
        # self._lang = lang
        needed = set(self._id_to_lang.values()) | {self._default_lang} if self._id_to_lang else {self._default_lang}
        self._data: Dict[str, Dict[str, Any]] = {
            l: self._load(l) for l in needed
        }

    # localeloader.py — inside LocaleLoader.t
    def t(self, *keys, _pid=None, **kwargs):
        if _pid is None or self._id_to_lang is None:
            lang = self._default_lang
        else:
            lang = self._id_to_lang.get(_pid, self._default_lang)

        # Recursively render nested LocalizedMessage values against THEIR loaders
        resolved_kwargs = {
            k: (v.render(_pid=_pid) if isinstance(v, LocalizedMessage) else v)
            for k, v in kwargs.items()
        }

        data = self._data[lang]
        result = self._fetch(data, keys)
        if result is None:
            available = ", ".join(f for f in os.listdir(self._locales_dir) if f.endswith(".json"))
            raise KeyError(
                f"Locale key {'.'.join(keys)!r} not found in lang={lang!r} "
                f"(locales_dir={self._locales_dir!r}, available files: {available})"
            )
        return result.format(**resolved_kwargs) if resolved_kwargs else result

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


def build_locale(cls=None, lang = "en") -> Optional[LocaleLoader]:
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
        if lang == "en" or (isinstance(lang, dict) and all(v == "en" for v in lang.values())):
            return None
        raise FileNotFoundError(f"No locales directory at {locales_dir} for lang={lang!r}.")

    return LocaleLoader(locales_dir, langs=lang)