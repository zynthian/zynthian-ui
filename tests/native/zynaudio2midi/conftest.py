"""zynaudio2midi: the real libzynaudio2midi.so (audio to MIDI converter).

Detection is tested offline with ``analyse()`` (the DSP core without JACK: deterministic, no server needed) on
synthetic signals: plucked strings (decaying harmonics), chords, noise. The JACK glue (start/stop, ports, MIDI
output, note off on stop) is tested on the session's dummy jackd.
"""

import ctypes

import numpy as np
import pytest

from tests.native.support import lib_path, missing_lib_reason

CLIENT = "audio2midi"
RATE = 48000
NOTE_ON, NOTE_OFF, PITCH_BEND = 0x90, 0x80, 0xE0


class Event(ctypes.Structure):
    _fields_ = [("frame", ctypes.c_uint32), ("data", ctypes.c_uint8 * 3)]


SIGNATURES = {
    "start": (ctypes.c_uint8, []),
    "stop": (None, []),
    "isRunning": (ctypes.c_uint8, []),
    "setOnsetThreshold": (None, [ctypes.c_float]),
    "getOnsetThreshold": (ctypes.c_float, []),
    "setReleaseThreshold": (None, [ctypes.c_float]),
    "getReleaseThreshold": (ctypes.c_float, []),
    "setPolyphonic": (None, [ctypes.c_uint8]),
    "getPolyphonic": (ctypes.c_uint8, []),
    "setNoiseFilter": (None, [ctypes.c_float]),
    "getNoiseFilter": (ctypes.c_float, []),
    "setPitchBend": (None, [ctypes.c_uint8]),
    "getPitchBend": (ctypes.c_uint8, []),
    "setBendRange": (None, [ctypes.c_float]),
    "getBendRange": (ctypes.c_float, []),
    "analyse": (ctypes.c_uint32, [ctypes.POINTER(ctypes.c_float), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                                  ctypes.POINTER(Event), ctypes.c_uint32]),
}


@pytest.fixture(scope="session")
def a2m_lib():
    """The compiled library, loaded once (parameters are process-global)."""
    reason = missing_lib_reason("zynaudio2midi")
    if reason:
        pytest.skip(reason)
    lib = ctypes.CDLL(str(lib_path("zynaudio2midi")))
    for name, (restype, argtypes) in SIGNATURES.items():
        fn = getattr(lib, name)
        fn.restype = restype
        fn.argtypes = argtypes
    return lib


@pytest.fixture
def a2m(a2m_lib):
    """The library with default parameters (restored after each test)."""
    def defaults():
        a2m_lib.setOnsetThreshold(-40)
        a2m_lib.setReleaseThreshold(-50)
        a2m_lib.setPolyphonic(0)
        a2m_lib.setNoiseFilter(50)
        a2m_lib.setPitchBend(0)
        a2m_lib.setBendRange(2)
    defaults()
    yield a2m_lib
    a2m_lib.stop()
    defaults()


def analyse(lib, signal, rate=RATE, block=256):
    """Run the offline analysis: list of (seconds, status, note, velocity)."""
    signal = np.ascontiguousarray(signal, dtype=np.float32)
    events = (Event * 4096)()
    n = lib.analyse(signal.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(signal), rate, block, events, 4096)
    return [(events[i].frame / rate, events[i].data[0], events[i].data[1], events[i].data[2]) for i in range(n)]


def note_ons(events):
    return [(t, note) for t, status, note, vel in events if status == NOTE_ON]


def pluck(note, secs, amp=0.3, decay=1.5, harmonics=8, rate=RATE, seed=None):
    """Plucked string: harmonics with 1/h amplitude, 5 ms attack, exponential decay. ``amp``: peak amplitude."""
    rng = np.random.default_rng(note if seed is None else seed)
    t = np.arange(int(secs * rate)) / rate
    f0 = 440.0 * 2 ** ((note - 69) / 12)
    x = np.zeros_like(t)
    for h in range(1, harmonics + 1):
        if f0 * h < rate / 2:
            x += np.sin(2 * np.pi * f0 * h * t + rng.uniform(0, 2 * np.pi)) / h
    env = np.exp(-t * decay) * np.minimum(1.0, t / 0.005)
    return (amp * x * env / np.max(np.abs(x[: rate // 20]))).astype(np.float32)


def silence(secs, rate=RATE):
    return np.zeros(int(secs * rate), dtype=np.float32)


def noise(secs, db, rate=RATE, seed=1):
    """White noise of the given RMS level (dBFS)."""
    return (np.random.default_rng(seed).normal(0, 10 ** (db / 20), int(secs * rate))).astype(np.float32)
