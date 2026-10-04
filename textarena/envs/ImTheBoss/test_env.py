"""Tests for ImTheBoss.

FLAGGED BUG / MISSING IMPLEMENTATION: `textarena/envs/ImTheBoss/env.py` is an
empty 0-byte file and the package directory has no `__init__.py`. There is no
environment class to import or exercise, so meaningful gameplay tests cannot be
written. The placeholder test below is skipped to document this and keep the
suite green; it should be replaced once the game is implemented.
"""
import os

import pytest

_ENV_PATH = os.path.join(os.path.dirname(__file__), "env.py")


def test_env_module_is_an_empty_stub():
    # Documents the current (broken) state: env.py exists but is empty.
    assert os.path.exists(_ENV_PATH)
    assert os.path.getsize(_ENV_PATH) == 0


@pytest.mark.skip(reason="ImTheBoss/env.py is an empty 0-byte stub; no environment implemented yet.")
def test_gameplay_placeholder():
    raise AssertionError("ImTheBoss is not implemented")
