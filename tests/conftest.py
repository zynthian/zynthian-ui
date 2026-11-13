# -*- coding: utf-8 -*-
"""Shared pytest configuration.

Goal: the default ``pytest`` run needs NO hardware, JACK server, display or
built native libraries. Anything that does is marked (see pyproject.toml) and
skipped unless explicitly enabled.
"""

import os

import pytest

# Side effects, must come before any production import: sandbox env + native fakes.
from tests import bootstrap  # noqa: F401
from tests.bootstrap import FAKE_ZYNCORE as _FAKE_ZYNCORE, NATIVE as _NATIVE  # noqa: F401

# Import order matters: zyngine.zynthian_chain_manager / zynthian_legacy_snapshot cannot be the
# first module imported (circular import, see tests/integration/test_imports.py). Importing the
# state manager first makes every later import work. Drop this once the cycle is removed.
import zyngine.zynthian_state_manager  # noqa: E402,F401


@pytest.fixture
def zyncore():
    """The fake ``lib_zyncore`` with a clean call log for each test."""
    _FAKE_ZYNCORE.reset_fake()
    yield _FAKE_ZYNCORE
    _FAKE_ZYNCORE.reset_fake()


@pytest.fixture
def native_libs():
    """Registry of fakes for the other native libraries, e.g. ``native_libs["libzynseq.so"]``."""
    _NATIVE.reset()
    yield _NATIVE
    _NATIVE.reset()


@pytest.fixture
def zynthian_dirs(tmp_path, monkeypatch):
    """Isolated ZYNTHIAN_* data directories under ``tmp_path``.

    NB: several production modules read these variables once at import time, so this only
    affects code that reads the environment lazily.
    """
    dirs = {
        "ZYNTHIAN_DIR": tmp_path,
        "ZYNTHIAN_CONFIG_DIR": tmp_path / "config",
        "ZYNTHIAN_MY_DATA_DIR": tmp_path / "my-data",
        "ZYNTHIAN_EX_DATA_DIR": tmp_path / "ex-data",
        "ZYNTHIAN_DATA_DIR": tmp_path / "data",
    }
    for key, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(key, str(path))
    (dirs["ZYNTHIAN_MY_DATA_DIR"] / "snapshots").mkdir(exist_ok=True)
    return dirs


# --- Skip tests whose environment is unavailable -----------------------------
def _have_display():
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def pytest_collection_modifyitems(config, items):
    skip_gui = pytest.mark.skip(reason="no DISPLAY (run under xvfb-run)")
    from tests.native.support import native_skip_reason
    reason = native_skip_reason()
    skip_native = pytest.mark.skip(reason=reason or "")
    skip_hw = pytest.mark.skip(reason="set ZYNTHIAN_TEST_HARDWARE=1 on a real Zynthian")
    for item in items:
        if "gui" in item.keywords and not _have_display():
            item.add_marker(skip_gui)
        # native/jack tests run the real compiled library on a private dummy jackd (tests/native)
        if reason and ("native" in item.keywords or "jack" in item.keywords):
            item.add_marker(skip_native)
        if "hardware" in item.keywords and os.environ.get("ZYNTHIAN_TEST_HARDWARE") != "1":
            item.add_marker(skip_hw)
