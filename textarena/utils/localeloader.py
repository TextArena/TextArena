import os
import json
from typing import Any, Dict, Optional, Tuple

class LocaleLoader:
    def __init__(self,locales_dir: str, lang: str = "en"):
        self._locales_dir = locales_dir
        self._lang = lang    
        self._strings: Dict[str, Any] = self._load(lang)
    
    @property
    def lang(self) -> str:
        return self._lang
    
    def reload(self, lang: str) -> None:
        if lang == self._lang:
            return
        self._lang = lang
        self._strings = self._load(lang)

    def t(self, *keys: str, **kwargs: Any) -> str:
        result = self._resolve(self._strings, keys)

        if result is None:
            available = ", ".join(
                f for f in os.listdir(self._locales_dir) if f.endswith(".json")
            )
            raise KeyError(
                f"Locale key {'.'.join(keys)!r} not found in lang={self._lang!r} "
                f"(locales_dir={self._locales_dir!r}, available files: {available})"
            )

        return result.format(**kwargs) if kwargs else result
    
    def _load(self, lang: str) -> Dict[str, Any]:
        path = os.path.join(self._locales_dir, f"{lang}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"No locale file found for lang={lang!r} at {path}. "
                f"Available: {[f for f in os.listdir(self._locales_dir) if f.endswith('.json')]}"
            )
        with open(path, encoding="utf-8") as f:
            return json.load(f)
        
    @staticmethod
    def _resolve(data: Dict[str, Any], keys: Tuple[str, ...]) -> Optional[str]:
        node = data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
        return node if isinstance(node, str) else None
    
def build_locale(owner_class_or_path, lang: str = "en") -> Optional[LocaleLoader]:
    import inspect

    if isinstance(owner_class_or_path, str):
        locales_dir = owner_class_or_path
    else:
        locales_dir = os.path.join(
            os.path.dirname(inspect.getfile(owner_class_or_path)), "locales"
        )

    if not os.path.isdir(locales_dir):
        return None

    return LocaleLoader(locales_dir, lang=lang)