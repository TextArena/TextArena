"""Observation-level translation of TextArena environments.

Environments only produce English. `TranslationWrapper` rewrites the final
observation strings line by line into each player's language, using message
catalogs that live next to the code producing the text:

- ``textarena/envs/<Game>/locales.json`` is ``{"en": {id: template}, "<lang>": {id: translation}}``.
  Each id is a short hash of an English *line template* extracted from the env source,
  e.g. ``"Player {player_id} placed their symbol ({symbol}) in cell {cell}."``, and
  translations use the same ``{slot}`` names.
- ``textarena/wrappers/locales.json`` holds the strings shared by all games (engine
  messages, sender labels) in the same format.

An observation line is rendered from the most specific English template that
matches it (the one with the most literal characters); captured slot values are
translated recursively when they are themselves template lines. Lines without a
matching translated template stay English. Because ids hash the English text,
editing an English line orphans its old translation instead of showing a stale
one. Catalogs are generated and validated with ``scripts/locales.py``.
"""
import hashlib
import inspect
import json
import os
import re
import warnings
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from textarena.core import GAME_ID, ObservationType, ObservationWrapper, Wrapper

__all__ = ["TranslationWrapper"]

CATALOG_FILE = "locales.json"
SHARED_CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), CATALOG_FILE)
CONFIDENCE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locale_confidence.json")
SOURCE_LANG = "en"
ID_LENGTH = 10
MAX_DEPTH = 3  # nesting depth for slot values that are template lines themselves
MAX_LINE_CHARS = 4000  # longer lines are passed through untouched
CACHE_SIZE = 20_000  # memo entries per catalog before the memo is reset

_FIELD = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")
_LETTER = re.compile(r"[^\W\d_]")  # every template has a letter, so lines without one never match
_LABEL = re.compile(r"\[([^\[\]\n]+)\]( |$)")
_COLUMN_GAP = re.compile(r"(\s{2,}|\t)")


def template_id(template: str) -> str:
    """Catalog id of an English line template."""
    return hashlib.sha1(template.encode("utf-8")).hexdigest()[:ID_LENGTH]


def split_template(template: str) -> Tuple[List[str], List[str]]:
    """Split a template into literal texts and slot names (``lits[0] slots[0] lits[1] ... lits[-1]``).

    ``{name}`` is a slot and ``{{`` / ``}}`` are literal braces; any other text is literal.
    """
    lits, slots, buf, pos = [], [], [], 0
    for m in _FIELD.finditer(template):
        buf.append(template[pos:m.start()])
        if m.group(1) is None:
            buf.append(m.group(0)[0])
        else:
            lits.append("".join(buf))
            slots.append(m.group(1))
            buf = []
        pos = m.end()
    buf.append(template[pos:])
    lits.append("".join(buf))
    return lits, slots


def join_template(lits: Sequence[str], slots: Sequence[str]) -> str:
    """Inverse of `split_template`."""
    out = [lits[0].replace("{", "{{").replace("}", "}}")]
    for slot, lit in zip(slots, lits[1:]):
        out.append("{" + slot + "}")
        out.append(lit.replace("{", "{{").replace("}", "}}"))
    return "".join(out)


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def _signature(path: str) -> Tuple:
    try:
        st = os.stat(path)
    except OSError:
        return ()
    return st.st_mtime_ns, st.st_size


_FILES: Dict[str, Tuple[Tuple, Dict[str, Dict[str, str]]]] = {}


def read_catalog_file(path: str) -> Dict[str, Dict[str, str]]:
    """``{lang: {id: text}}`` of a catalog file, parsed once per process (again only if it changes)."""
    path = os.path.abspath(path)
    signature = _signature(path)
    cached = _FILES.get(path)
    if cached is None or cached[0] != signature:
        data = {lang: entries for lang, entries in _read_json(path).items() if isinstance(entries, dict)}
        cached = _FILES[path] = (signature, data)
    return cached[1]


class _Template:
    """An English line template compiled into an anchored regex."""

    __slots__ = ("id", "slots", "literal", "regex", "groups", "specificity", "prefix", "suffix", "needle", "rank")

    def __init__(self, tid: str, text: str, rank: int):
        lits, slots = split_template(text)
        self.id, self.slots, self.rank = tid, slots, rank
        pattern, cores, groups = [], [], {}
        for i, lit in enumerate(lits):
            # whitespace next to a slot is optional, so empty slot values still match stripped lines
            if i > 0 and lit[:1].isspace():
                lit = lit.lstrip()
                pattern.append(r"\s*")
            trailing = i < len(slots) and lit[-1:].isspace()
            if trailing:
                lit = lit.rstrip()
            pattern.append(re.escape(lit))
            if trailing and lit:
                pattern.append(r"\s*")
            cores.append(lit)
            if i < len(slots):
                group = groups.get(slots[i])
                if group is None:
                    group = groups[slots[i]] = f"g{len(groups)}"
                    pattern.append(f"(?P<{group}>.*?)")
                else:
                    pattern.append(f"(?P={group})")
        self.literal = lits[0] if not slots else None
        self.regex = re.compile("".join(pattern), re.DOTALL)
        self.groups = groups
        self.specificity = sum(len(c) for c in cores)
        self.prefix, self.suffix = cores[0], (cores[-1] if slots else "")
        self.needle = max(cores[1:-1], key=len, default="")


