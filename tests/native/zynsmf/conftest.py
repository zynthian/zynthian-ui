"""zynsmf: the real libzynsmf.so (Standard MIDI File parser, JACK player and recorder)."""

import ctypes

import pytest

from tests.native.support import lib_path, missing_lib_reason
from tests.native.zynsmf import midifile

vp, u8, u16, u32 = ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32
sz, boolean, dbl, cstr = ctypes.c_size_t, ctypes.c_bool, ctypes.c_double, ctypes.c_char_p

SIGNATURES = {
    "addSmf": (vp, []),
    "removeSmf": (None, [vp]),
    "getSmfCount": (sz, []),
    "load": (boolean, [vp, cstr]),
    "save": (boolean, [vp, cstr]),
    "unload": (None, [vp]),
    "getDuration": (dbl, [vp]),
    "setPosition": (None, [vp, u32]),
    "getTracks": (u32, [vp]),
    "getFormat": (u8, [vp]),
    "getEvents": (u32, [vp, sz]),
    "getTicksPerQuarterNote": (u16, [vp]),
    "getEvent": (boolean, [vp, boolean]),
    "addNote": (None, [vp, u32, u32, u32, u8, u8, u8]),
    "addTempo": (None, [vp, u32, dbl]),
    "setEndOfTrack": (None, [vp, u32, u32]),
    "getEventTrack": (sz, []),
    "getEventTime": (u32, []),
    "getEventType": (u8, []),
    "getEventChannel": (u8, []),
    "getEventStatus": (u8, []),
    "getEventValue1": (u8, []),
    "getEventValue2": (u8, []),
    "getTempo": (dbl, [vp, u32]),
    "muteTrack": (None, [vp, sz, boolean]),
    "isTrackMuted": (boolean, [vp, sz]),
    "setTranspose": (None, [ctypes.c_int8]),
    "getTranspose": (ctypes.c_int8, []),
    "attachPlayer": (boolean, [vp]),
    "removePlayer": (None, []),
    "setLoop": (None, [boolean]),
    "startPlayback": (None, []),
    "stopPlayback": (None, []),
    "getPlayState": (u8, []),
    "attachRecorder": (boolean, [vp]),
    "removeRecorder": (None, []),
    "startRecording": (None, []),
    "stopRecording": (None, []),
    "isRecording": (boolean, []),
}
NO_EVENT = 0xFFFFFFFF
EVENT_TYPE_MIDI, EVENT_TYPE_META = 1, 3          # zynsmf event types seen from getEventType()
ALL_TRACKS = ctypes.c_size_t(-1).value
STOPPED, STARTING, PLAYING = 0, 1, 2             # zynsmf play states


class Smf:
    """Handle on one SMF object plus convenient wrappers."""

    def __init__(self, lib):
        self.lib = lib
        self.h = lib.addSmf()

    def __getattr__(self, name):
        func = getattr(self.lib, name)
        return lambda *args: func(self.h, *args)

    def load_bytes(self, tmp_path, data, name="song.mid"):
        path = tmp_path / name
        path.write_bytes(data)
        return self.lib.load(self.h, str(path).encode())

    def events(self):
        """All events as dicts, in playback order (walks the library's event cursor)."""
        self.lib.setPosition(self.h, 0)
        out = []
        while self.lib.getEvent(self.h, False):
            lib = self.lib
            out.append(dict(time=lib.getEventTime(), type=lib.getEventType(), status=lib.getEventStatus(),
                            channel=lib.getEventChannel(), v1=lib.getEventValue1(), v2=lib.getEventValue2(),
                            track=lib.getEventTrack()))
            lib.getEvent(self.h, True)
        return out


@pytest.fixture(scope="session")
def zynsmf_lib(jack_server):
    reason = missing_lib_reason("zynsmf")
    if reason:
        pytest.skip(reason)
    lib = ctypes.CDLL(str(lib_path("zynsmf")))
    for name, (restype, argtypes) in SIGNATURES.items():
        func = getattr(lib, name)
        func.restype, func.argtypes = restype, argtypes
    return lib


@pytest.fixture
def smf(zynsmf_lib):
    handle = Smf(zynsmf_lib)
    yield handle
    zynsmf_lib.removePlayer()
    zynsmf_lib.removeRecorder()
    zynsmf_lib.removeSmf(handle.h)


@pytest.fixture
def song(smf, tmp_path):
    """An SMF loaded with midifile.SONG."""
    assert smf.load_bytes(tmp_path, midifile.SONG)
    return smf
