#!/usr/bin/env python
"""Catalog tooling for `textarena.wrappers.TranslationWrapper` (development only, not shipped).

    python scripts/locales.py extract [GAME ...] [--all] [--check]
    python scripts/locales.py migrate [GAME ...] [--ref origin/main] [--fresh] [--no-cross-game]
    python scripts/locales.py coverage [GAME ...] --lang de [--seeds 3] [--steps 150]
    python scripts/locales.py check

extract   regenerate the ``"en"`` section (English line templates) of ``locales.json`` from the source of each
          env that already has a catalog, plus the shared catalog, and drop translations of
          lines that no longer exist. Name games (or pass ``--all``) to create catalogs;
          ``--check`` only reports stale catalogs.
migrate   carry upstream (``origin/main``) translations over to the current templates and
          write them as ``"<lang>"`` sections of ``locales.json``. Existing valid entries are
          kept unless ``--fresh``.
coverage  seeded random rollouts through the wrapper, reporting the share of non-board
          observation lines that get translated.
check     validate every catalog file.

Use ``shared`` as the game name for the shared catalog (engine and wrapper strings).
"""
import argparse
import ast
import collections
import itertools
import json
import os
import random
import re
import string
import subprocess
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from textarena.wrappers.translation import (  # noqa: E402
    CATALOG_FILE, CONFIDENCE_PATH, SHARED_CATALOG, SOURCE_LANG, join_template, split_template, template_id,
)

ENVS_DIR = os.path.join(ROOT, "textarena", "envs")
SHARED = "shared"
SHARED_SOURCES = [
    os.path.join(ROOT, "textarena", "engine.py"),
    os.path.join(ROOT, "textarena", "wrappers", "observation_wrappers.py"),
]
DEFAULT_REF = "origin/main"
UPSTREAM_CONFIDENCE = "textarena/utils/locales/_trackb_confidence.json"


# --------------------------------------------------------------------------- extraction
# Every string expression in an env's source becomes a set of line templates: f-string
# fields and other non-literal parts become {slots}, `+` concatenations and conditional
# expressions expand into alternatives, and the result is split into stripped lines.
# Lines that do not look like UI text (dict keys, regexes, identifiers, file names) are
# dropped, except the role names returned by `roles()`, which label senders.

MAX_ALTERNATIVES = 32
LABEL_FUNCTIONS = {"roles", "_sender_name"}
_STRING_METHODS = {
    "startswith", "endswith", "split", "rsplit", "splitlines", "replace", "strip", "lstrip", "rstrip",
    "index", "find", "rfind", "count", "partition", "rpartition", "removeprefix", "removesuffix", "encode",
}
_KEY_METHODS = {"get", "pop", "setdefault"}
_SKIP_CALLS = {
    "print", "getattr", "setattr", "hasattr", "delattr", "isinstance", "issubclass", "open",
    "register", "register_with_versions", "import_module", "__import__", "TypeVar", "namedtuple",
}
_SKIP_OWNERS = {"re", "os", "path", "logging", "logger", "log", "warnings", "json", "importlib", "sys", "subprocess", "shutil", "pathlib"}
_PATTERN_TARGET = re.compile(r"(?i)pattern|regex|^re_|_re$")
_REGEX_TEXT = re.compile(r"\\[dswbDSWB.]|\(\?[:P<=!]|\[\^|\.\*|\.\+")
_WORD = re.compile(r"[^\W\d_]{2,}")
_LETTER = re.compile(r"[^\W\d_]")
_PERCENT = re.compile(r"%(?:\((\w+)\))?[-#0 +]*(?:\d+|\*)?(?:\.\d+)?([diouxXeEfFgGcrsa%])")
_REPLACED_TOKEN = re.compile(r"<[A-Z][A-Z0-9_]*>")  # filled in with str.replace, e.g. "<PLAYER_ID>"


class _Slot:
    __slots__ = ("expr",)

    def __init__(self, expr: Optional[ast.AST]):
        self.expr = expr


def _is_str(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_format_call(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "format" and _is_str(node.func.value))


def _is_texty(node) -> bool:
    if _is_str(node) or isinstance(node, ast.JoinedStr) or _is_format_call(node):
        return True
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Add):
            return _is_texty(node.left) or _is_texty(node.right)
        if isinstance(node.op, ast.Mod):
            return _is_str(node.left)
    if isinstance(node, ast.IfExp):
        return _is_texty(node.body) or _is_texty(node.orelse)
    return False


def _is_plural_suffix(node, previous) -> bool:
    """``f"card{'s' if n != 1 else ''}"``: expanded into both words instead of becoming a slot."""
    if not (isinstance(node, ast.IfExp) and _is_str(node.body) and _is_str(node.orelse)):
        return False
    values = {node.body.value, node.orelse.value}
    return "" in values and values <= {"", "s", "es"} and _is_str(previous) and previous.value[-1:].isalpha()


def _product(options: List[List[list]]) -> List[list]:
    alternatives = [[]]
    for choices in options:
        alternatives = [a + c for a in alternatives for c in choices][:MAX_ALTERNATIVES]
    return alternatives


def _format_parts(node: ast.Call) -> list:
    fmt = node.func.value.value
    args = list(node.args)
    kwargs = {k.arg: k.value for k in node.keywords if k.arg}
    try:
        parsed = list(string.Formatter().parse(fmt))
    except ValueError:
        return [fmt]
    parts, auto = [], 0
    for literal, field, _, _ in parsed:
        if literal:
            parts.append(literal)
        if field is None:
            continue
        base = re.match(r"[^.\[]*", field).group(0)
        if base == "":
            expr = args[auto] if auto < len(args) else None
            auto += 1
        elif base.isdigit():
            expr = args[int(base)] if int(base) < len(args) else None
        else:
            expr = kwargs.get(base, ast.Name(id=base, ctx=ast.Load()))
        parts.append(_Slot(expr))
    return parts


