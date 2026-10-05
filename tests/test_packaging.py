"""Every data file an environment reads must ship in the built package."""
import fnmatch
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "textarena"


def _manifest_patterns():
    patterns = []
    for line in (ROOT / "MANIFEST.in").read_text().splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "recursive-include":
            base = parts[1].rstrip("/")
            patterns.extend((base, glob) for glob in parts[2:])
    return patterns


def test_manifest_ships_every_package_file_type():
    patterns = _manifest_patterns()
    unshipped = []
    for path in PACKAGE.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.name == "README.md" or path.suffix == ".pyc":
            continue
        relative = path.relative_to(ROOT).as_posix()
        if not any(
            relative.startswith(base + "/") and fnmatch.fnmatch(path.name, glob) for base, glob in patterns
        ):
            unshipped.append(relative)
    assert not unshipped, f"add these file types to MANIFEST.in: {sorted({Path(p).suffix for p in unshipped})} e.g. {unshipped[:5]}"


def test_manifest_patterns_are_well_formed():
    assert all(re.fullmatch(r"[\w./*-]+", glob) for _, glob in _manifest_patterns())