class Catalog:
    """English templates and their translations, merged from catalog files in priority order."""

    def __init__(self, files: Sequence[str]):
        self.files = list(files)
        self._data = [read_catalog_file(f) for f in self.files]
        self.languages = [set(data) - {SOURCE_LANG} for data in self._data]
        templates: Dict[str, _Template] = {}
        for data in self._data:
            for tid, text in data.get(SOURCE_LANG, {}).items():
                if tid not in templates and isinstance(text, str) and text.strip():
                    templates[tid] = _Template(tid, text, len(templates))
        self._exact: Dict[str, List[_Template]] = {}
        for t in templates.values():
            if t.literal is not None:
                self._exact.setdefault(t.literal, []).append(t)
        self._slotted = sorted((t for t in templates.values() if t.literal is None), key=lambda t: (-t.specificity, len(t.slots), t.rank))
        self._tables: Dict[str, Dict[str, Tuple[List[str], List[str]]]] = {}
        self._matches: Dict[str, List[Tuple[_Template, Dict[str, str]]]] = {}
        self._lines: Dict[Tuple[str, str], Tuple[str, bool]] = {}

    def __deepcopy__(self, memo):
        return self  # read-only apart from memo caches; share it between env copies and snapshots

    def table(self, lang: str) -> Dict[str, Tuple[List[str], List[str]]]:
        """Translations for ``lang`` as ``{id: (literals, slots)}``."""
        table = self._tables.get(lang)
        if table is None:
            table = {}
            for data in self._data:
                for tid, text in data.get(lang, {}).items():
                    if tid not in table and isinstance(text, str) and text.strip():
                        table[tid] = split_template(text)
            self._tables[lang] = table
        return table

    def match(self, line: str) -> List[Tuple[_Template, Dict[str, str]]]:
        """Templates of maximal specificity that fully match a stripped line, with their captures."""
        hit = self._matches.get(line)
        if hit is not None:
            return hit
        exact = self._exact.get(line, ())
        best = [(t, {}) for t in exact]
        top = len(line) if exact else -1
        for t in self._slotted:
            if t.specificity < top:
                break
            if not (line.startswith(t.prefix) and line.endswith(t.suffix) and t.needle in line):
                continue
            m = t.regex.fullmatch(line)
            if m is None:
                continue
            captures = {name: m.group(group) for name, group in t.groups.items()}
            if t.specificity > top:
                best, top = [(t, captures)], t.specificity
            else:
                best.append((t, captures))
        if len(self._matches) >= CACHE_SIZE:
            self._matches.clear()
        self._matches[line] = best
        return best

    def translate_text(self, line: str, lang: str, depth: int = 0) -> Optional[str]:
        """Translate a stripped line that fully matches a translated template; None otherwise."""
        table = self.table(lang)
        if not table:
            return None
        for t, captures in self.match(line):
            translation = table.get(t.id)
            if translation is None:
                continue
            lits, slots = translation
            if any(slot not in captures for slot in slots):
                return None
            if depth < MAX_DEPTH:
                captures = {slot: self._translate_value(captures[slot], lang, depth + 1) for slot in set(slots)}
            out = [lits[0]]
            for slot, lit in zip(slots, lits[1:]):
                out.append(captures[slot])
                out.append(lit)
            return "".join(out)
        return None

    def _translate_value(self, value: str, lang: str, depth: int) -> str:
        core = value.strip()
        if not core or len(core) > MAX_LINE_CHARS:
            return value
        out = self.translate_text(core, lang, depth)
        if out is None and not self.match(core):
            out = self._translate_columns(core, lang, depth)
        if out is None:
            return value
        return value[: len(value) - len(value.lstrip())] + out.strip() + value[len(value.rstrip()):]

    def translate_line(self, line: str, lang: str) -> Tuple[str, bool]:
        """Translate one observation line, preserving its surrounding whitespace.

        Returns the line and whether anything was translated. A line whose best
        template has no translation stays English; only lines that match no
        template at all fall back to translating space-separated columns.
        """
        if not _LETTER.search(line):
            return line, False
        key = (lang, line)
        hit = self._lines.get(key)
        if hit is not None:
            return hit
        core = line.strip()
        out = None
        if core and len(core) <= MAX_LINE_CHARS:
            out = self.translate_text(core, lang)
            if out is None and not self.match(core):
                out = self._translate_columns(core, lang)
        if out is None:
            result = (line, False)
        else:
            result = (line[: len(line) - len(line.lstrip())] + out.strip() + line[len(line.rstrip()):], True)
        if len(self._lines) >= CACHE_SIZE:
            self._lines.clear()
        self._lines[key] = result
        return result

    def _translate_columns(self, line: str, lang: str, depth: int = 0) -> Optional[str]:
        parts = _COLUMN_GAP.split(line)
        if len(parts) < 3:
            return None
        changed = False
        for i in range(0, len(parts), 2):
            if parts[i]:
                out = self.translate_text(parts[i], lang, depth)
                if out is not None:
                    parts[i], changed = out.strip(), True
        return "".join(parts) if changed else None

    def translate_block(self, text: str, lang: str) -> str:
        """Translate every line of a multi-line text."""
        return "\n".join(self.translate_line(line, lang)[0] for line in text.split("\n"))


