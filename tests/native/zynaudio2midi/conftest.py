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


OUTPUTS = 2


class Event(ctypes.Structure):
    _fields_ = [("frame", ctypes.c_uint32), ("output", ctypes.c_uint8), ("data", ctypes.c_uint8 * 3)]


SIGNATURES = {
    "start": (ctypes.c_uint8, []),
    "stop": (None, []),
    "isRunning": (ctypes.c_uint8, []),
    "setOnsetThreshold": (None, [ctypes.c_float]),
    "getOnsetThreshold": (ctypes.c_float, []),
    "setReleaseThreshold": (None, [ctypes.c_float]),
    "getReleaseThreshold": (ctypes.c_float, []),
    "setNoiseFilter": (None, [ctypes.c_float]),
    "getNoiseFilter": (ctypes.c_float, []),
    "setOutputActive": (None, [ctypes.c_uint8, ctypes.c_uint8]),
    "getOutputActive": (ctypes.c_uint8, [ctypes.c_uint8]),
    "setPolyphonic": (None, [ctypes.c_uint8, ctypes.c_uint8]),
    "getPolyphonic": (ctypes.c_uint8, [ctypes.c_uint8]),
    "setPitchBend": (None, [ctypes.c_uint8, ctypes.c_uint8]),
    "getPitchBend": (ctypes.c_uint8, [ctypes.c_uint8]),
    "setBendRange": (None, [ctypes.c_uint8, ctypes.c_float]),
    "getBendRange": (ctypes.c_float, [ctypes.c_uint8]),
    "analyse": (ctypes.c_uint32, [ctypes.POINTER(ctypes.c_float), ctypes.POINTER(ctypes.c_float), ctypes.c_uint32,
                                  ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint8, ctypes.POINTER(Event), ctypes.c_uint32]),
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
    """The library with default parameters (restored after each test). No output is active."""
    def defaults():
        a2m_lib.setOnsetThreshold(-40)
        a2m_lib.setReleaseThreshold(-50)
        a2m_lib.setNoiseFilter(50)
        for output in range(OUTPUTS):
            a2m_lib.setOutputActive(output, 0)
            a2m_lib.setPolyphonic(output, 0)
            a2m_lib.setPitchBend(output, 0)
            a2m_lib.setBendRange(output, 2)
    defaults()
    yield a2m_lib
    a2m_lib.stop()
    defaults()


def analyse_outputs(lib, signal, outputs=0b11, rate=RATE, block=256, signal2=None):
    """Run the offline analysis with the given outputs (bitmask) active: {output: [(seconds, status, note, velocity)]}.

    ``signal``: input 1 (None: not connected), ``signal2``: input 2 (None: not connected), padded to the same length.
    """
    signals = [None if x is None else np.asarray(x, dtype=np.float32) for x in (signal, signal2)]
    frames = max(len(x) for x in signals if x is not None)
    signals = [None if x is None else np.ascontiguousarray(np.pad(x, (0, frames - len(x)))) for x in signals]
    ptrs = [None if x is None else x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)) for x in signals]
    events = (Event * 8192)()
    n = lib.analyse(ptrs[0], ptrs[1], frames, rate, block, outputs, events, 8192)
    result = {o: [] for o in range(OUTPUTS)}
    for i in range(n):
        e = events[i]
        result[e.output].append((e.frame / rate, e.data[0], e.data[1], e.data[2]))
    return result


def analyse(lib, signal, rate=RATE, block=256):
    """Run the offline analysis on output 0 alone: list of (seconds, status, note, velocity)."""
    return analyse_outputs(lib, signal, 0b01, rate, block)[0]


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
