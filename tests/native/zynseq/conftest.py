"""zynseq: the real libzynseq.so on the session's private dummy jackd.

The library keeps global state (one JACK client, one sequence manager), so it is initialised once per session
(client name ``zyntest_seq``) and shared by all zynseq test modules. ``seq`` (function scope) calls
``reset()`` first: a known default state (17 phrases x 8 sequences, each with one track and one pattern).
"""

import ctypes

import pytest

from tests.native.support import lib_path, missing_lib_reason

CLIENT = "zyntest_seq"

u8, u16, u32 = ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32
i8, i32 = ctypes.c_int8, ctypes.c_int32
flt, dbl, boolean, cstr = ctypes.c_float, ctypes.c_double, ctypes.c_bool, ctypes.c_char_p
SEQ = [u8, u8, u8]  # (scene, phrase, sequence)

# name: (restype, argtypes). ctypes passes ints as C int and floats wrongly unless declared.
SIGNATURES = {
    # library
    "init": (None, [cstr]),
    "reset": (None, []),
    "isModified": (boolean, []),
    "getState": (cstr, []),
    "getPatternState": (cstr, [u32]),
    "setState": (boolean, [cstr]),
    "setPattern": (None, [u32, cstr]),
    "setTempo": (None, [dbl]),
    "getTempo": (dbl, []),
    "setExtClockPPQN": (None, [u8]),
    "setMetronomeMode": (None, [u8]),
    "transportStop": (None, [u8]),
    # pattern (operates on the selected pattern)
    "selectPattern": (None, [u32]),
    "getPatternIndex": (u32, []),
    "createPattern": (u32, []),
    "copyPattern": (None, [u32, u32]),
    "clearPattern": (None, [u32]),
    "clearNotes": (None, []),
    "isPatternEmpty": (boolean, [u32]),
    "isPatternModified": (boolean, []),
    "getSteps": (u32, []),
    "getStepsPerBeat": (u32, []),
    "setStepsPerBeat": (None, [u32]),
    "getBeatsInPattern": (u32, [u32]),
    "setBeatsInPattern": (None, [u32, u32]),
    "getClocksPerStep": (u32, [u32]),
    "getPatternLength": (u32, [u32]),
    "addNote": (boolean, [u32, u8, u8, flt, flt]),
    "removeNote": (None, [u32, u8]),
    "getNoteVelocity": (u8, [u32, u8]),
    "setNoteVelocity": (None, [u32, u8, u8]),
    "getNoteDuration": (flt, [u32, u8]),
    "getNoteOffset": (flt, [u32, u8]),
    "setNoteOffset": (None, [u32, u8, flt]),
    "getNoteStart": (i32, [u32, u8]),
    "transpose": (None, [i8]),
    "changeVelocityAll": (None, [ctypes.c_int]),
    "setInterpolateCC": (None, [u8, boolean]),
    "addControl": (boolean, [u32, u8, u8, u8, flt, flt]),
    "getControlValue": (u8, [u32, u8]),
    "getControlValueEnd": (u8, [u32, u8]),
    "getControlDuration": (flt, [u32, u8]),
    "removeControl": (None, [u32, u8]),
    "addProgramChange": (boolean, [u32, u8]),
    "getProgramChange": (u8, [u32]),
    "savePatternSnapshot": (None, []),
    "undoPattern": (boolean, []),
    "redoPattern": (boolean, []),
    # sequences: (scene, phrase, sequence, ...)
    "addTrackToSequence": (u32, SEQ + [u32]),
    "getTracksInSequence": (u32, SEQ),
    "addPattern": (boolean, SEQ + [u32, u32, u32, boolean]),
    "getPattern": (i32, SEQ + [u32, u32]),
    "removePattern": (None, SEQ + [u32, u32]),
    "setChannel": (None, SEQ + [u32, u8]),
    "getChannel": (u8, SEQ + [u32]),
    "setSequenceMode": (None, SEQ + [u8]),
    "getSequenceMode": (u8, SEQ),
    "setSequenceRepeat": (None, SEQ + [u8]),
    "getSequenceRepeat": (u8, SEQ),
    "setPlayState": (None, SEQ + [u8]),
    "getPlayState": (u8, SEQ),
    "togglePlayState": (None, SEQ),
    "getSequenceLength": (u32, SEQ),
    "clearSequence": (None, SEQ),
    "isEmpty": (boolean, SEQ),
    "updateSequenceInfo": (None, []),
    "setSequenceName": (None, SEQ + [cstr]),
    "getSequenceName": (cstr, SEQ),
    "setSequenceTempo": (None, SEQ + [flt]),
    "getSequenceTempo": (flt, SEQ),
    "stop": (None, []),
}

# play states and sequence modes (constants.h)
STOPPED, PLAYING, STARTING, STOPPING, FORCED_STOP, STOPPING_SYNC = 0, 1, 2, 3, 4, 5
MODE_END_END, MODE_END_SYNC, MODE_END_IMMEDIATE = 0, 1, 2
MODE_START_SYNC, MODE_START_IMMEDIATE = 0, 4
REPEAT_ENDLESS = 255   # setSequenceRepeat: 0 = disabled, 1 = play once, N = N times, 255 = loop forever


def load_libzynseq():
    lib = ctypes.CDLL(str(lib_path("zynseq")))
    for name, (restype, argtypes) in SIGNATURES.items():
        func = getattr(lib, name)
        func.restype = restype
        func.argtypes = argtypes
    return lib


@pytest.fixture(scope="session")
def zynseq(jack_server):
    reason = missing_lib_reason("zynseq")
    if reason:
        pytest.skip(reason)
    lib = load_libzynseq()
    lib.init(CLIENT.encode())
    return lib


@pytest.fixture
def seq(zynseq):
    """The library in its default state, nothing playing, internal tempo 120 BPM."""
    zynseq.stop()
    zynseq.transportStop(255)
    zynseq.setExtClockPPQN(24)
    zynseq.setMetronomeMode(0)
    zynseq.reset()
    zynseq.setTempo(120.0)
    return zynseq