def _percent_parts(fmt: str, right: ast.AST) -> list:
    values = list(right.elts) if isinstance(right, ast.Tuple) else [right]
    parts, pos, k = [], 0, 0
    for m in _PERCENT.finditer(fmt):
        parts.append(fmt[pos:m.start()])
        if m.group(2) == "%":
            parts.append("%")
        elif m.group(1):
            parts.append(_Slot(ast.Name(id=m.group(1), ctx=ast.Load())))
        else:
            parts.append(_Slot(values[k] if k < len(values) else None))
            k += 1
        pos = m.end()
    parts.append(fmt[pos:])
    return parts


def _alternatives(node, depth: int = 0) -> List[list]:
    """Alternative texts of a string expression, as lists of literal strings and `_Slot`s."""
    if depth > 12:
        return [[_Slot(node)]]
    if _is_str(node):
        return [[node.value]]
    if isinstance(node, ast.JoinedStr):
        options = []
        for i, value in enumerate(node.values):
            if _is_str(value):
                options.append([[value.value]])
            elif isinstance(value, ast.FormattedValue):
                if _is_plural_suffix(value.value, node.values[i - 1] if i else None):
                    options.append([[value.value.body.value], [value.value.orelse.value]])
                else:
                    options.append([[_Slot(value.value)]])
            else:
                options.append([[_Slot(value)]])
        return _product(options)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and _is_texty(node):
        return _product([_alternatives(node.left, depth + 1), _alternatives(node.right, depth + 1)])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and _is_str(node.left):
        return [_percent_parts(node.left.value, node.right)]
    if isinstance(node, ast.IfExp) and _is_texty(node):
        return (_alternatives(node.body, depth + 1) + _alternatives(node.orelse, depth + 1))[:MAX_ALTERNATIVES]
    if _is_format_call(node):
        return [_format_parts(node)]
    return [[_Slot(node)]]


def _placeholders(node) -> List[ast.AST]:
    """The non-literal sub-expressions of a string expression (visited for nested strings)."""
    if _is_str(node):
        return []
    if isinstance(node, ast.JoinedStr):
        out = []
        for i, value in enumerate(node.values):
            if isinstance(value, ast.FormattedValue) and not _is_plural_suffix(value.value, node.values[i - 1] if i else None):
                out.append(value.value)
        return out
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add) and _is_texty(node):
        return _placeholders(node.left) + _placeholders(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) and _is_str(node.left):
        return [node.right]
    if isinstance(node, ast.IfExp) and _is_texty(node):
        return [node.test] + _placeholders(node.body) + _placeholders(node.orelse)
    if _is_format_call(node):
        return list(node.args) + [k.value for k in node.keywords]
    return [node]


def _slot_name(expr) -> Optional[str]:
    if isinstance(expr, ast.Name):
        name = expr.id
    elif isinstance(expr, ast.Attribute):
        name = expr.attr
    elif isinstance(expr, ast.Subscript):
        key = expr.slice
        if _is_str(key):
            name = key.value
        else:
            return _slot_name(expr.value)
    elif isinstance(expr, ast.Call):
        func = expr.func
        fname = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
        if fname in ("str", "int", "float", "repr", "round", "abs", "sorted", "list", "tuple", "set", "sum", "max", "min") and expr.args:
            return _slot_name(expr.args[0])
        if fname == "len" and expr.args:
            inner = _slot_name(expr.args[0])
            return f"num_{inner}" if inner else None
        if isinstance(func, ast.Attribute) and fname == "join" and expr.args:
            return _slot_name(expr.args[0])
        if isinstance(func, ast.Attribute) and fname in ("upper", "lower", "title", "capitalize", "strip", "format"):
            return _slot_name(func.value)
        name = fname
    else:
        return None
    name = re.sub(r"\W", "_", name or "").strip("_")
    if not name:
        return None
    return "v" + name if name[0].isdigit() else name


def _split_lines(parts: list) -> List[list]:
    lines, current = [], []
    for part in parts:
        if isinstance(part, str):
            chunks = part.split("\n")
            if chunks[0]:
                current.append(chunks[0])
            for chunk in chunks[1:]:
                lines.append(current)
                current = [chunk] if chunk else []
        else:
            current.append(part)
    lines.append(current)
    return lines


def _line_template(parts: list) -> Optional[Tuple[str, str]]:
    """(template, literal text) of one line; slots are named after their expression."""
    merged = []
    for part in parts:
        if isinstance(part, str) and merged and isinstance(merged[-1], str):
            merged[-1] += part
        else:
            merged.append(part)
    if merged and isinstance(merged[0], str):
        merged[0] = merged[0].lstrip()
        if not merged[0]:
            merged.pop(0)
    if merged and isinstance(merged[-1], str):
        merged[-1] = merged[-1].rstrip()
        if not merged[-1]:
            merged.pop()
    if not merged:
        return None
    lits, slots, by_expr, used, positional = [""], [], {}, set(), 0
    for part in merged:
        if isinstance(part, str):
            lits[-1] += part
            continue
        key = ast.dump(part.expr) if part.expr is not None else None
        name = by_expr.get(key) if key is not None else None
        if name is None:
            base = _slot_name(part.expr)
            if base is None:
                while f"v{positional}" in used:
                    positional += 1
                name = f"v{positional}"
            else:
                name, n = base, 2
                while name in used:
                    name, n = f"{base}_{n}", n + 1
            used.add(name)
            if key is not None:
                by_expr[key] = name
        slots.append(name)
        lits.append("")
    return join_template(lits, slots), " ".join(lits)


