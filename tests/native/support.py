"""Locate the real native libraries and a ``jackd`` for the ``native`` tests.

Libraries are built out of tree by ``tests/native/build_native.sh`` into ``tests/native/build/``:
``libzyncore.so`` (TOUCH_ONLY wiring layout: the real ZynMidiRouter, no wiringPi / I2C), ``libzynseq.so``,
``libzynsmf.so``, ``libzynaudioplayer.so``, ``libzynmixer.so``, ``libzynaudio2midi.so``. ``ZYNTHIAN_TEST_<NAME>_LIB`` overrides a path.
"""

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD_DIR = HERE / "build"


def lib_path(name):
    """Path of ``lib<name>.so`` (e.g. ``"zynseq"``), or None if it is not built."""
    override = os.environ.get(f"ZYNTHIAN_TEST_{name.upper()}_LIB")
    path = Path(override) if override else BUILD_DIR / f"lib{name}.so"
    return path if path.is_file() else None


def zyncore_lib_path():
    return lib_path("zyncore")


def missing_lib_reason(name):
    if lib_path(name) is None:
        return f"lib{name}.so not built: run tests/native/build_native.sh (or set ZYNTHIAN_TEST_{name.upper()}_LIB)"
    return None


def native_skip_reason():
    """Why the native tests cannot run at all here (no jackd / python modules), or None.

    Whether a particular library is built is checked by its own fixture (``missing_lib_reason``)."""
    if shutil.which("jackd") is None:
        return "jackd not installed (needed for the private dummy JACK server)"
    try:
        import jack  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as e:
        return f"missing python module for the JACK harness: {e.name}"
    return None
