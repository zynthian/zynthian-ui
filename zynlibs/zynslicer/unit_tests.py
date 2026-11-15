#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Unit tests for the zynslicer library.

These tests drive libzynslicer through ctypes and therefore need a running
JACK server. They are intended for a Zynthian/Linux host:

    cd zynlibs/zynslicer
    ./run_tests.sh

The script uses the existing JACK server, or starts a dummy server when none
is running. Do not run it while zynthian-ui owns the "zynslicer" JACK client.
"""

import ctypes
import math
import os
import struct
import tempfile
import time
import unittest
import wave

try:
    import jack
    HAVE_JACK = True
except ImportError:
    jack = None
    HAVE_JACK = False


HERE = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(HERE, "build", "libzynslicer.so")

ERROR_SUCCESS = 0
ERROR_RANGE = 2
ERROR_CREATE = 3

SLICE_FLAG_GATE = 0x01
SLICE_FLAG_LOOP = 0x02
MAX_PLAYERS = 16


def make_test_wav(path, samplerate=48000, seconds=2.0, channels=2):
    """Create a deterministic stereo WAV with four strong clicks."""
    frames = int(samplerate * seconds)
    with wave.open(path, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(samplerate)
        payload = bytearray()
        for i in range(frames):
            t = i / samplerate
            # Click for 1 ms every 500 ms, quiet tone in between.
            if (i % (samplerate // 2)) < (samplerate // 1000):
                value = 0.9 if (i // 48) % 2 == 0 else -0.9
            else:
                value = 0.1 * math.sin(2 * math.pi * 220 * t)
            sample = int(max(-1.0, min(1.0, value)) * 32767)
            payload += struct.pack("<h", sample)
            if channels > 1:
                payload += struct.pack("<h", -sample)
        out.writeframes(payload)


def configure_library(lib):
    byte = ctypes.c_uint8
    u32 = ctypes.c_uint32

    lib.init.restype = ctypes.c_int
    lib.end.restype = None
    lib.getJackname.argtypes = []
    lib.getJackname.restype = ctypes.c_char_p

    lib.addPlayer.argtypes = [byte]
    lib.addPlayer.restype = byte
    lib.removePlayer.argtypes = [byte]
    lib.removePlayer.restype = byte

    lib.setPolyphony.argtypes = [byte, byte]
    lib.setPolyphony.restype = byte

    lib.getFileFrames.argtypes = [ctypes.c_char_p]
    lib.getFileFrames.restype = u32
    lib.loadSample.argtypes = [byte, ctypes.c_char_p, u32, u32, byte]
    lib.loadSample.restype = byte
    lib.unloadSample.argtypes = [byte]
    lib.unloadSample.restype = byte
    lib.getSampleFrames.argtypes = [byte]
    lib.getSampleFrames.restype = u32

    lib.setSlice.argtypes = [byte, byte, u32, u32, ctypes.c_float, byte]
    lib.setSlice.restype = byte
    lib.setSliceTune.argtypes = [byte, byte, ctypes.c_float]
    lib.setSliceTune.restype = byte
    lib.clearSlices.argtypes = [byte]
    lib.clearSlices.restype = byte
    lib.auditionSlice.argtypes = [byte, byte, byte]
    lib.auditionSlice.restype = byte
    lib.releaseSlice.argtypes = [byte, byte]
    lib.releaseSlice.restype = byte
    lib.stopSlices.argtypes = [byte]
    lib.stopSlices.restype = byte
    lib.getSlicePlayheads.argtypes = [
        byte, ctypes.POINTER(byte), ctypes.POINTER(ctypes.c_float),
        ctypes.POINTER(u32), byte]
    lib.getSlicePlayheads.restype = byte


class TestSlicerAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.isfile(LIB_PATH):
            raise unittest.SkipTest(
                f"{LIB_PATH} not found; build zynslicer first")
        cls.lib = ctypes.CDLL(LIB_PATH)
        configure_library(cls.lib)
        result = cls.lib.init()
        if result != ERROR_SUCCESS:
            raise RuntimeError(
                f"libzynslicer.init() failed with {result}. "
                "Is JACK running, and is the zynslicer client already in use?")

        jackname = cls.lib.getJackname()
        if not jackname:
            raise RuntimeError("libzynslicer.getJackname() returned NULL")
        cls.jackname = jackname.decode("utf-8")

        cls.tempdir = tempfile.TemporaryDirectory(prefix="zynslicer-tests-")
        cls.wav_path = os.path.join(cls.tempdir.name, "slicer-test.wav")
        make_test_wav(cls.wav_path)

    @classmethod
    def tearDownClass(cls):
        cls.lib.end()
        cls.tempdir.cleanup()

    def setUp(self):
        self._remove_all_players()

    def tearDown(self):
        self._remove_all_players()

    def _remove_all_players(self):
        for channel in range(MAX_PLAYERS):
            self.lib.removePlayer(channel)

    def _make_slicer_player(self, channel=0):
        player = self.lib.addPlayer(channel)
        self.assertEqual(player, channel)
        return player

    def _load_sample(self, channel=0):
        frames = self.lib.getFileFrames(self.wav_path.encode())
        self.assertGreater(frames, 0)
        result = self.lib.loadSample(
            channel, self.wav_path.encode(), 0, 0, 4)
        self.assertEqual(result, ERROR_SUCCESS)
        self.assertEqual(self.lib.getSampleFrames(channel), frames)
        return frames

    # ------------------------------------------------------------------
    # Player allocation
    # ------------------------------------------------------------------

    def test_aa00_add_player_allocation(self):
        self.assertEqual(self.lib.addPlayer(0), 0)
        # Requested channel is occupied: return the first free player.
        self.assertEqual(self.lib.addPlayer(0), 1)
        self.assertEqual(self.lib.removePlayer(0), ERROR_SUCCESS)
        # Freed player can be requested again.
        self.assertEqual(self.lib.addPlayer(0), 0)
        # Fill the pool.
        for channel in range(2, MAX_PLAYERS):
            self.assertEqual(self.lib.addPlayer(channel), channel)
        self.assertEqual(self.lib.addPlayer(255), 255)

    def test_aa01_invalid_calls(self):
        self.assertNotEqual(self.lib.removePlayer(0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.removePlayer(16), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setPolyphony(0, 4), ERROR_SUCCESS)
        self.assertEqual(self.lib.getSampleFrames(16), 0)

    # ------------------------------------------------------------------
    # Sample / slice API
    # ------------------------------------------------------------------

    def test_ba00_load_sample(self):
        channel = self._make_slicer_player()
        frames = self._load_sample(channel)
        self.assertNotEqual(self.lib.loadSample(
            channel, b"/does/not/exist.wav", 0, 0, 4), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.loadSample(
            channel, self.wav_path.encode(), 100, 50, 4), ERROR_SUCCESS)
        self.assertEqual(self.lib.getSampleFrames(channel), frames)

    def test_ba01_set_and_clear_slices(self):
        channel = self._make_slicer_player()
        frames = self._load_sample(channel)
        midpoint = frames // 2

        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, midpoint, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertEqual(self.lib.setSlice(
            channel, 37, midpoint, frames, ctypes.c_float(0.5), 0), ERROR_SUCCESS)
        self.assertEqual(self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)
        notes = (ctypes.c_uint8 * 16)()
        progress = (ctypes.c_float * 16)()
        order = (ctypes.c_uint32 * 16)()
        count = self.lib.getSlicePlayheads(
            channel, notes, progress, order, 16)
        self.assertEqual(count, 1)
        self.assertEqual(notes[0], 36)
        self.assertGreaterEqual(progress[0], 0.0)
        self.assertLessEqual(progress[0], 1.0)
        self.assertGreater(order[0], 0)
        self.assertEqual(self.lib.getSlicePlayheads(
            channel, notes, progress, order, 0), 0)
        self.assertEqual(self.lib.getSlicePlayheads(
            16, notes, progress, order, 16), 0)
        self.assertEqual(self.lib.stopSlices(channel), ERROR_SUCCESS)

        # Invalid ranges and notes must be rejected.
        self.assertNotEqual(self.lib.setSlice(
            channel, 38, 10, 10, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSlice(
            channel, 38, 0, frames + 1, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSlice(
            channel, 0, 0, midpoint, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSlice(
            channel, 128, 0, midpoint, ctypes.c_float(1.0), 0), ERROR_SUCCESS)

        self.assertEqual(self.lib.clearSlices(channel), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)

    def test_ba02_update_existing_slice(self):
        channel = self._make_slicer_player()
        frames = self._load_sample(channel)
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, frames // 4, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertEqual(self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)
        # Updating the same note must succeed while a voice is active.
        self.assertEqual(self.lib.setSlice(
            channel, 36, frames // 8, frames // 2,
            ctypes.c_float(0.25), SLICE_FLAG_GATE), ERROR_SUCCESS)

    def _count_playing(self, channel):
        notes = (ctypes.c_uint8 * 16)()
        progress = (ctypes.c_float * 16)()
        order = (ctypes.c_uint32 * 16)()
        return self.lib.getSlicePlayheads(channel, notes, progress, order, 16)

    def test_ba02b_loop_repeats_until_stopped(self):
        channel = self._make_slicer_player()
        self._load_sample(channel)
        short = 2048  # ~43 ms at 48 kHz, much shorter than the waits below
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, short, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertEqual(self.lib.setSlice(
            channel, 37, short, 2 * short, ctypes.c_float(1.0), SLICE_FLAG_LOOP), ERROR_SUCCESS)
        self.assertEqual(self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)
        self.assertEqual(self.lib.auditionSlice(channel, 37, 127), ERROR_SUCCESS)
        time.sleep(0.3)
        # The one-shot slice has ended; the looping one is still playing
        self.assertEqual(self._count_playing(channel), 1)
        # Releasing it, as a note-off does, fades it out
        self.assertEqual(self.lib.releaseSlice(channel, 37), ERROR_SUCCESS)
        time.sleep(0.1)
        self.assertEqual(self._count_playing(channel), 0)

    def test_ba02c_tune_changes_slice_speed(self):
        channel = self._make_slicer_player()
        self._load_sample(channel)
        length = 9600  # 200 ms at 48 kHz
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, length, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        # Undefined slices, bad notes and NaN are refused
        self.assertNotEqual(self.lib.setSliceTune(channel, 37, 1.0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSliceTune(channel, 0, 1.0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSliceTune(16, 36, 1.0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSliceTune(channel, 36, float("nan")), ERROR_SUCCESS)
        # An octave down plays at half speed: still playing after its untuned length
        self.assertEqual(self.lib.setSliceTune(channel, 36, -12.0), ERROR_SUCCESS)
        self.assertEqual(self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)
        time.sleep(0.3)
        self.assertEqual(self._count_playing(channel), 1)
        # Retuning a playing slice two octaves up makes it end quickly
        self.assertEqual(self.lib.setSliceTune(channel, 36, 24.0), ERROR_SUCCESS)
        time.sleep(0.15)
        self.assertEqual(self._count_playing(channel), 0)

    def test_ba03_polyphony(self):
        channel = self._make_slicer_player()
        self._load_sample(channel)
        for voices in (0, 1, 4, 16, 17, 255):
            self.assertEqual(self.lib.setPolyphony(channel, voices), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setPolyphony(16, 4), ERROR_SUCCESS)

    def test_ba04_unload_sample(self):
        channel = self._make_slicer_player()
        self._load_sample(channel)
        self.assertEqual(self.lib.unloadSample(channel), ERROR_SUCCESS)
        self.assertEqual(self.lib.getSampleFrames(channel), 0)
        self.assertNotEqual(self.lib.setSlice(
            channel, 36, 0, 1, ctypes.c_float(1.0), 0), ERROR_SUCCESS)

    def test_ba06_crop_relative_slice_frames(self):
        channel = self._make_slicer_player()
        file_frames = self.lib.getFileFrames(self.wav_path.encode())
        start = 1000
        end = min(start + 4000, file_frames)
        self.assertGreater(end, start)
        self.assertEqual(self.lib.loadSample(
            channel, self.wav_path.encode(), start, end, 4), ERROR_SUCCESS)
        crop_frames = end - start
        self.assertEqual(self.lib.getSampleFrames(channel), crop_frames)
        # Slice positions are relative to the crop, not the source file.
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, crop_frames, ctypes.c_float(1.0), 0),
            ERROR_SUCCESS)
        self.assertEqual(self.lib.setSlice(
            channel, 37, crop_frames - 1, crop_frames,
            ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self.assertNotEqual(self.lib.setSlice(
            channel, 38, 0, crop_frames + 1,
            ctypes.c_float(1.0), 0), ERROR_SUCCESS)

    def test_ba07_reload_clears_old_slices(self):
        channel = self._make_slicer_player()
        frames = self._load_sample(channel)
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, frames, ctypes.c_float(1.0), 0), ERROR_SUCCESS)
        self._load_sample(channel)
        self.assertNotEqual(self.lib.auditionSlice(channel, 36, 127),
                            ERROR_SUCCESS)

    # ------------------------------------------------------------------
    # Audio output (optional; needs the Python jack package)
    # ------------------------------------------------------------------

    @unittest.skipUnless(HAVE_JACK, "python jack package not installed")
    def test_da00_audition_produces_audio(self):
        channel = self._make_slicer_player()
        frames = self._load_sample(channel)
        self.assertEqual(self.lib.setSlice(
            channel, 36, 0, frames, ctypes.c_float(1.0), 0), ERROR_SUCCESS)

        capture = jack.Client("zynslicer_audio_test")
        level = [0.0]
        port_a = capture.inports.register("in_a")

        def process(frames):
            data = port_a.get_array()
            level[0] += float(sum(abs(v) for v in data))

        try:
            capture.inports.register("in_b")
            capture.set_process_callback(process)
            # jack.Client.connect() only works after activation.
            capture.activate()
            capture.connect(
                f"{self.jackname}:out_01a", f"{capture.name}:in_a")
            capture.connect(
                f"{self.jackname}:out_01b", f"{capture.name}:in_b")
            time.sleep(0.05)  # Let JACK settle the graph.
            self.assertEqual(
                self.lib.auditionSlice(channel, 36, 127), ERROR_SUCCESS)
            time.sleep(0.25)
        finally:
            try:
                capture.deactivate()
                capture.close()
            except Exception:
                pass

        self.assertGreater(level[0], 1e-6, "No audio captured from zynslicer output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