def _is_ui_text(literal: str, forced: bool) -> bool:
    if _REGEX_TEXT.search(literal):
        return False
    if forced:
        return bool(_LETTER.search(literal))
    words = [token for token in literal.split() if _WORD.search(token)]
    return len(words) >= 2 or (len(words) == 1 and literal.rstrip()[-1:] in ":!.?")


def _target_name(target) -> str:
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return ""


def _dotted(func) -> List[str]:
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    parts.append(func.id if isinstance(func, ast.Name) else "")
    return parts[::-1]


def _container_strings(node) -> List[str]:
    if _is_str(node):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [s for elt in node.elts for s in _container_strings(elt)]
    if isinstance(node, ast.Dict):
        return [s for value in node.values for s in _container_strings(value)]
    return []


class _Collector:
    """Collects line templates from one module, in source order.

    ``replaced`` holds placeholder tokens that the env fills in with ``str.replace``;
    they become slots.
    """

    def __init__(self, tree: ast.AST, replaced: Iterable[str] = ()):
        self.templates: List[str] = []
        replaced = sorted(replaced)
        self._replaced = re.compile("(" + "|".join(map(re.escape, replaced)) + ")") if replaced else None
        self._assigned = collections.defaultdict(list)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                    if _target_name(target):
                        self._assigned[_target_name(target)].append(node.value)
        self._in_labels = 0
        self.visit(tree)

    def visit(self, node, skip: bool = False):
        if isinstance(node, ast.Expr) and _is_str(node.value):
            return  # docstring
        if isinstance(node, ast.Assert):
            self.visit(node.test)
            return
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(_PATTERN_TARGET.search(_target_name(t)) for t in targets):
                return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.decorator_list + node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                self.visit(default, skip=True)
            is_label = node.name in LABEL_FUNCTIONS
            self._in_labels += is_label
            for stmt in node.body:
                self.visit(stmt)
            self._in_labels -= is_label
            return
        if isinstance(node, ast.Subscript):
            self.visit(node.value)
            if self._in_labels:
                self._follow(node.value)
            self.visit(node.slice, skip=True)
            return
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if key is not None:
                    self.visit(key, skip=True)
                self.visit(value)
            return
        if isinstance(node, ast.Compare):
            for operand in [node.left] + node.comparators:
                self.visit(operand, skip=True)
            return
        if isinstance(node, ast.Call) and not _is_format_call(node):
            self._visit_call(node)
            return
        if _is_texty(node):
            if not skip:
                self._emit(node)
            for sub in _placeholders(node):
                self.visit(sub)
            return
        if type(node).__name__ == "MatchValue":
            return
        container = isinstance(node, (ast.Tuple, ast.List, ast.Set))
        for child in ast.iter_child_nodes(node):
            self.visit(child, skip=skip and container)

    def _visit_call(self, node: ast.Call):
        path = _dotted(node.func)
        name, owners = path[-1], path[:-1]
        method = isinstance(node.func, ast.Attribute)
        skip_all = (
            (not method and name in _SKIP_CALLS)
            or (method and (name in _STRING_METHODS or name in ("register", "register_with_versions")))
            or any(owner in _SKIP_OWNERS for owner in owners)
        )
        skip_first = method and name in _KEY_METHODS
        if self._in_labels and not method and name in ("dict", "list", "tuple"):
            for arg in node.args:
                self._follow(arg)
        self.visit(node.func)
        for i, arg in enumerate(node.args):
            self.visit(arg, skip=skip_all or (skip_first and i == 0))
        for keyword in node.keywords:
            self.visit(keyword.value, skip=skip_all)

    def _emit(self, node):
        for alternative in _alternatives(node):
            if self._replaced is not None:
                alternative = self._expand_replaced(alternative)
            for parts in _split_lines(alternative):
                built = _line_template(parts)
                if built and _is_ui_text(built[1], forced=self._in_labels > 0):
                    self.templates.append(built[0])

    def _expand_replaced(self, parts: list) -> list:
        out = []
        for part in parts:
            if not isinstance(part, str):
                out.append(part)
                continue
            for i, piece in enumerate(self._replaced.split(part)):
                if i % 2:
                    out.append(_Slot(ast.Name(id=piece[1:-1].lower(), ctx=ast.Load())))
                elif piece:
                    out.append(piece)
        return out

    def _follow(self, expr):
        """Role names looked up from a module/class constant, e.g. ``self.PLAYER_COLORS[i]``."""
        for value in self._assigned.get(_target_name(expr), ()):
            for text in _container_strings(value):
                if _LETTER.search(text) and not _REGEX_TEXT.search(text):
                    self.templates.append(join_template([text.strip()], []))


def extract_templates(paths: Iterable[str]) -> List[str]:
    """Line templates found in the given Python files, in source order (with duplicates)."""
    trees = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            trees.append(ast.parse(f.read(), filename=path))
    replaced = {
        node.args[0].value
        for tree in trees for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "replace"
        and node.args and _is_str(node.args[0]) and _REPLACED_TOKEN.fullmatch(node.args[0].value)
    }
    return [t for tree in trees for t in _Collector(tree, replaced).templates]


def shape(template: str) -> str:
    """Template text with slot names erased (repeated slots stay distinguishable)."""
    lits, slots = split_template(template)
    order: Dict[str, int] = {}
    out = [lits[0]]
    for slot, lit in zip(slots, lits[1:]):
        out.append("\x00%d\x00" % order.setdefault(slot, len(order)))
        out.append(lit)
    return "".join(out)


_QUOTE_CHARS = str.maketrans({c: "'" for c in "\"`‘’‚‛“”„‟"})


