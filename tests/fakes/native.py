# -*- coding: utf-8 -*-
"""Hermetic replacement for every ``libzyn*.so`` loaded through ctypes.

The Python wrappers in ``zynlibs/*`` (and ``zyncoder``) call
``ctypes.cdll.LoadLibrary(".../build/libzynXXX.so")`` at import or construction
time and some of them immediately ``init()`` the library, which on a dev machine
starts a real JACK server and grabs MIDI hardware. Patching ``LoadLibrary`` lets
the real wrapper code run while the C layer is a recording fake.

Access the fake for a library with ``native_libs["libzynseq.so"]`` (see the
``native_libs`` fixture in conftest.py).
"""

import ctypes
import os

from tests.fakes.zyncore import FakeZyncore

# Return values that make the wrappers' init sequences succeed.
_DEFAULT_RETURNS = {
    "libzynaudioplayer.so": {"init": 1},
    "libzynmixer.so": {"setMeterConfig": 1},
    "libzynmixer_mixbus.so": {"setMeterConfig": 1},
    "libzynseq.so": {
        "getPPQN": 96,
        # Minimal valid sequencer state (what zynseq.refresh_state() parses)
        "getState": b'{"tempo": 120.0, "bpb": 4, "scenes": [{"phrases": [{"sequences": []}]}]}',
    },
}


class FakeNativeLib(FakeZyncore):
    """Recording fake of one shared library. Same API as FakeZyncore."""

    DEFAULT_RETURNS = {}  # per-library values come from _DEFAULT_RETURNS above

    def __init__(self, name):
        self.lib_name = name
        self._handle = 0  # zynsmf does dlclose(lib._handle); keep it an int
        super().__init__()

    def _apply_defaults(self):
        self.returns.update(_DEFAULT_RETURNS.get(self.lib_name, {}))


class NativeLibRegistry:
    def __init__(self):
        self.libs = {}
        self._real_load = None

    def __getitem__(self, name):
        return self.libs.setdefault(name, FakeNativeLib(name))

    def reset(self):
        for lib in self.libs.values():
            lib.reset_fake()

    def _load(self, path, *args, **kwargs):
        base = os.path.basename(str(path))
        if base.startswith("libzyn") and base.endswith(".so"):
            return self[base]
        return self._real_load(path, *args, **kwargs)

    def install(self):
        """Patch ctypes.cdll.LoadLibrary (idempotent)."""
        if self._real_load is None:
            self._real_load = ctypes.cdll.LoadLibrary
            ctypes.cdll.LoadLibrary = self._load

    def uninstall(self):
        if self._real_load is not None:
            ctypes.cdll.LoadLibrary = self._real_load
            self._real_load = None


registry = NativeLibRegistry()
