"""Fixtures for tests that run the REAL zyncore library (TOUCH_ONLY build) on a private dummy jackd.

The library is opened with ``ctypes.CDLL`` directly, bypassing the ``ctypes.cdll.LoadLibrary`` patch that
tests/bootstrap.py installs for every other test. Nothing here imports ``zyngine`` for the library.
"""

import ctypes
import os
import sys
import time
import uuid

import pytest

from tests.bootstrap import REPO_ROOT
from tests.native.support import native_skip_reason, zyncore_lib_path

# Reuse the JACK helpers written for zynseq (private jackd -d dummy, freewheel, MIDI source/recorder)
sys.path.insert(0, str(REPO_ROOT / "zynlibs" / "zynseq" / "tests"))

pytestmark = [pytest.mark.native, pytest.mark.jack]

NUM_CHAINS = 17
FRAMES_PER_SEND = 2048  # 8 process cycles of 256 frames: plenty for an event to travel through


class RouterRig:
    """The real ZynMidiRouter, plus a MIDI source/recorder to drive and observe it through JACK."""

    def __init__(self, lib, server):
        from jacktest import FreewheelRunner, MidiSource, Recorder  # noqa: E402 (path set above)
        self.lib = lib
        self.server = server
        self.src = MidiSource(server)
        self.runner = FreewheelRunner(server)
        self._Recorder = Recorder
        self.rec = None
        self._clients = [self.src, self.runner]
        self._src_connected = set()

    # -- wiring ---------------------------------------------------------------------------------
    def listen(self, *outputs):
        """Record the given router output ports, e.g. ``"ch0"``, ``"dev3"``, ``"mod"``.

        The router learns about JACK connections asynchronously (port-connect callback) and skips
        outputs it believes are unconnected. So a canary output (``mod``) is connected last and a
        canary event is sent until it arrives: by then the router has seen every connection."""
        assert self.rec is None, "call listen() once, before the first send()"
        self._requested = tuple(outputs)
        ports = tuple(dict.fromkeys(outputs + ("mod",)))  # "mod" last-but-deduplicated: the canary
        ports = tuple(p for p in ports if p != "mod") + ("mod",)
        self.rec = self._Recorder(self.server, midi_ports=ports)
        self._clients.append(self.rec)
        for client in self._clients:
            client.activate()
        for name in ports:
            self.rec.client.connect(f"ZynMidiRouter:{name}_out", self.rec.midi_ports[name])
        self._connect_input("dev0_in")
        # Handshake in real time (not freewheel): the notifications are not delivered reliably while
        # the server switches in and out of freewheel mode.
        for _ in range(100):
            self.rec.clear()
            self.src.schedule([(self.runner.frame_time + 2048, b"\xbf\x77\x00")])  # CC#119 on ch16
            time.sleep(0.1)
            if self.rec.midi["mod"]:
                break
        else:
            raise TimeoutError("router never saw the JACK connections")
        self.src.clear()
        self.ui_events()  # discard the canary captured for the UI
        return self

    def _connect_input(self, port_name):
        if port_name not in self._src_connected:
            self.src.client.connect(self.src.port, f"ZynMidiRouter:{port_name}")
            self._src_connected.add(port_name)

    # -- stimulus / observation ------------------------------------------------------------------
    def send(self, *events, via="dev0_in"):
        """Send MIDI events (bytes/lists) into router input ``via``; return what each listened output got.

        Result: ``{"ch0": [b"\\x90<d", ...], ...}`` - only outputs that received something."""
        self._connect_input(via)
        self.rec.clear()
        start = self.runner.frame_time + 512
        self.src.schedule([(start + i, bytes(ev)) for i, ev in enumerate(events)])
        self.runner.run(FRAMES_PER_SEND)
        assert self.src.late == 0, "test source scheduled events in the past"
        return {name: [data for _, data in evs] for name, evs in self.rec.midi.items()
                if evs and name in self._requested}

    def ui_events(self):
        """Drain the queue of MIDI events captured for the UI: ``[(device, b0, b1, b2), ...]``."""
        out = []
        while self.lib.get_zynmidi_num_pending() > 0:
            ev = self.lib.read_zynmidi()
            out.append((ev >> 24, (ev >> 16) & 0xFF, (ev >> 8) & 0xFF, ev & 0xFF))
        return out

    def close(self):
        for client in self._clients:
            if getattr(client, "client", None) is not None and client.client.name:
                try:
                    client.close()
                except Exception:
                    pass


@pytest.fixture(scope="session")
def jack_server():
    reason = native_skip_reason()
    if reason:
        pytest.skip(reason)
    from jacktest import JackTestServer
    saved = os.environ.get("JACK_DEFAULT_SERVER")
    server = JackTestServer(f"zyntest_{os.getpid()}_{uuid.uuid4().hex[:6]}")
    server.start()
    try:
        yield server
    finally:
        server.stop()
        if saved is None:
            os.environ.pop("JACK_DEFAULT_SERVER", None)
        else:
            os.environ["JACK_DEFAULT_SERVER"] = saved


@pytest.fixture(scope="session")
def real_zyncore(jack_server):
    """The compiled library, loaded once (its router state is process-global)."""
    lib = ctypes.CDLL(str(zyncore_lib_path()))
    lib.read_zynmidi.restype = ctypes.c_uint32
    return lib


@pytest.fixture
def router(real_zyncore, jack_server):
    """A freshly initialised router (init_zyncore) with a rig to drive it. Torn down after each test."""
    assert real_zyncore.init_zyncore() == 0
    rig = RouterRig(real_zyncore, jack_server)
    try:
        yield rig
    finally:
        rig.close()
        assert real_zyncore.end_zyncore() == 1