def canonical(template: str) -> str:
    """Comparison key across catalogs: slots erased, whitespace and quote characters normalized."""
    lits, _ = split_template(template)
    return " ".join("\x00".join(lits).translate(_QUOTE_CHARS).split())


def build_catalog(paths: Iterable[str]) -> Dict[str, str]:
    """``{id: template}`` for the given sources; one template per shape, in source order."""
    chosen: Dict[str, str] = {}
    for text in extract_templates(paths):
        key = shape(text)
        if key not in chosen or text < chosen[key]:
            chosen[key] = text  # dict keeps first-seen order; the representative is the smallest text
    catalog: Dict[str, str] = {}
    for text in chosen.values():
        tid = template_id(text)
        if catalog.get(tid, text) != text:
            raise RuntimeError(f"template id collision: {text!r} vs {catalog[tid]!r}")
        catalog[tid] = text
    return catalog


# --------------------------------------------------------------------------- catalogs on disk

def game_names() -> List[str]:
    return sorted(
        name for name in os.listdir(ENVS_DIR)
        if os.path.isfile(os.path.join(ENVS_DIR, name, "__init__.py")) and not name.startswith("_")
    )


def catalog_path(name: str) -> str:
    return SHARED_CATALOG if name == SHARED else os.path.join(ENVS_DIR, name, CATALOG_FILE)


def source_files(name: str) -> List[str]:
    if name == SHARED:
        return list(SHARED_SOURCES)
    files = []
    for dirpath, dirnames, filenames in os.walk(os.path.join(ENVS_DIR, name)):
        dirnames[:] = sorted(d for d in dirnames if d not in ("__pycache__", "locales") and not d.startswith("."))
        files.extend(os.path.join(dirpath, f) for f in sorted(filenames) if f.endswith(".py") and not f.startswith("test_"))
    return files


def catalog_names() -> List[str]:
    """The shared catalog plus every game that has a ``locales.json``."""
    return [SHARED] + [g for g in game_names() if os.path.isfile(catalog_path(g))]


def dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def canonical_catalog(sections: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """``en`` first, then languages sorted, ids sorted within each; empty languages dropped."""
    langs = [SOURCE_LANG] + sorted(lang for lang, entries in sections.items() if lang != SOURCE_LANG and entries)
    return {lang: dict(sorted(sections.get(lang, {}).items())) for lang in langs}


def read_catalog(name: str) -> Dict[str, Dict[str, str]]:
    """``{lang: {id: text}}`` of a catalog; empty if it does not exist yet."""
    try:
        data = read_json(catalog_path(name))
    except FileNotFoundError:
        return {}
    return {lang: dict(entries) for lang, entries in data.items() if isinstance(entries, dict)}


def write_catalog(name: str, sections: Dict[str, Dict[str, str]]) -> bool:
    return write_text(catalog_path(name), dumps(canonical_catalog(sections)))


def write_text(path: str, text: str) -> bool:
    """Write ``text`` unless the file already holds it; returns whether the file changed."""
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    except FileNotFoundError:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def _rel(path: str) -> str:
    return os.path.relpath(path, ROOT)


def _resolve_names(names: Sequence[str]) -> List[str]:
    known = set(game_names())
    unknown = [n for n in names if n != SHARED and n not in known]
    if unknown:
        raise SystemExit(f"unknown game(s): {', '.join(unknown)}")
    return list(dict.fromkeys(names))


def prune_translations(sections: Dict[str, Dict[str, str]], catalog: Dict[str, str]) -> int:
    """Drop translations whose English line no longer exists (in place); returns how many were dropped."""
    dropped = 0
    for lang, entries in sections.items():
        if lang == SOURCE_LANG:
            continue
        kept = {
            tid: text for tid, text in entries.items()
            if tid in catalog and isinstance(text, str) and text.strip()
            and set(split_template(text)[1]) == set(split_template(catalog[tid])[1])
        }
        dropped += len(entries) - len(kept)
        sections[lang] = kept
    return dropped


def cmd_extract(names: Sequence[str], check: bool = False, all_games: bool = False) -> int:
    if names:
        names = _resolve_names(names)
    else:
        names = [SHARED] + game_names() if all_games else catalog_names()
    stale = []
    for name in names:
        catalog = build_catalog(source_files(name))
        sections = read_catalog(name)
        if check:
            if list(sections.get(SOURCE_LANG, {}).items()) != sorted(catalog.items()):
                stale.append(name)
            continue
        sections[SOURCE_LANG] = catalog
        dropped = prune_translations(sections, catalog)
        if write_catalog(name, sections):
            print(f"updated {_rel(catalog_path(name))} ({len(catalog)} templates, {dropped} orphaned translations dropped)")
    if check:
        if stale:
            print(f"stale English templates for: {', '.join(stale)}\n"
                  f"run `python scripts/locales.py extract` (then `migrate` to pick up upstream translations)")
            return 1
        print(f"{len(names)} catalogs up to date")
    return 0


# --------------------------------------------------------------------------- migration

_BRACKET_TOKEN = re.compile(r"\[[^\[\]\n]*\]")
_QUOTED = re.compile(r"(?<![\w'])'([^'\n]+?)'(?![\w'])|\"([^\"\n]+?)\"|`([^`\n]+?)`")

SKIP_REASONS = {
    "line_count_mismatch": "entry has a different number of lines in the translation",
    "no_matching_template": "English line no longer exists in our env text",
    "bracket_token_missing": "dropped [bracketed] token not found in the translation",
    "slot_mismatch": "slots differ between upstream English, translation and our template",
    "command_token_changed": "a quoted command token of our template is missing from the translation",
    "empty_translation": "translation is empty",
    "superseded": "another upstream translation was chosen for the same line",
    "game_removed": "the game no longer exists here",
}


def has_words(line: str) -> bool:
    lits, _ = split_template(line)
    return bool(_WORD.search(" ".join(lits)))


def quoted_tokens(template: str) -> List[str]:
    return [next(g for g in m.groups() if g is not None) for m in _QUOTED.finditer(template)]


def unbracket_variants(line: str) -> List[Tuple[str, Tuple[Tuple[str, str], ...]]]:
    """``line`` with upstream's bracketed action tokens rewritten the way our envs show actions.

    Each ``[token]`` is kept, loses its brackets (``'[4]'`` -> ``'4'``) or has them replaced by
    quotes (``[coup x]`` -> ``'coup x'``). Returns ``(variant, ((token, replacement), ...))``.
    """
    tokens = list(dict.fromkeys(_BRACKET_TOKEN.findall(line)))
    if not tokens:
        return []
    if len(tokens) > 5:
        plans = [[(t, t[1:-1]) for t in tokens], [(t, "'" + t[1:-1] + "'") for t in tokens]]
    else:
        options = [[None, (t, t[1:-1]), (t, "'" + t[1:-1] + "'")] for t in tokens]
        plans = [[c for c in combo if c is not None] for combo in itertools.product(*options)][1:]
    out = []
    for plan in plans:
        variant = line
        for token, replacement in plan:
            variant = variant.replace(token, replacement)
        out.append((variant, tuple(plan)))
    return out


def convert(en_line: str, tr_line: str, template: str,
            rewrites: Sequence[Tuple[str, str]] = ()) -> Tuple[Optional[str], Optional[str]]:
    """Turn an upstream (English, translation) line pair into a translation of ``template``.

    ``rewrites`` lists ``(bracketed token, our form)`` pairs for action tokens whose markup our
    template changed; the translation must contain each token verbatim. Returns
    ``(translation, None)`` or ``(None, skip reason)``.
    """
    translation = tr_line.strip()
    if not translation:
        return None, "empty_translation"
    for token, replacement in rewrites:
        if token not in translation:
            return None, "bracket_token_missing"
        translation = translation.replace(token, replacement)
    _, upstream_slots = split_template(en_line)
    _, our_slots = split_template(template)
    if len(upstream_slots) != len(our_slots):
        return None, "slot_mismatch"
    mapping: Dict[str, str] = {}
    for theirs, ours in zip(upstream_slots, our_slots):
        if mapping.setdefault(theirs, ours) != ours:
            return None, "slot_mismatch"
    if len(set(mapping.values())) != len(mapping):
        return None, "slot_mismatch"
    lits, slots = split_template(translation)
    if set(slots) != set(mapping):
        return None, "slot_mismatch"
    text = join_template(lits, [mapping[s] for s in slots])
    if any(token not in text for token in quoted_tokens(template)):
        return None, "command_token_changed"
    return text, None


def _git(*args: str, data: Optional[bytes] = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, input=data, capture_output=True, check=True).stdout


def _read_blobs(shas: Sequence[str]) -> Dict[str, bytes]:
    data = _git("cat-file", "--batch", data="".join(s + "\n" for s in shas).encode())
    blobs, pos = {}, 0
    for sha in shas:
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        if len(header) < 3:
            pos = end + 1
            continue
        size = int(header[2])
        blobs[sha] = data[end + 1:end + 1 + size]
        pos = end + 1 + size + 1
    return blobs


def flatten(node, prefix: str = "") -> Dict[str, str]:
    """Nested upstream locale dict -> ``{"a.b": text}``; ``_``-prefixed keys are metadata."""
    out: Dict[str, str] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).startswith("_"):
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, str):
                out[path] = value
            elif isinstance(value, dict):
                out.update(flatten(value, path))
    return out


