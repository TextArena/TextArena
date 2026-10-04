"""Keep the code importable on the oldest supported Python (3.10).

The suite usually runs on a newer interpreter, which happily accepts syntax that
3.10/3.11 reject. f-strings are the usual culprit: before Python 3.12 (PEP 701)
an f-string expression may not reuse the enclosing quote character, contain a
backslash, or contain a comment.
"""
import ast
import io
import sys
import tokenize
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted(
    path
    for folder in ("textarena", "scripts", "examples", "tests")
    for path in (ROOT / folder).rglob("*.py")
    if "__pycache__" not in path.parts
)


def _quote_style(token_string: str) -> str:
    body = token_string.lstrip("rRbBuUfF")
    return body[:3] if body[:3] in ('"""', "'''") else body[:1]


def _conflicts(outer: str, inner: str) -> bool:
    return inner == outer if len(outer) == 3 else inner[0] == outer


def pre_312_fstring_problems(source: str):
    problems, enclosing = [], []
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type == tokenize.FSTRING_END:
            enclosing.pop()
            continue
        if enclosing and tok.type != tokenize.FSTRING_MIDDLE:
            if tok.type in (tokenize.STRING, tokenize.FSTRING_START):
                style = _quote_style(tok.string)
                if any(_conflicts(outer, style) for outer in enclosing):
                    problems.append((tok.start[0], "reuses the enclosing f-string quote"))
            if "\\" in tok.string and tok.type != tokenize.FSTRING_START:
                problems.append((tok.start[0], "has a backslash inside an f-string expression"))
            if tok.type == tokenize.COMMENT:
                problems.append((tok.start[0], "has a comment inside an f-string expression"))
        if tok.type == tokenize.FSTRING_START:
            enclosing.append(_quote_style(tok.string))
    return problems


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_source_parses_with_python_310_grammar(path):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 10))


@pytest.mark.skipif(sys.version_info < (3, 12), reason="older interpreters reject these f-strings on import")
@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_fstrings_are_valid_before_python_312(path):
    problems = pre_312_fstring_problems(path.read_text(encoding="utf-8"))
    assert not problems, "\n".join(f"{path.name}:{line} {why}" for line, why in problems)


@pytest.mark.skipif(sys.version_info < (3, 12), reason="needs the PEP 701 tokenizer")
@pytest.mark.parametrize(
    "source, expected",
    [
        ('x = f"{d["a"]}"\n', 1),
        ("x = f'{chr(10).join(\"\\\\n\")}'\n", 1),
        ("x = f\"{d['a']}\"\n", 0),
        ('x = f"""{d["a"]}"""\n', 0),
        ("x = f'{a:>{width}}'\n", 0),
    ],
)
def test_pre_312_fstring_detector(source, expected):
    assert len(pre_312_fstring_problems(source)) == expected