_CATALOGS: Dict[Tuple, Catalog] = {}


def load_catalog(files: Sequence[str]) -> Catalog:
    """Catalog for ``files`` (highest priority first), rebuilt only when one of the files changes."""
    files = tuple(os.path.abspath(f) for f in files)
    key = (files, tuple(_signature(f) for f in files))
    catalog = _CATALOGS.get(key)
    if catalog is None:
        for old in [k for k in _CATALOGS if k[0] == files]:
            del _CATALOGS[old]
        catalog = _CATALOGS[key] = Catalog(files)
    return catalog


def _unwrap(env):
    while isinstance(env, Wrapper):
        env = env.env
    return env


def _env_catalog_files(env) -> List[str]:
    """``locales.json`` files next to the modules defining the env class and its game base classes."""
    files = []
    for cls in type(env).__mro__:
        path = getattr(inspect.getmodule(cls), "__file__", None)
        if not path:
            continue
        f = os.path.join(os.path.dirname(os.path.abspath(path)), CATALOG_FILE)
        if f != SHARED_CATALOG and f not in files and os.path.isfile(f):
            files.append(f)
    return files


def _game_name(env) -> str:
    try:
        return os.path.basename(os.path.dirname(inspect.getfile(type(env))))
    except (TypeError, OSError):
        return type(env).__name__


_CONFIDENCE: Optional[Dict[str, Dict[str, Any]]] = None


def _confidence() -> Dict[str, Dict[str, Any]]:
    global _CONFIDENCE
    if _CONFIDENCE is None:
        data = _read_json(CONFIDENCE_PATH)
        _CONFIDENCE = {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}
    return _CONFIDENCE


def _warn_if_uncertified(lang: str, game: str):
    """Warn for machine-translated languages that were verified automatically but not certified."""
    record = _confidence().get(lang)
    if not record or record.get("tier") == "CERTIFIED":
        return
    name = record.get("name", lang)
    if record.get("tier") == "EXPERIMENTAL":
        message = f"{name} ({lang}) is an EXPERIMENTAL machine translation: structurally valid, but its meaning is not certified."
    else:
        message = (f"{name} ({lang}) is machine-translated and automatically verified, not reviewed by "
                   f"native speakers; some phrases may be imperfect.")
    if game in record.get("flagged_games", ()):
        message += f" {game} has known divergences in this language."
    warnings.warn(message, UserWarning, stacklevel=3)


