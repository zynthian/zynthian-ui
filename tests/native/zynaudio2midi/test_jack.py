"""The JACK client: lifecycle, ports and MIDI output, on the session's dummy jackd."""

import threading

import numpy as np
import pytest

from tests.jacktest import FreewheelRunner, Recorder, TestClient
from tests.native.zynaudio2midi.conftest import CLIENT, NOTE_OFF, NOTE_ON, pluck, silence


class Player(TestClient):
    """Plays a buffer once (then silence) or loops it."""

    def __init__(self, server, name="zyntest_a2m_player"):
        super().__init__(server, name)
        self.port = self.client.outports.register("out")
        self.lock = threading.Lock()
        self.buffer = np.zeros(0, dtype=np.float32)
        self.pos = 0
        self.loop = False

    def play(self, buffer, loop=False):
        with self.lock:
            self.buffer, self.pos, self.loop = np.asarray(buffer, dtype=np.float32), 0, loop

    def process(self, frame, nframes):
        out = np.frombuffer(self.port.get_buffer(), dtype=np.float32)
        out[:] = 0.0
        with self.lock:
            n = 0
            while n < nframes and len(self.buffer):
                if self.pos >= len(self.buffer):
                    if not self.loop:
                        break
                    self.pos = 0
                k = min(nframes - n, len(self.buffer) - self.pos)
                out[n:n + k] = self.buffer[self.pos:self.pos + k]
                n += k
                self.pos += k


@pytest.fixture
def rig(a2m, jack_server):
    assert a2m.start() == 1
    player = Player(jack_server)
    rec = Recorder(jack_server, "zyntest_a2m_rec", midi_ports=("in",))
    runner = FreewheelRunner(jack_server, "zyntest_a2m_runner")
    for c in (player, rec, runner):
        c.activate()
    player.client.connect(player.port, f"{CLIENT}:input")
    rec.client.connect(f"{CLIENT}:midi_out", rec.midi_ports["in"])
    yield a2m, player, rec, runner
    a2m.stop()
    for c in (player, rec, runner):
        c.close()


def received(rec):
    with rec.lock:
        return [(data[0], data[1]) for frame, data in rec.midi["in"]]


def test_start_registers_ports_and_stop_removes_them(a2m, jack_server):
    import jack
    probe = jack.Client("zyntest_a2m_probe", servername=jack_server.name, no_start_server=True)
    try:
        assert a2m.isRunning() == 0
        assert a2m.start() == 1
        assert a2m.isRunning() == 1
        assert a2m.start() == 1  # already running
        audio = [p.name for p in probe.get_ports(f"{CLIENT}:", is_audio=True, is_input=True)]
        midi = [p.name for p in probe.get_ports(f"{CLIENT}:", is_midi=True, is_output=True)]
        assert audio == [f"{CLIENT}:input"]
        assert midi == [f"{CLIENT}:midi_out"]
        a2m.stop()
        assert a2m.isRunning() == 0
        assert probe.get_ports(f"{CLIENT}:") == []
        a2m.stop()  # already stopped
    finally:
        probe.close()


def test_converts_audio_to_midi(rig):
    a2m, player, rec, runner = rig
    player.play(np.concatenate([pluck(57, 0.5, decay=0.5), silence(0.5)]))
    runner.run_seconds(1.2)
    assert received(rec) == [(NOTE_ON, 57), (NOTE_OFF, 57)]


def test_polyphonic(rig):
    a2m, player, rec, runner = rig
    a2m.setPolyphonic(1)
    player.play(np.concatenate([sum(pluck(n, 1.0, amp=0.2) for n in (48, 52, 55)), silence(0.4)]))
    runner.run_seconds(1.6)
    events = received(rec)
    assert sorted(n for s, n in events if s == NOTE_ON) == [48, 52, 55]
    assert sorted(n for s, n in events if s == NOTE_OFF) == [48, 52, 55]


def test_stop_releases_held_note(rig):
    a2m, player, rec, runner = rig
    t = np.arange(48000) / 48000
    player.play((0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), loop=True)
    runner.run_seconds(0.5)
    assert received(rec) == [(NOTE_ON, 57)]
    a2m.stop()  # the server runs in real time now: the process thread releases the note before the client closes
    runner.run_seconds(0.1)
    assert received(rec) == [(NOTE_ON, 57), (NOTE_OFF, 57)]


def test_mode_change_releases_held_note(rig):
    a2m, player, rec, runner = rig
    t = np.arange(48000) / 48000
    player.play((0.2 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), loop=True)
    runner.run_seconds(0.5)
    a2m.setPolyphonic(1)
    runner.run_seconds(0.05)
    assert received(rec)[:2] == [(NOTE_ON, 57), (NOTE_OFF, 57)]