def read_upstream(ref: str) -> Dict[str, Dict[str, Dict[str, str]]]:
    """``{catalog: {lang: {flat key: text}}}`` for every upstream locale file at ``ref``."""
    listing = _git("ls-tree", "-r", "-z", ref, "--", "textarena/envs", "textarena/utils/locales")
    entries = []
    for record in listing.split(b"\0"):
        if not record:
            continue
        meta, path = record.split(b"\t", 1)
        _, kind, sha = meta.split()
        m = re.fullmatch(r"textarena/(?:envs/([^/]+)|utils)/locales/([^/_][^/]*)\.json", path.decode())
        if m and kind == b"blob":
            entries.append((m.group(1) or SHARED, m.group(2), sha.decode()))
    blobs = _read_blobs([sha for _, _, sha in entries])
    upstream: Dict[str, Dict[str, Dict[str, str]]] = collections.defaultdict(dict)
    for name, lang, sha in entries:
        try:
            upstream[name][lang] = flatten(json.loads(blobs[sha].decode("utf-8")))
        except (KeyError, ValueError):
            continue
    return dict(upstream)


def read_upstream_confidence(ref: str) -> Dict[str, dict]:
    try:
        data = json.loads(_git("show", f"{ref}:{UPSTREAM_CONFIDENCE}").decode("utf-8"))
    except (subprocess.CalledProcessError, ValueError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, dict)}


def confidence_text(records: Dict[str, dict]) -> str:
    comment = (
        "Confidence of the open-model machine translations (upstream Track B, _trackb_confidence.json): "
        "forward MT checked by two independent LLM meaning judges, not by native speakers. "
        "CERTIFIED_FLAGGED: verified, confirmed divergences reverted to English, flagged_games had residual "
        "divergences. EXPERIMENTAL: playable but meaning not certified. CERTIFIED is reserved for "
        "native-reviewed (Track A) languages, which are not listed. Generated by scripts/locales.py migrate."
    )
    lines = [f"  {json.dumps('_comment')}: {json.dumps(comment)}"]
    for lang in sorted(records):
        rec = records[lang]
        compact = {"name": rec.get("name", lang), "tier": rec.get("tier"), "flagged_games": sorted(rec.get("flagged_games", []))}
        lines.append(f"  {json.dumps(lang)}: {json.dumps(compact, ensure_ascii=False)}")
    return "{\n" + ",\n".join(lines) + "\n}\n"


