"""zynmixer: the real libzynmixer.so (channel strips) on the session's dummy jackd, in freewheel.

The library opens its JACK client from a constructor that runs when it is loaded (``init()`` has
``__attribute__((constructor))``) and calls ``exit(1)`` if there is no server, so it must only be loaded once the
private server is up. It is loaded once per session (client ``zynmixer_chan``); every test creates its own strips
and removes them afterwards.

Signals are constant (DC) levels written by a JACK source client, so a strip's output can be compared with
exact arithmetic. Level and balance changes are faded over one JACK period, so ``settle()`` runs a few periods
before measuring.
"""

import ctypes
import time

import numpy as np
import pytest

from tests.jacktest import FreewheelRunner, TestClient
from tests.native.support import lib_path, missing_lib_reason

u8, i8, flt = ctypes.c_uint8, ctypes.c_int8, ctypes.c_float
CLIENT = "zynmixer_chan"

SIGNATURES = {
    "addStrip": (i8, []),
    "removeStrip": (i8, [u8]),
    "getMaxChannels": (u8, []),
    "getLastChannel": (u8, []),
    "reset": (None, [u8]),
    "setGain": (None, [u8, flt]),
    "getGain": (flt, [u8]),
    "setLevel": (None, [u8, flt]),
    "getLevel": (flt, [u8]),
    "levelToDb": (flt, [flt]),
    "dbToLevel": (flt, [flt]),
    "setBalance": (None, [u8, flt]),
    "getBalance": (flt, [u8]),
    "setMute": (None, [u8, u8]),
    "getMute": (u8, [u8]),
    "toggleMute": (None, [u8]),
    "setSolo": (None, [u8, u8]),
    "getSolo": (u8, [u8]),
    "toggleSolo": (None, [u8]),
    "clearSolo": (None, []),
    "getGlobalSolo": (u8, []),
    "setPfl": (None, [u8, u8]),
    "getPfl": (u8, [u8]),
    "clearPfl": (None, []),
    "togglePFL": (None, [u8]),
    "toggleMono": (None, [u8]),
    "toggleMS": (None, [u8]),
    "togglePhase": (None, [u8]),
    "getGlobalPfl": (u8, []),
    "setMono": (None, [u8, u8]),
    "getMono": (u8, [u8]),
    "setMS": (None, [u8, u8]),
    "getMS": (u8, [u8]),
    "setPhase": (None, [u8, u8]),
    "getPhase": (u8, [u8]),
    "setGlobalXFader": (None, [flt]),
    "getGlobalXFader": (flt, []),
    "setABMixGroup": (None, [u8, u8]),
    "getABMixGroup": (u8, [u8]),
    "addSend": (ctypes.c_int, []),
    "removeSend": (u8, [u8]),
    "getSendCount": (u8, []),
    "setSend": (None, [u8, u8, flt]),
    "getSend": (flt, [u8, u8]),
    "setSendMode": (None, [u8, u8, u8]),
    "getSendMode": (u8, [u8, u8]),
    "getDpm": (flt, [u8, u8]),
    "getDpmHold": (flt, [u8, u8]),
    "enableDpm": (None, [u8]),
    "setMeterConfig": (u8, [flt, flt, flt, flt]),
}
FADER_UNITY = 0.75


class AudioSource(TestClient):
    """Outputs a constant value on each of its ports (set ``levels[name]``)."""

    def __init__(self, server, names, name="zyntest_mix_src"):
        super().__init__(server, name)
        self.ports = {n: self.client.outports.register(n) for n in names}
        self.levels = {n: 0.0 for n in names}

    def process(self, frame, nframes):
        for n, port in self.ports.items():
            np.frombuffer(port.get_buffer(), dtype=np.float32)[:] = self.levels[n]


class AudioProbe(TestClient):
    """Keeps the last period of each of its input ports."""

    def __init__(self, server, names, name="zyntest_mix_probe"):
        super().__init__(server, name)
        self.ports = {n: self.client.inports.register(n) for n in names}
        self.last = {n: np.zeros(1) for n in names}
        self.history = None          # set to [] to keep every period of tap "a"

    def process(self, frame, nframes):
        for n, port in self.ports.items():
            self.last[n] = np.frombuffer(port.get_buffer(), dtype=np.float32).copy()
        if self.history is not None:
            self.history.append(self.last["a"])

    def level(self, name):
        """Value of a constant signal over the last period (asserts it really is constant)."""
        buf = self.last[name]
        assert np.ptp(buf) < 1e-5, f"{name} is not settled: {buf.min()}..{buf.max()}"
        return float(buf[0])


