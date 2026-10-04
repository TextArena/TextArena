#!/usr/bin/env python3
"""Regenerate the registry-derived parts of the environment documentation.

Hand-written prose lives in ``textarena/envs/README.md`` (the catalog) and in each
``textarena/envs/<Env>/README.md``. This script only rewrites the blocks between
``<!-- BEGIN GENERATED: ... -->`` and ``<!-- END GENERATED: ... -->`` markers:

- per environment: player count, every registered env id with its parameters,
  and what the ``-mdp`` observation contains;
- in the catalog: one table per player-count category, linking every game.

Usage:
    python scripts/generate_env_docs.py          # rewrite the generated blocks
    python scripts/generate_env_docs.py --check  # exit 1 if anything is stale
"""
import argparse
import importlib
import inspect
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENVS_DIR = os.path.join(REPO_ROOT, "textarena", "envs")
sys.path.insert(0, REPO_ROOT)

from textarena.envs.registration import ENV_REGISTRY  # noqa: E402

BLOCK = re.compile(
    r"(<!-- BEGIN GENERATED: (?P<name>[\w-]+) -->\n)(?P<body>.*?)(<!-- END GENERATED: (?P=name) -->)",
    re.S,
)
MDP_VIEWS = {
    False: "the prompt, every game message and the latest board (raw player actions are left out)",
    True: "the prompt, the full transcript including every player action, and the latest board",
}


@dataclass
class EnvDoc:
    directory: str
    cls: type
    variants: Dict[str, dict] = field(default_factory=dict)

    @property
    def min_players(self) -> int:
        return self.cls.min_players

    @property
    def max_players(self) -> Optional[int]:
        return self.cls.max_players

    @property
    def players(self) -> str:
        lo, hi = self.min_players, self.max_players
        if hi is None:
            return f"{lo}+"
        return str(lo) if lo == hi else f"{lo}–{hi}"

    @property
    def category(self) -> str:
        if self.max_players == 1:
            return "single"
        if self.min_players == self.max_players == 2:
            return "two"
        return "multi"

    @property
    def readme_path(self) -> str:
        return os.path.join(ENVS_DIR, self.directory, "README.md")


def _sort_ids(ids: List[str]) -> List[str]:
    return sorted(ids, key=lambda env_id: (env_id.count("-"), env_id))


def collect() -> List[EnvDoc]:
    docs: Dict[str, EnvDoc] = {}
    for env_id, spec in ENV_REGISTRY.items():
        module_path, class_name = spec.entry_point.split(":")
        directory = module_path.split(".envs.")[1].split(".")[0]
        if directory not in docs:
            cls = getattr(importlib.import_module(module_path), class_name)
            docs[directory] = EnvDoc(directory=directory, cls=cls)
        if not env_id.endswith("-mdp"):
            docs[directory].variants[env_id] = spec.kwargs
    return [docs[name] for name in sorted(docs, key=str.lower)]


def _format_value(value) -> str:
    if inspect.isclass(value) or inspect.isfunction(value):
        return value.__name__
    if isinstance(value, str):
        return f'"{value}"'
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _format_kwargs(kwargs: dict) -> str:
    if not kwargs:
        return "defaults"
    return ", ".join(f"`{key}={_format_value(value)}`" for key, value in kwargs.items())


def env_block(doc: EnvDoc) -> str:
    ids = _sort_ids(list(doc.variants))
    lines = [
        f"**Players:** {doc.players}",
        "",
        f"**`-mdp` observation:** {MDP_VIEWS[doc.cls.mdp_includes_actions]}",
        "",
        "| Env ID | Parameters |",
        "| --- | --- |",
    ]
    lines += [f"| `{env_id}` | {_format_kwargs(doc.variants[env_id])} |" for env_id in ids]
    note = f"Append `-mdp` to any ID for the state-complete variant (e.g. `{ids[0]}-mdp`)."
    parameters = list(doc.variants[ids[0]])
    if parameters:
        note += f' Parameters can be overridden in `ta.make`, e.g. `ta.make("{ids[0]}", {parameters[0]}=...)`.'
    lines += ["", note, ""]
    return "\n".join(lines)


def _readme_title_and_summary(doc: EnvDoc):
    title, summary = doc.directory, ""
    if not os.path.exists(doc.readme_path):
        return title, summary
    with open(doc.readme_path, encoding="utf-8") as handle:
        text = BLOCK.sub("", handle.read())
    heading = re.search(r"^# (.+)$", text, re.M)
    if heading:
        title = heading.group(1).strip()
        text = text[heading.end():]
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = paragraph.strip()
        if paragraph and not paragraph.startswith(("#", "|", "<", "!", "```", ">", "-", "*")):
            url = r"\((?:[^()\s]|\([^()\s]*\))*\)"  # allows one level of parentheses, e.g. Nim_(game)
            paragraph = re.sub(r"\s*\(\[[^\]]+\]" + url + r"\)", "", " ".join(paragraph.split()))
            sentence = re.split(r"(?<=[.!?])\s", paragraph, maxsplit=1)[0]
            summary = re.sub(r"\[([^\]]+)\]" + url, r"\1", sentence).replace("**", "")
            break
    return title, summary


def catalog_block(docs: List[EnvDoc]) -> str:
    sections = [
        ("single", "Single-player"),
        ("two", "Two-player"),
        ("multi", "Multi-player"),
    ]
    lines = [f"**{len(docs)} games, {sum(len(d.variants) for d in docs)} registered configurations.**", ""]
    for key, heading in sections:
        group = [d for d in docs if d.category == key]
        lines += [f"### {heading} ({len(group)})", ""]
        lines += ["| Game | Players | Description | Env IDs |", "| --- | :---: | --- | --- |"]
        for doc in group:
            title, summary = _readme_title_and_summary(doc)
            ids = _sort_ids(list(doc.variants))
            shown = ", ".join(f"`{env_id}`" for env_id in ids[:3])
            if len(ids) > 3:
                shown += f" +{len(ids) - 3} more"
            summary = summary.replace("|", "\\|")
            lines.append(f"| [{title}]({doc.directory}/README.md) | {doc.players} | {summary} | {shown} |")
        lines.append("")
    return "\n".join(lines)


def _replace_block(text: str, name: str, body: str) -> Optional[str]:
    """Return ``text`` with the named block replaced, or None if the block is missing."""
    replaced = False

    def substitute(match):
        nonlocal replaced
        if match.group("name") != name:
            return match.group(0)
        replaced = True
        return f"{match.group(1)}{body}{match.group(4)}"

    text = BLOCK.sub(substitute, text)
    return text if replaced else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report stale files instead of writing")
    args = parser.parse_args()

    docs = collect()
    targets = {os.path.join(ENVS_DIR, "README.md"): ("catalog", catalog_block(docs))}
    missing = [doc.directory for doc in docs if not os.path.exists(doc.readme_path)]
    for doc in docs:
        if doc.directory not in missing:
            targets[doc.readme_path] = ("variants", env_block(doc))

    stale, problems = [], [f"missing README: textarena/envs/{d}/README.md" for d in missing]
    for path, (name, body) in targets.items():
        with open(path, encoding="utf-8") as handle:
            current = handle.read()
        updated = _replace_block(current, name, body)
        if updated is None:
            problems.append(f"no '{name}' generated block: {os.path.relpath(path, REPO_ROOT)}")
        elif updated != current:
            stale.append(os.path.relpath(path, REPO_ROOT))
            if not args.check:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(updated)

    for problem in problems:
        print(problem)
    for path in stale:
        print(f"{'stale' if args.check else 'updated'}: {path}")
    return 1 if problems or (args.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