class _Index:
    """Our templates keyed by canonical text, for one catalog."""

    def __init__(self, catalog: Dict[str, str]):
        self.by_canonical: Dict[str, List[str]] = collections.defaultdict(list)
        for tid, text in catalog.items():
            self.by_canonical[canonical(text)].append(tid)


Rewrites = Tuple[Tuple[str, str], ...]


def lookup(en_line: str, indexes: Sequence[Tuple[str, "_Index"]]) -> List[Tuple[str, str, Rewrites]]:
    """``(catalog, template id, action-token rewrites)`` for an upstream English line.

    Exact matches win over ones that rewrite bracketed tokens; earlier catalogs win over later ones.
    """
    key = canonical(en_line)
    for name, index in indexes:
        if key in index.by_canonical:
            return [(name, tid, ()) for tid in index.by_canonical[key]]
    for variant, rewrites in unbracket_variants(en_line):
        key = canonical(variant)
        for name, index in indexes:
            if key in index.by_canonical:
                return [(name, tid, rewrites) for tid in index.by_canonical[key]]
    return []


def pair_lines(english: str, translated: str) -> Optional[List[Tuple[str, str]]]:
    """Line pairs of one upstream entry, or None when the lines cannot be aligned.

    A translation that only dropped or added blank lines is aligned on its non-blank lines.
    """
    en_lines, tr_lines = english.split("\n"), translated.split("\n")
    if len(en_lines) != len(tr_lines):
        en_lines = [line for line in en_lines if line.strip()]
        tr_lines = [line for line in tr_lines if line.strip()]
        if len(en_lines) != len(tr_lines):
            return None
    return list(zip(en_lines, tr_lines))


def _upstream_entries(upstream: Dict[str, Dict[str, Dict[str, str]]]):
    """``(source, lang, english, translation)`` for every translated upstream entry, in a fixed order."""
    for source in sorted(upstream):
        english = upstream[source].get(SOURCE_LANG, {})
        for lang in sorted(upstream[source]):
            if lang == SOURCE_LANG:
                continue
            translated = upstream[source][lang]
            for key in sorted(english):
                if key in translated:
                    yield source, lang, english[key], translated[key]


def _choose(candidates: List[Tuple[int, int, str]]) -> Tuple[str, int]:
    """Best (tier, rewritten) rank first, then the most frequent text, then the first seen."""
    rank = min((tier, rewritten) for tier, rewritten, _ in candidates)
    pool = [text for tier, rewritten, text in candidates if (tier, rewritten) == rank]
    counts = collections.Counter(pool)
    top = max(counts.values())
    return next(text for text in pool if counts[text] == top), rank[0]


def plan_migration(upstream: Dict[str, Dict[str, Dict[str, str]]], catalogs: Dict[str, Dict[str, str]],
                   cross_game: bool = True):
    """Translations for our ``catalogs`` derived from ``upstream`` locale data.

    ``upstream`` is ``{catalog: {lang: {flat key: text}}}`` and ``catalogs`` is
    ``{catalog: {id: template}}``. Returns ``(chosen, stats)`` where ``chosen`` maps
    ``(catalog, lang, id)`` to ``(translation, tier)``: tier 0 comes from the same
    catalog upstream, 1 from a game's upstream file into the shared catalog, 2 from
    another game's upstream translation of the same line.
    """
    indexes = {name: _Index(cat) for name, cat in catalogs.items()}
    stats = collections.Counter()

    # Pass 1: each upstream line goes to the same catalog here, else to the shared one.
    candidates: Dict[Tuple[str, str, str], List[Tuple[int, int, str]]] = collections.defaultdict(list)
    converted_lines = []  # (lang, [(catalog, id, text), ...]) per converted upstream line
    for source, lang, english, translated in _upstream_entries(upstream):
        content = sum(1 for line in english.split("\n") if has_words(line))
        stats["seen"] += content
        pairs = pair_lines(english, translated)
        if pairs is None:
            stats["line_count_mismatch"] += content
            continue
        if len(pairs) != english.count("\n") + 1:
            stats["realigned"] += content
        if source not in indexes:
            stats["game_removed"] += content
            continue
        own = [(n, indexes[n]) for n in dict.fromkeys([source, SHARED]) if n in indexes]
        for en_line, tr_line in pairs:
            if not has_words(en_line):
                continue
            hits = lookup(en_line, own)
            if not hits:
                stats["no_matching_template"] += 1
                continue
            converted, reason = [], None
            for name, tid, rewrites in hits:
                text, why = convert(en_line, tr_line, catalogs[name][tid], rewrites)
                if text is None:
                    reason = reason or why
                    continue
                converted.append((name, tid, text))
                candidates[(name, lang, tid)].append((0 if name == source else 1, int(bool(rewrites)), text))
            if converted:
                converted_lines.append((lang, converted))
            else:
                stats[reason] += 1
    chosen = {key: _choose(cands) for key, cands in candidates.items()}
    for lang, converted in converted_lines:
        carried = any(chosen[(name, lang, tid)][0] == text for name, tid, text in converted)
        stats["carried" if carried else "superseded"] += 1

    # Pass 2: lines still untranslated take the translation another game used for the same line.
    if cross_game:
        pool: Dict[str, List[Tuple[str, str, str, str, Rewrites]]] = collections.defaultdict(list)
        for source, lang, english, translated in _upstream_entries(upstream):
            for en_line, tr_line in pair_lines(english, translated) or ():
                if has_words(en_line):
                    pool[canonical(en_line)].append((source, lang, en_line, tr_line, ()))
                    for variant, rewrites in unbracket_variants(en_line):
                        pool[canonical(variant)].append((source, lang, en_line, tr_line, rewrites))
        for name in sorted(catalogs):
            for tid, template in catalogs[name].items():
                by_lang: Dict[str, List[Tuple[int, int, str]]] = collections.defaultdict(list)
                for source, lang, en_line, tr_line, rewrites in pool.get(canonical(template), ()):
                    if source == name or (name, lang, tid) in chosen:
                        continue
                    text, _ = convert(en_line, tr_line, template, rewrites)
                    if text is not None:
                        by_lang[lang].append((2, int(bool(rewrites)), text))
                for lang, cands in by_lang.items():
                    chosen[(name, lang, tid)] = _choose(cands)
    return chosen, stats


