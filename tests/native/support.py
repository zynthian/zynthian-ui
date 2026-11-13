"""Locate the real zyncore library and a ``jackd`` for the ``native`` tests.

The library is built out of tree (``tests/native/build_zyncore.sh``) with the ``TOUCH_ONLY`` wiring
layout: the real ZynMidiRouter/ZynMaster code, but no wiringPi, I2C, rotaries or switches.
"""

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LIB = HERE / "build" / "libzyncore.so"


def zyncore_lib_path():
    """Path of the TOUCH_ONLY ``libzyncore.so`` (``ZYNTHIAN_TEST_ZYNCORE_LIB`` overrides), or None."""
    path = Path(os.environ.get("ZYNTHIAN_TEST_ZYNCORE_LIB") or DEFAULT_LIB)
    return path if path.is_file() else None


def native_skip_reason():
    """Why the native tests cannot run here, or None if they can."""
    if zyncore_lib_path() is None:
        return "no libzyncore.so: run tests/native/build_zyncore.sh (or set ZYNTHIAN_TEST_ZYNCORE_LIB)"
    if shutil.which("jackd") is None:
        return "jackd not installed (needed for the private dummy JACK server)"
    try:
        import jack  # noqa: F401
        import numpy  # noqa: F401
    except ImportError as e:
        return f"missing python module for the JACK harness: {e.name}"
    return None
