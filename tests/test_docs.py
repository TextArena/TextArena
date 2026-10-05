"""The environment docs must match the registry; run `python scripts/generate_env_docs.py` to refresh them."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_env_docs_are_in_sync_with_the_registry():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_env_docs.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
