# -*- coding: utf-8 -*-
"""Make ``zyngine``/``zyngui``/``zynlibs`` importable without hardware.

Importing this module (it has side effects, on purpose) must happen BEFORE any
production module is imported:

* creates a throw-away sandbox and points every ZYNTHIAN_* directory at it,
* forbids JACK from auto-starting a server,
* replaces ``zyncoder.zyncore`` and every ``libzyn*.so`` loaded through ctypes
  with recording fakes (tests/fakes).

pytest gets it through tests/conftest.py; subprocess based tests do
``import tests.bootstrap`` as their first line.
"""

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# --- Environment expected by production modules at import time ---------------
SANDBOX = Path(tempfile.mkdtemp(prefix="zynthian-tests-"))
atexit.register(shutil.rmtree, SANDBOX, ignore_errors=True)
os.environ.setdefault("ZYNTHIAN_DIR", str(SANDBOX))
os.environ["ZYNTHIAN_UI_DIR"] = str(REPO_ROOT)  # zynthian_midi_filter appends this to sys.path
os.environ.setdefault("ZYNTHIAN_CONFIG_DIR", str(SANDBOX / "config"))
os.environ.setdefault("ZYNTHIAN_MY_DATA_DIR", str(SANDBOX / "my-data"))
os.environ.setdefault("ZYNTHIAN_EX_DATA_DIR", str(SANDBOX / "ex-data"))
os.environ.setdefault("ZYNTHIAN_DATA_DIR", str(SANDBOX / "data"))

# Safety net: if anything ever creates a JACK client, fail instead of spawning jackd
# (which on a dev machine would grab the real audio/MIDI hardware).
if os.environ.get("ZYNTHIAN_TEST_JACK") != "1":
    os.environ["JACK_NO_START_SERVER"] = "1"

# zyngui.zynthian_gui_config loads config files at import time (a known blocker,
# see tests/README.md). Provide the minimum it needs in the sandbox.
_wiring = Path(os.environ["ZYNTHIAN_CONFIG_DIR"]) / "wiring-profiles"
_wiring.mkdir(parents=True, exist_ok=True)
(_wiring / "v5").write_text('ZYNTHIAN_WIRING_ZYNAPTIK_CONFIG=""\n')
(Path(os.environ["ZYNTHIAN_CONFIG_DIR"]) / "zynthian_envars.sh").write_text(
    'export ZYNTHIAN_MIDI_FINE_TUNING="440"\n')
(Path(os.environ["ZYNTHIAN_CONFIG_DIR"]) / "jalv").mkdir(exist_ok=True)
(Path(os.environ["ZYNTHIAN_CONFIG_DIR"]) / "jalv" / "plugins.json").write_text("{}\n")
for _d in ("my-data", "ex-data", "data"):
    (SANDBOX / _d).mkdir(exist_ok=True)
(SANDBOX / "my-data" / "midi-profiles").mkdir(exist_ok=True)
_profile = SANDBOX / "my-data" / "midi-profiles" / "default.sh"
_profile.write_text('export ZYNTHIAN_MIDI_FINE_TUNING="440"\n')
os.environ.setdefault("ZYNTHIAN_SCRIPT_MIDI_PROFILE", str(_profile))

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# --- Optional third-party modules ---------------------------------------------
# Bindings that come from OS packages (python3-lilv, python3-dbus, ...) or need hardware.
# Stubbed ONLY when not installed, so the suite also runs on a bare CI image and the real
# modules are still used on a full Zynthian/dev machine.
STUB_IF_MISSING = (
    "lilv", "dbus", "mididings", "evdev", "usb", "board", "neopixel_spi", "pyudev",
    "rdflib", "wavio", "moderngl", "moderngl_window", "websocket_server", "cairosvg", "bs4",
    "soundfile", "ffmpeg", "tkinterweb",
)


def stub_missing_modules():
    import importlib
    from unittest import mock
    stubbed = []
    for name in STUB_IF_MISSING:
        try:
            importlib.import_module(name)
        except ImportError:
            sys.modules[name] = mock.MagicMock(name=f"stub:{name}")
            stubbed.append(name)
    return stubbed


STUBBED_MODULES = stub_missing_modules()

# --- Fake native layer --------------------------------------------------------
from tests.fakes.zyncore import FakeZyncore, build_module  # noqa: E402
from tests.fakes.native import registry as NATIVE  # noqa: E402

FAKE_ZYNCORE = FakeZyncore()


def install_fakes():
    """Replace ``zyncoder.zyncore`` and ctypes loading of ``libzyn*.so``.

    Opt out with ZYNTHIAN_TEST_REAL_ZYNCORE=1 (native / hardware runs).
    """
    if os.environ.get("ZYNTHIAN_TEST_REAL_ZYNCORE") == "1":
        return
    NATIVE.install()
    import zyncoder  # package only (has no import side effects)
    mod = build_module(FAKE_ZYNCORE)
    sys.modules["zyncoder.zyncore"] = mod
    zyncoder.zyncore = mod


install_fakes()
