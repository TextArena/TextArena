"""
reflection_memory.py — optional Reflexion-style global lesson bank.

Purpose
-------
A persistent, append-only-with-dedup memory of short lessons distilled from
past Avalon games.  Lives at ``results/reflection_memory.json`` by default.
Used by ``tinker_multiagent.py`` as the SFT warm-start data source.

Schema (one JSON file)
----------------------
    {
      "max_entries": 200,
      "lessons": [
        {
          "text":            "Reject teams whose proposer voted approve on a failed mission.",
          "created_ts":      1.7e9,
          "last_seen_ts":    1.7e9,
          "cite_count":      3,
          "outcome_context": "won",        // "won" | "lost" | ""
          "role_context":    "Servant"     // free-form role string
        },
        ...
      ]
    }

This module deliberately does NOT integrate with ``basic_agents.py``.  You can
populate the JSON manually, via a small wrapper script, or by extending the
agent later.  Concurrent writers are serialised via a POSIX file lock.

Public API
----------
    ReflectionMemory.load(path)           – load or create
    mem.add(text, ...)                    – append lesson (deduplicates)
    mem.merge_from(other)                 – merge another bank
    mem.top_k(k)                          – ranked Lesson list
    mem.get_cheat_sheet(k, role_filter)   – formatted prompt block
    mem.size()                            – number of stored lessons
    mem.save()                            – flush to disk atomically
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional


try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:
    _HAS_FCNTL = False


_DEFAULT_MEMORY_PATH   = Path("results") / "reflection_memory.json"
_DEFAULT_MAX_ENTRIES   = 200
_DEFAULT_CHEAT_SHEET_K = 5


# ---------------------------------------------------------------------------
# File lock
# ---------------------------------------------------------------------------

class _FileLock:
    """Exclusive POSIX file lock; no-op on Windows."""

    def __init__(self, path: Path):
        self._path = Path(str(path) + ".lock")
        self._fh: Optional[Any] = None

    def __enter__(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "w")
        if _HAS_FCNTL:
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        if self._fh is None:
            return
        try:
            if _HAS_FCNTL:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None


# ---------------------------------------------------------------------------
# Lesson dataclass
# ---------------------------------------------------------------------------

@dataclass
class Lesson:
    text:             str
    created_ts:       float = field(default_factory=time.time)
    last_seen_ts:     float = field(default_factory=time.time)
    cite_count:       int   = 1
    outcome_context:  str   = ""
    role_context:     str   = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Lesson":
        return Lesson(
            text             = str(d.get("text", "")),
            created_ts       = float(d.get("created_ts",   time.time())),
            last_seen_ts     = float(d.get("last_seen_ts", time.time())),
            cite_count       = int(d.get("cite_count", 1)),
            outcome_context  = str(d.get("outcome_context", "")),
            role_context     = str(d.get("role_context",    "")),
        )


def _normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, truncate to 120 chars."""
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t[:120]


# ---------------------------------------------------------------------------
# ReflectionMemory
# ---------------------------------------------------------------------------

class ReflectionMemory:
    """Global persistent lesson bank for Avalon."""

    def __init__(
        self,
        path:        Path = _DEFAULT_MEMORY_PATH,
        max_entries: int  = _DEFAULT_MAX_ENTRIES,
        lessons:     Optional[List[Lesson]] = None,
    ):
        self.path        = Path(path)
        self.max_entries = max_entries
        self.lessons:    List[Lesson] = list(lessons) if lessons else []

    # ------------------------------------------------------------------
    # IO
    # ------------------------------------------------------------------

    @classmethod
    def load(
        cls,
        path: Path = _DEFAULT_MEMORY_PATH,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
    ) -> "ReflectionMemory":
        p = Path(path)
        if not p.is_file():
            return cls(path=p, max_entries=max_entries, lessons=[])
        try:
            with _FileLock(p):
                data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls(path=p, max_entries=max_entries, lessons=[])
        raw = data.get("lessons") or []
        lessons = [Lesson.from_dict(d) for d in raw if isinstance(d, dict)]
        return cls(
            path=p,
            max_entries=int(data.get("max_entries", max_entries)),
            lessons=lessons,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "max_entries": self.max_entries,
            "lessons":     [l.to_dict() for l in self.lessons],
        }
        with _FileLock(self.path):
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add(
        self,
        text: str,
        *,
        outcome_context: str = "",
        role_context:    str = "",
    ) -> bool:
        text = (text or "").strip()
        if not text or len(text) < 10:
            return False

        key = _normalise(text)
        now = time.time()
        for existing in self.lessons:
            if _normalise(existing.text) == key:
                existing.cite_count   += 1
                existing.last_seen_ts  = now
                return False

        self.lessons.append(Lesson(
            text             = text,
            outcome_context  = outcome_context,
            role_context     = role_context,
        ))

        if len(self.lessons) > self.max_entries:
            self.lessons.sort(key=lambda l: l.last_seen_ts)
            self.lessons = self.lessons[-self.max_entries:]
        return True

    def merge_from(self, other: "ReflectionMemory") -> int:
        added = 0
        for l in other.lessons:
            if self.add(
                l.text,
                outcome_context = l.outcome_context,
                role_context    = l.role_context,
            ):
                added += 1
        return added

    def clear(self) -> None:
        self.lessons = []

    # ------------------------------------------------------------------
    # Query / formatting
    # ------------------------------------------------------------------

    def size(self) -> int:
        return len(self.lessons)

    def top_k(self, k: int = _DEFAULT_CHEAT_SHEET_K) -> List[Lesson]:
        ranked = sorted(
            self.lessons,
            key=lambda l: (l.cite_count, l.last_seen_ts),
            reverse=True,
        )
        return ranked[:max(0, int(k))]

    def get_cheat_sheet(
        self,
        k: int = _DEFAULT_CHEAT_SHEET_K,
        role_filter: Optional[str] = None,
    ) -> str:
        if not self.lessons:
            return ""

        if role_filter:
            rf = role_filter.strip().lower()
            scored = sorted(
                self.lessons,
                key=lambda l: (
                    l.role_context.lower() == rf,
                    not l.role_context,
                    l.cite_count,
                    l.last_seen_ts,
                ),
                reverse=True,
            )
        else:
            scored = sorted(
                self.lessons,
                key=lambda l: (l.cite_count, l.last_seen_ts),
                reverse=True,
            )

        top = scored[:max(0, int(k))]
        if not top:
            return ""
        return "\n".join(f"- {l.text}" for l in top)