class Rig:
    """A source (``a``, ``b``) and probe (``a``, ``b`` and extra taps) around the channel mixer."""

    TAPS = ("a", "b", "solo_a", "solo_b", "pfl_a", "pfl_b", "send_a", "send_b", "a2", "b2")

    def __init__(self, server, lib):
        self.server, self.lib = server, lib
        self.src = AudioSource(server, ("a", "b", "a2", "b2"))
        self.probe = AudioProbe(server, self.TAPS)
        self.runner = FreewheelRunner(server, "zyntest_mix_runner")
        for c in (self.src, self.probe, self.runner):
            c.activate()
        self.probe.client.connect(f"{CLIENT}:solo_a", self.probe.ports["solo_a"])
        self.probe.client.connect(f"{CLIENT}:solo_b", self.probe.ports["solo_b"])
        self.probe.client.connect(f"{CLIENT}:pfl_out_a", self.probe.ports["pfl_a"])
        self.probe.client.connect(f"{CLIENT}:pfl_out_b", self.probe.ports["pfl_b"])
        self.strips = []

    def strip(self, a=0.5, b=0.25, inputs=("a", "b"), outputs=("a", "b")):
        """Add a strip fed with constant ``a``/``b`` and connected to the probe; reset to unity."""
        chan = self.lib.addStrip()
        assert chan >= 0
        self.strips.append(chan)
        self.src.levels[inputs[0]], self.src.levels[inputs[1]] = a, b
        self.src.client.connect(self.src.ports[inputs[0]], f"{CLIENT}:input_{chan:02d}a")
        self.src.client.connect(self.src.ports[inputs[1]], f"{CLIENT}:input_{chan:02d}b")
        self.probe.client.connect(f"{CLIENT}:output_{chan:02d}a", self.probe.ports[outputs[0]])
        self.probe.client.connect(f"{CLIENT}:output_{chan:02d}b", self.probe.ports[outputs[1]])
        self.wait_routed(outputs[0])
        return chan

    def wait_routed(self, tap, timeout=3.0):
        """The mixer learns about connections through an asynchronous callback; wait until audio flows."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            time.sleep(0.02)
            if np.any(self.probe.last[tap] != 0):
                return
        raise TimeoutError(f"no audio on {tap}: mixer never saw the connections")

    def settle(self, periods=4):
        self.runner.run(periods * 256)
        return self

    def out(self):
        self.settle()
        return self.probe.level("a"), self.probe.level("b")

    def tap(self, name):
        self.settle()
        return self.probe.level(name)

    def cleanup(self):
        for chan in self.strips:
            self.lib.removeStrip(chan)
        self.strips = []
        self.lib.clearSolo()
        self.lib.clearPfl()
        self.lib.setGlobalXFader(0.0)
        for name in self.src.levels:
            self.src.levels[name] = 0.0

    def close(self):
        for c in (self.runner, self.probe, self.src):
            c.close()


def load(name):
    lib = ctypes.CDLL(str(lib_path(name)))
    for fname, (restype, argtypes) in SIGNATURES.items():
        func = getattr(lib, fname, None)
        if func is not None:
            func.restype, func.argtypes = restype, argtypes
    return lib


@pytest.fixture(scope="session")
def zynmixer(jack_server):
    reason = missing_lib_reason("zynmixer")
    if reason:
        pytest.skip(reason)
    lib = load("zynmixer")      # constructor connects to the session server (JACK_DEFAULT_SERVER)
    yield lib
    # Work around a known mixer.c bug so the test process can exit (see test_exit_after_solo_is_clean):
    # once a strip is soloed, onJackProcess points g_soloBufferA/B at JACK port buffers, and the end() exit
    # handler then free()s them -> crash at process exit. Stop soloing, then make those frees harmless.
    lib.clearSolo()
    time.sleep(0.05)
    for name in ("g_soloBufferA", "g_soloBufferB"):
        ctypes.c_void_p.in_dll(lib, name).value = None


@pytest.fixture(scope="module")
def rig_module(jack_server, zynmixer):
    rig = Rig(jack_server, zynmixer)
    yield rig
    rig.close()


@pytest.fixture
def mix(rig_module):
    yield rig_module
    rig_module.cleanup()