def cmd_migrate(names: Sequence[str], ref: str = DEFAULT_REF, fresh: bool = False, cross_game: bool = True) -> int:
    upstream = read_upstream(ref)
    local = set(game_names())
    available = sorted(n for n in upstream if n == SHARED or n in local)
    targets = _resolve_names(names) if names else available
    catalogs = {name: build_catalog(source_files(name)) for name in sorted(set(available) | set(targets) | {SHARED})}
    chosen, stats = plan_migration(upstream, catalogs, cross_game=cross_game)

    tiers = collections.Counter()
    languages, games_with = set(), set()
    for name in targets:
        catalog = catalogs[name]
        current = read_catalog(name)
        sections = {SOURCE_LANG: catalog}
        langs = {lang for (n, lang, _) in chosen if n == name} | (set(current) - {SOURCE_LANG})
        for lang in sorted(langs):
            existing = {} if fresh else current.get(lang, {})
            entries = {}
            for tid, template in catalog.items():
                old = existing.get(tid)
                if isinstance(old, str) and old.strip() and set(split_template(old)[1]) == set(split_template(template)[1]):
                    entries[tid] = old
                    tiers["kept"] += 1
                elif (name, lang, tid) in chosen:
                    entries[tid], tier = chosen[(name, lang, tid)]
                    tiers[tier] += 1
            if entries:
                sections[lang] = entries
                languages.add(lang)
                games_with.add(name)
        if write_catalog(name, sections):
            print(f"updated {_rel(catalog_path(name))}")
        if name == SHARED:
            records = read_upstream_confidence(ref)
            if records:
                write_text(CONFIDENCE_PATH, confidence_text(records))

    print(f"\nupstream: {len(upstream) - (SHARED in upstream)} games + shared strings at {ref}")
    print(f"migrated: {len(games_with)} catalogs, {len(languages)} languages")
    print(f"upstream lines seen (same game or shared): {stats['seen']}")
    print(f"  carried over: {stats['carried']}")
    print(f"  (lines in entries aligned on non-blank lines because only blank lines differed: {stats['realigned']})")
    for reason in SKIP_REASONS:
        if stats[reason]:
            print(f"  skipped {reason}: {stats[reason]}  ({SKIP_REASONS[reason]})")
    print(f"entries: {tiers[0]} from the same game, {tiers[1]} from game files into shared, "
          f"{tiers[2]} from other games, {tiers['kept']} kept from existing files")
    return 0


# --------------------------------------------------------------------------- coverage

COVERAGE_SKIP = {"Debate", "ScenarioPlanning", "GuessWho", "TwentyQuestions"}  # need network agents
NUM_PLAYERS = {"ScorableGames": 6}
ACTION_POOL = ["0", "1", "2", "3", "4", "a1", "roll", "call", "Bid: 1, 2", "accept", "fold", "check",
               "pass", "hold", "b2 c3", "e2e4", "nonsense"]
_QUOTED_ACTION = re.compile(r"'([^'\n]{1,40})'")


def _env_id(game: str) -> Optional[str]:
    from textarena.envs.registration import ENV_REGISTRY
    ids = [i for i, spec in ENV_REGISTRY.items() if f".envs.{game}." in str(spec.entry_point) and not i.endswith("-mdp")]
    return min(ids, key=lambda i: (len(i), i)) if ids else None


def _action_candidates(state, player_id: int) -> List[str]:
    found = []
    for sender, message, _, to in state.events[-40:]:
        if sender == -1 and to in (-1, player_id):
            found.extend(_QUOTED_ACTION.findall(message))
    return found


def coverage(game: str, lang: str, seeds: int = 3, steps: int = 150):
    """(lines, matched, translated, untranslated Counter) over seeded random rollouts."""
    import textarena as ta
    from textarena.core import ObservationType
    from textarena.wrappers.translation import TranslationWrapper, _unwrap

    env_id = _env_id(game)
    if env_id is None:
        raise ValueError(f"no registered env for {game}")
    lines = matched = translated = 0
    untranslated = collections.Counter()
    for seed in range(seeds):
        env = TranslationWrapper(ta.make(env_id), lang=lang)
        base = _unwrap(env)
        env.reset(num_players=NUM_PLAYERS.get(game, type(base).min_players), seed=seed)
        rng = random.Random(seed)
        for _ in range(steps):
            player_id, _ = env.get_observation()
            options = _action_candidates(base.state, player_id)
            action = rng.choice(options) if options and rng.random() < 0.7 else rng.choice(ACTION_POOL)
            done, _ = env.step(action)
            if done:
                break
        env.get_observation()
        env.close()
        for sender, message, obs_type, _ in base.state.events:
            if obs_type in (ObservationType.PLAYER_ACTION, ObservationType.GAME_BOARD):
                continue
            for line in message.split("\n"):
                core = line.strip()
                if len(re.findall(r"[A-Za-z]{2,}", core)) < 2:
                    continue  # board art and numbers
                lines += 1
                hit = bool(env.catalog.match(core))
                matched += hit
                if env.catalog.translate_line(line, lang)[1]:
                    translated += 1
                else:
                    untranslated[(core, "untranslated" if hit else "no template")] += 1
    return lines, matched, translated, untranslated