class TranslationWrapper(ObservationWrapper):
    """Show observations in each player's language.

    Apply it on top of a made env, e.g. ``TranslationWrapper(ta.make("TicTacToe-v0"), lang="de")``
    or ``lang={0: "de", 1: "en"}`` (players not listed see English). It works with every
    observation variant because it rewrites the final observation string; the env
    itself, the actions players type, and game behavior are unchanged.

    Args:
        env: the environment to wrap.
        lang: a language code for all players, or a ``{player_id: code}`` mapping.
        locales_file: env catalog file(s) to use instead of the env's own ``locales.json``.
        shared_locales_file: shared catalog file (engine messages, sender labels).
    """

    def __init__(self, env, lang: Union[str, Dict[int, str]] = SOURCE_LANG,
                 locales_file: Union[str, Sequence[str], None] = None, shared_locales_file: Optional[str] = None):
        super().__init__(env)
        base = _unwrap(env)
        self.game_name = _game_name(base)
        if locales_file is None:
            env_files = _env_catalog_files(base)
        else:
            env_files = [locales_file] if isinstance(locales_file, str) else list(locales_file)
        shared_file = SHARED_CATALOG if shared_locales_file is None else shared_locales_file
        self.catalog = load_catalog(env_files + [shared_file])
        # a language without a section in this env's catalog is an exact passthrough, shared strings included
        self._env_langs = frozenset(set().union(*self.catalog.languages[: len(env_files)]))
        if isinstance(lang, str):
            default, per_player = lang, {}
        elif isinstance(lang, dict) and all(isinstance(k, int) and isinstance(v, str) for k, v in lang.items()):
            default, per_player = SOURCE_LANG, dict(lang)
        else:
            raise TypeError("lang must be a language code or a {player_id: language code} dict")
        known = set(self._env_langs).union(*self.catalog.languages)
        for code in sorted({default, *per_player.values()} - {SOURCE_LANG}):
            if code not in known:
                raise ValueError(
                    f"Unknown language {code!r} for {self.game_name}; available: {', '.join(self.available_languages)}"
                )
            if code in self._env_langs:
                _warn_if_uncertified(code, self.game_name)
        self.lang = lang
        self._default_lang, self._player_langs = default, per_player

    @property
    def available_languages(self) -> List[str]:
        """Languages this env has translations for (English is always available)."""
        return [SOURCE_LANG] + sorted(self._env_langs)

    def language(self, player_id: int) -> str:
        """Language code configured for a player."""
        return self._player_langs.get(player_id, self._default_lang)

    def translate(self, text: str, lang: str) -> str:
        """Translate a block of game text (without sender labels) into ``lang``."""
        return self.catalog.translate_block(text, lang) if lang in self._env_langs else text

    def observation(self, player_id: int, observation):
        lang = self.language(player_id)
        if lang not in self._env_langs or not observation:
            return observation
        if isinstance(observation, str):
            return self._translate_observation(observation, lang)
        if isinstance(observation, list):  # unformatted (sender, message, type) tuples
            return [self._translate_message(item, lang) for item in observation]
        return observation

    def close(self):
        result = self.env.close()
        if not (isinstance(result, tuple) and len(result) == 2 and isinstance(result[1], dict)):
            return result
        rewards, game_info = result
        translated = {}
        for pid, info in game_info.items():
            lang = self.language(pid)
            if lang in self._env_langs and isinstance(info, dict) and isinstance(info.get("reason"), str):
                info = {**info, "reason": self.catalog.translate_block(info["reason"], lang)}
            translated[pid] = info
        return rewards, translated

    def _translate_message(self, item, lang: str):
        if not (isinstance(item, tuple) and len(item) == 3 and isinstance(item[1], str)):
            return item
        sender, message, obs_type = item
        if sender != GAME_ID and obs_type == ObservationType.PLAYER_ACTION:
            return item
        return sender, self.catalog.translate_block(message, lang), obs_type

    def _senders(self) -> Dict[str, int]:
        state = getattr(self.env, "state", None)
        senders = {f"Player {pid}": pid for pid in range(getattr(state, "num_players", 0) or 0)}
        for pid, name in (getattr(state, "role_mapping", None) or {}).items():
            if isinstance(name, str):
                senders[name] = pid
        senders["GAME"] = GAME_ID
        return senders

    def _game_authored(self) -> Set[str]:
        """Messages the game sent under a player's name (never text a player typed)."""
        authored, typed = set(), set()
        for event in getattr(getattr(self.env, "state", None), "events", None) or ():
            sender, message, obs_type = event[0], event[1], event[2]
            if sender != GAME_ID:
                (typed if obs_type == ObservationType.PLAYER_ACTION else authored).add(message)
        return authored - typed

    def _translate_observation(self, text: str, lang: str) -> str:
        senders = self._senders()
        blocks = []  # [label match or None, sender id, message lines]
        for line in text.split("\n"):
            m = _LABEL.match(line) if line.startswith("[") else None
            if m is not None and m.group(1) in senders:
                blocks.append([m, senders[m.group(1)], [line[m.end():]]])
            elif blocks:
                blocks[-1][2].append(line)
            else:
                blocks.append([None, GAME_ID, [line]])
        authored = None
        out = []
        for m, sender, lines in blocks:
            translate = sender == GAME_ID
            if not translate:
                if authored is None:
                    authored = self._game_authored()
                translate = "\n".join(lines) in authored
            if translate:
                lines = [self.catalog.translate_line(line, lang)[0] for line in lines]
            if m is not None:
                label = m.group(1)
                lines[0] = "[" + (self.catalog.translate_text(label, lang) or label) + "]" + m.group(2) + lines[0]
            out.extend(lines)
        return "\n".join(out)
