"""zynaudioplayer: the real libzynaudioplayer.so on the session's dummy jackd, in REAL time.

Unlike the MIDI libraries these tests do not use freewheel: the player streams the file from a background thread
that cannot keep up with a freewheeling JACK server (the playback position lags JACK time), so results would
not be reproducible. The dummy driver runs at real speed, which costs about one second per playing test.
Test files carry constant (DC) or linear-ramp signals, so what is heard identifies the file position without
depending on exact timing.
"""

import ctypes
import time
import wave

import numpy as np
import pytest

from tests.jacktest import TestClient
from tests.native.support import lib_path, missing_lib_reason

u8, flt, i32, i8 = ctypes.c_uint8, ctypes.c_float, ctypes.c_int, ctypes.c_int8
cstr, vp = ctypes.c_char_p, ctypes.c_void_p
CALLBACK = ctypes.CFUNCTYPE(None, u8, u8, u8, flt, flt)     # id, play_state, loop, position, varispeed

SIGNATURES = {
    "init": (u8, [vp]),
    "add_player": (u8, []),
    "remove_player": (None, [u8]),
    "get_player_count": (u8, []),
    "get_jack_client_name": (cstr, []),
    "load": (u8, [u8, cstr]),
    "unload": (None, [u8]),
    "save": (u8, [u8, cstr]),
    "get_filename": (cstr, [u8]),
    "get_duration": (flt, [u8]),
    "get_codec": (cstr, [u8]),
    "get_channels": (i32, [u8]),
    "get_samplerate": (i32, [u8]),
    "get_frames": (i32, [u8]),
    "is_codec_supported": (i32, [cstr]),
    "get_supported_codecs": (cstr, []),
    "get_file_duration": (flt, [cstr]),
    "get_file_channels": (i32, [cstr]),
    "start_playback": (None, [u8]),
    "stop_playback": (None, [u8]),
    "get_playback_state": (u8, [u8]),
    "set_position": (None, [u8, flt]),
    "get_position": (flt, [u8]),
    "enable_loop": (None, [u8, u8]),
    "is_loop": (u8, [u8]),
    "set_crop_start_time": (None, [u8, flt]),
    "get_crop_start_time": (flt, [u8]),
    "set_crop_end_time": (None, [u8, flt]),
    "get_crop_end_time": (flt, [u8]),
    "set_gain": (None, [u8, flt]),
    "get_gain": (flt, [u8]),
    "set_track_a": (None, [u8, i32]),
    "get_track_a": (i32, [u8]),
    "set_track_b": (None, [u8, i32]),
    "get_track_b": (i32, [u8]),
    "set_speed": (None, [u8, flt]),
    "get_speed": (flt, [u8]),
    "set_pitch_semitone": (None, [u8, i8]),
    "get_pitch_semitone": (i8, [u8]),
    "set_varispeed": (None, [u8, flt]),
    "get_varispeed": (flt, [u8]),
}
STOPPED, PLAYING, STARTING, STOPPING = 0, 1, 2, 3          # player.h enum playState
RATE = 48000


def write_wav(path, left, right=None, rate=RATE):
    """Write a 16-bit WAV from float arrays in -1..1 (stereo if ``right`` is given)."""
    channels = [left] if right is None else [left, right]
    pcm = (np.stack(channels, 1).clip(-1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(len(channels))
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return str(path)


def wait_for(condition, timeout=5.0, step=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(step)
    return condition()


class AudioCapture(TestClient):
    """JACK client recording what a player outputs on its left/right ports."""

    def __init__(self, server, name="zyntest_ap_cap"):
        super().__init__(server, name)
        self.a = self.client.inports.register("a")
        self.b = self.client.inports.register("b")
        self.blocks = []
        self.recording = False

    def process(self, frame, nframes):
        if self.recording:
            self.blocks.append((np.frombuffer(self.a.get_buffer(), dtype=np.float32).copy(),
                                np.frombuffer(self.b.get_buffer(), dtype=np.float32).copy()))

    def capture(self, seconds):
        """(left, right) samples heard during the next ``seconds`` (real time)."""
        self.blocks = []
        self.recording = True
        time.sleep(seconds)
        self.recording = False
        blocks = list(self.blocks)
        if not blocks:
            return np.zeros(0), np.zeros(0)
        return np.concatenate([b[0] for b in blocks]), np.concatenate([b[1] for b in blocks])


class Player:
    """One player of the library, with ``lib`` calls bound to its id."""

    def __init__(self, lib, capture, jack_client):
        self.lib = lib
        self.id = lib.add_player()
        name = lib.get_jack_client_name().decode()
        self.ports = (f"{name}:out_{self.id:02d}a", f"{name}:out_{self.id:02d}b")
        capture.client.connect(self.ports[0], capture.a)
        capture.client.connect(self.ports[1], capture.b)
        self.capture = capture

    def __getattr__(self, name):
        func = getattr(self.lib, name)
        return lambda *args: func(self.id, *args)

    @property
    def state(self):
        return self.lib.get_playback_state(self.id)

    def play(self):
        self.lib.start_playback(self.id)
        assert wait_for(lambda: self.state == PLAYING), "player did not reach PLAYING"

    def heard(self, seconds=0.25):
        """Mean (left, right) level over the next ``seconds``."""
        left, right = self.capture.capture(seconds)
        assert len(left), "nothing captured"
        return float(left.mean()), float(right.mean())


@pytest.fixture(scope="session")
def libplayer(jack_server):
    reason = missing_lib_reason("zynaudioplayer")
    if reason:
        pytest.skip(reason)
    lib = ctypes.CDLL(str(lib_path("zynaudioplayer")))
    for name, (restype, argtypes) in SIGNATURES.items():
        func = getattr(lib, name)
        func.restype, func.argtypes = restype, argtypes
    lib.notifications = []
    lib._callback = CALLBACK(lambda i, st, lp, pos, vs: lib.notifications.append((i, st, lp, pos, vs)))
    assert lib.init(lib._callback), "libzynaudioplayer failed to start its JACK client"
    return lib


@pytest.fixture(scope="session")
def capture(jack_server, libplayer):
    cap = AudioCapture(jack_server)
    cap.activate()
    yield cap
    cap.close()


@pytest.fixture(scope="session")
def wavs(tmp_path_factory):
    """dc: 1.5 s, left 0.5 / right 0.25.  ramp: 2.0 s, left rises 0 -> 0.9 linearly, right 0.25."""
    d = tmp_path_factory.mktemp("wavs")
    n = int(1.5 * RATE)
    dc = write_wav(d / "dc.wav", np.full(n, 0.5), np.full(n, 0.25))
    n = 2 * RATE
    ramp = write_wav(d / "ramp.wav", np.arange(n) / n * 0.9, np.full(n, 0.25))
    mono = write_wav(d / "mono.wav", np.full(RATE, 0.5))
    return dict(dc=dc, ramp=ramp, mono=mono, dir=d)


@pytest.fixture
def player(libplayer, capture, jack_server):
    p = Player(libplayer, capture, jack_server)
    yield p
    libplayer.stop_playback(p.id)
    libplayer.enable_loop(p.id, 0)
    wait_for(lambda: p.state == STOPPED, 3.0)
    libplayer.remove_player(p.id)