def cmd_coverage(names: Sequence[str], lang: str, seeds: int, steps: int, top: int) -> int:
    games = _resolve_names(names) if names else [g for g in catalog_names() if g != SHARED]
    games = [g for g in games if g not in COVERAGE_SKIP and g != SHARED]
    total = [0, 0, 0]
    print(f"{'game':28s} {'lines':>6s} {'matched':>8s} {'translated':>10s}   ({lang})")
    for game in games:
        try:
            lines, matched, translated, untranslated = coverage(game, lang, seeds, steps)
        except Exception as exc:  # report and continue with the other games
            print(f"{game:28s} ERROR {type(exc).__name__}: {exc}")
            continue
        total = [total[0] + lines, total[1] + matched, total[2] + translated]
        print(f"{game:28s} {lines:6d} {_percent(matched, lines):>8s} {_percent(translated, lines):>10s}")
        for (line, why), count in untranslated.most_common(top):
            print(f"      x{count:<3d} [{why}] {line[:110]}")
    print(f"{'TOTAL':28s} {total[0]:6d} {_percent(total[1], total[0]):>8s} {_percent(total[2], total[0]):>10s}")
    return 0


def _percent(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "-"


# --------------------------------------------------------------------------- check

def check_catalogs() -> List[str]:
    problems = []
    for name in [SHARED] + game_names():
        legacy = os.path.join(os.path.dirname(catalog_path(name)), "locales")
        if os.path.isdir(legacy):
            problems.append(f"{_rel(legacy)}: per-language folders are replaced by {CATALOG_FILE}")
    try:
        if not isinstance(read_json(CONFIDENCE_PATH), dict):
            problems.append(f"{_rel(CONFIDENCE_PATH)}: not a JSON object")
    except FileNotFoundError:
        pass
    except ValueError as exc:
        problems.append(f"{_rel(CONFIDENCE_PATH)}: invalid JSON ({exc})")
    for name in catalog_names():
        path = _rel(catalog_path(name))
        try:
            with open(catalog_path(name), encoding="utf-8") as f:
                text = f.read()
            data = json.loads(text)
        except FileNotFoundError:
            problems.append(f"{path}: missing")
            continue
        except ValueError as exc:
            problems.append(f"{path}: invalid JSON ({exc})")
            continue
        if not isinstance(data, dict) or not all(isinstance(v, dict) for v in data.values()):
            problems.append(f"{path}: not a {{language: {{id: text}}}} object")
            continue
        if SOURCE_LANG not in data:
            problems.append(f"{path}: missing the {SOURCE_LANG!r} section")
            continue
        if text != dumps(canonical_catalog(data)):
            problems.append(f"{path}: not in canonical form (en first, languages and ids sorted, 2-space indent)")
        english = data[SOURCE_LANG]
        for tid, template in english.items():
            if not isinstance(template, str) or template_id(template) != tid:
                problems.append(f"{path} [{SOURCE_LANG}]: id {tid} does not match its template")
        for lang, entries in data.items():
            if lang == SOURCE_LANG:
                continue
            for tid, text in entries.items():
                if tid not in english:
                    problems.append(f"{path} [{lang}]: id {tid} is not an English template")
                elif not isinstance(text, str) or not text.strip():
                    problems.append(f"{path} [{lang}]: empty translation for {tid}")
                elif set(split_template(text)[1]) != set(split_template(english[tid])[1]):
                    problems.append(f"{path} [{lang}]: slots of {tid} differ from {english[tid]!r}")
    return problems


def cmd_check() -> int:
    problems = check_catalogs()
    for problem in problems[:200]:
        print(problem)
    if len(problems) > 200:
        print(f"... and {len(problems) - 200} more")
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


# --------------------------------------------------------------------------- CLI

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("extract", help="regenerate the English templates from env source")
    p.add_argument("games", nargs="*")
    p.add_argument("--all", action="store_true", help="every env, including ones without a catalog")
    p.add_argument("--check", action="store_true", help="fail if any English templates are stale")
    p = sub.add_parser("migrate", help="carry over upstream translations")
    p.add_argument("games", nargs="*")
    p.add_argument("--ref", default=DEFAULT_REF)
    p.add_argument("--fresh", action="store_true", help="ignore existing translation files")
    p.add_argument("--no-cross-game", action="store_true", help="only use the same game's upstream translations")
    p = sub.add_parser("coverage", help="share of observation lines translated in random rollouts")
    p.add_argument("games", nargs="*")
    p.add_argument("--lang", required=True)
    p.add_argument("--seeds", type=int, default=3)
    p.add_argument("--steps", type=int, default=150)
    p.add_argument("--top", type=int, default=0, help="show the N most frequent untranslated lines per game")
    sub.add_parser("check", help="validate every catalog")
    args = parser.parse_args(argv)
    if args.command == "extract":
        return cmd_extract(args.games, check=args.check, all_games=args.all)
    if args.command == "migrate":
        return cmd_migrate(args.games, ref=args.ref, fresh=args.fresh, cross_game=not args.no_cross_game)
    if args.command == "coverage":
        return cmd_coverage(args.games, args.lang, args.seeds, args.steps, args.top)
    return cmd_check()


if __name__ == "__main__":
    sys.exit(main())
