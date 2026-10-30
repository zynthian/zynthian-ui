#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynseq external clock sync tests
#
# Integration tests of zynseq external clock synchronization (PLL), running the
# real library on a private JACK server (dummy backend, freewheel mode).
#
# A test client sends MIDI clock to zynseq:clock_in at exact frame times, with
# optional jitter. Another client records zynseq's MIDI clock output, tempo and
# metronome clicks, which are compared with the ideal input clock.
#
# Run from zynthian-ui directory, with the python venv activated (needs jackd,
# the JACK-Client and numpy python modules, and a built libzynseq.so):
#   source venv/bin/activate
#   python3 -m unittest discover -s zynlibs/zynseq/tests -v
# Set ZYNTEST_LOG=INFO to show the measured values.
#
# Copyright (C) 2026 Fernando Moyano <jofemodo@zynthian.org>
#
# ******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
# ******************************************************************************

import os
import sys
import time
import ctypes
import random
import logging
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jacktest import JackTestServer, FreewheelRunner, MidiSource, Recorder

logging.basicConfig(level=os.environ.get("ZYNTEST_LOG", "WARNING"), format="%(message)s")
log = logging.getLogger(__name__)

LIB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "libzynseq.so")

RATE = 48000
PERIOD = 256
PPQN_INTERNAL = 1920
PPQN_MIDI = 24
DEFAULT_TEMPO = 120.0
MIDI_CLOCK = b"\xf8"
MIDI_START = b"\xfa"
METRO_MODE_OFF = 0
METRO_MODE_ON = 2
TRANSPORT_CLIENT_ALL = 255
METRO_PIP_LEN = 2200   # Length in samples of metronome beat click (metronome.h)
METRO_PEEP_LEN = 1693  # Length in samples of metronome bar start click (metronome.h)

server = None
runner = None
source = None
staller = None
recorder = None
probe = None
lib = None


def load_libzynseq():
    lib = ctypes.CDLL(LIB_PATH)
    lib.init.argtypes = [ctypes.c_char_p]
    lib.getTempo.restype = ctypes.c_double
    lib.setTempo.argtypes = [ctypes.c_double]
    lib.setExtClockPPQN.argtypes = [ctypes.c_uint8]
    lib.setMetronomeMode.argtypes = [ctypes.c_uint8]
    lib.transportStop.argtypes = [ctypes.c_uint8]
    return lib


class TempoProbe:
    """Recorder hook sampling zynseq tempo on each cycle"""

    def __init__(self):
        self.tempo = []  # List of (frame, tempo)

    def __call__(self, frame, nframes):
        self.tempo.append((frame, lib.getTempo()))


def setUpModule():
    global server, runner, source, staller, recorder, probe, lib
    if not os.path.isfile(LIB_PATH):
        raise unittest.SkipTest(f"{LIB_PATH} not found. Build zynseq first.")
    server = JackTestServer("zyntest", RATE, PERIOD)
    server.start()
    lib = load_libzynseq()
    lib.init(b"zyntest_seq")
    runner = FreewheelRunner(server)
    source = MidiSource(server)
    staller = MidiSource(server, "zyntest_staller")  # Used to cause xruns of zynseq
    recorder = Recorder(server, midi_ports=("clock",), audio_ports=("metronome",))
    probe = TempoProbe()
    recorder.hooks.append(probe)
    for client in (runner, source, staller, recorder):
        client.activate()
    # Connections set the process order: source => zynseq => recorder
    source.port.connect("zyntest_seq:clock_in")
    staller.port.connect("zyntest_seq:input")
    recorder.midi_ports["clock"].connect("zyntest_seq:clock")
    recorder.audio_ports["metronome"].connect("zyntest_seq:metronome")


def tearDownModule():
    for client in (runner, source, staller, recorder):
        if client:
            client.close()
    if server:
        server.stop()


def clock_pulses(start, segments, ppqn=PPQN_MIDI, jitter_ms=0.0, quantize=False, seed=1):
    """Generate external clock pulses

    start: Frame time of first pulse
    segments: List of (duration in seconds, BPM)
    jitter_ms: Standard deviation of gaussian timing jitter
    quantize: True to emulate drivers that timestamp events at the start of jack period
    returns: (ideal pulse frames as numpy array, list of (frame, MIDI_CLOCK) events)
    """
    rng = random.Random(seed)
    ideal = []
    events = []
    t = float(start)
    seg_end = float(start)
    last = start
    for duration, bpm in segments:
        seg_end += duration * RATE
        period = 60.0 * RATE / (bpm * ppqn)
        while t < seg_end:
            ideal.append(t)
            frame = t + rng.gauss(0.0, jitter_ms * RATE / 1000.0) if jitter_ms else t
            frame = int(frame) // PERIOD * PERIOD if quantize else int(round(frame))
            last = max(frame, last)  # Keep pulses in order
            events.append((last, MIDI_CLOCK))
            t += period
    return np.array(ideal), events


def phase_errors_ms(out_frames, ideal, t0, t1, ratio=1.0):
    """Phase errors of output clock pulses relative to ideal input pulses, in window [t0, t1)

    ratio: Quantity of output pulses per input pulse
    The constant phase offset between input and output is removed.
    returns: (numpy array of phase errors in ms, quantity of output pulses, expected quantity of output pulses)
    """
    t1 = min(t1, ideal[-1])  # Output after last input pulse can't be measured
    out = np.array([f for f in out_frames if t0 <= f < t1], dtype=float)
    index = np.arange(len(ideal))
    pos = np.interp(out, ideal, index) * ratio  # Position in output pulses
    offset = np.angle(np.mean(np.exp(2j * np.pi * pos))) / (2 * np.pi)
    err = pos - offset
    err -= np.round(err)
    period = np.interp(out, ideal[:-1], np.diff(ideal)) / ratio
    expected = (np.interp(t1, ideal, index) - np.interp(t0, ideal, index)) * ratio
    return err * period / RATE * 1000.0, len(out), expected


class TestExtClock(unittest.TestCase):

    def setUp(self):
        source.clear()
        lib.setMetronomeMode(METRO_MODE_OFF)
        lib.transportStop(TRANSPORT_CLIENT_ALL)
        lib.setExtClockPPQN(PPQN_MIDI)  # Also resets the PLL
        runner.run_seconds(0.1)
        lib.setTempo(DEFAULT_TEMPO)
        runner.run_seconds(0.1)
        recorder.clear()
        with recorder.lock:
            probe.tempo = []

    # ----------------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------------

    @staticmethod
    def start_frame():
        """Frame time to start a scenario, with margin to schedule events in advance"""
        return runner.frame_time + server.seconds(0.2)

    def play(self, events, until, extra=0.5):
        """Send events and run until frame 'until' plus 'extra' seconds"""
        source.schedule(events)
        runner.run(int(until) - runner.frame_time + server.seconds(extra))
        self.assertEqual(source.late, 0, "MIDI events were sent late")

    def out_clock(self):
        return [f for f, data in recorder.midi["clock"] if data == MIDI_CLOCK]

    def check_sync(self, start, ideal, segments, settle=3.0, tempo_tol=0.5, rms_max=1.0, err_max=3.0, ratio=1.0):
        """Check tempo and phase lock on each segment, after settle time"""
        seg_start = start
        for duration, bpm in segments:
            t0 = seg_start + server.seconds(settle)
            t1 = seg_start + server.seconds(duration - 0.1)
            seg_start += server.seconds(duration)
            with self.subTest(bpm=bpm):
                tempos = np.array([t for f, t in probe.tempo if t0 <= f < t1])
                self.assertTrue(len(tempos), "No tempo samples")
                tempo_err = np.max(np.abs(tempos - bpm))
                err, count, expected = phase_errors_ms(self.out_clock(), ideal, t0, t1, ratio)
                rms = np.sqrt(np.mean(err ** 2))
                log.info(f"{self.id().split('.')[-1]} {bpm} BPM: tempo [{tempos.min():.3f}..{tempos.max():.3f}],"
                         f" phase err rms={rms:.3f}ms max={np.max(np.abs(err)):.3f}ms, pulses {count}/{expected:.1f}")
                self.assertLessEqual(tempo_err, tempo_tol, f"Tempo error {tempo_err:.3f} BPM")
                self.assertLessEqual(rms, rms_max, f"Phase error rms {rms:.3f} ms")
                self.assertLessEqual(np.max(np.abs(err)), err_max, f"Phase error max {np.max(np.abs(err)):.3f} ms")
                # Each input pulse must produce exactly 'ratio' output pulses => no skipped or repeated ticks
                self.assertAlmostEqual(count, expected, delta=1.0, msg="Skipped or repeated clock pulses")

    def check_beats(self, ideal, first_pulse, beats=8, beats_per_bar=4, bpm=DEFAULT_TEMPO, first_beat=0):
        """Check metronome beats are aligned to input pulses, from first_pulse

        first_beat: Beat index (since bar start) of first_pulse
        """
        frames_per_tick = 60.0 * RATE / (bpm * PPQN_INTERNAL)
        clicks = [c for c in recorder.clicks["metronome"] if c[0] >= ideal[first_pulse] - 1]
        self.assertGreaterEqual(len(clicks), beats, "Missing metronome beats")
        for n in range(beats):
            pulse_frame = ideal[first_pulse + n * PPQN_MIDI]
            frame, length = clicks[n]
            is_bar = abs(length - METRO_PEEP_LEN) < abs(length - METRO_PIP_LEN)
            with self.subTest(beat=n):
                # Beat is on first internal tick at or after the pulse (+/-1 frame rounding)
                self.assertTrue(-1 <= frame - pulse_frame <= frames_per_tick + 1,
                                f"Beat {n} at {frame - pulse_frame:.1f} frames from pulse")
                self.assertEqual(is_bar, (first_beat + n) % beats_per_bar == 0, f"Beat {n} bar start mismatch")

    # ----------------------------------------------------------------------------
    # Tests
    # ----------------------------------------------------------------------------

    def test_01_steady_clock(self):
        segments = [(10.0, 120)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments, tempo_tol=0.01, rms_max=0.05, err_max=0.1)

    def test_02_jitter(self):
        segments = [(20.0, 120)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments, jitter_ms=2.0)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments)

    def test_03_period_quantized_timestamps(self):
        segments = [(20.0, 120)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments, quantize=True)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments)

    def test_04_tempo_change(self):
        segments = [(10.0, 120), (10.0, 90)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments, jitter_ms=1.0)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments)

    def test_05_tempo_jumps(self):
        segments = [(8.0, 174), (8.0, 60), (8.0, 174)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments, jitter_ms=1.0)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments, settle=4.0)

    def test_06_low_ppqn(self):
        ppqn = 4
        lib.setExtClockPPQN(ppqn)
        segments = [(15.0, 120)]
        start = self.start_frame()
        ideal, clock = clock_pulses(start, segments, ppqn=ppqn)
        self.play(clock, ideal[-1])
        self.check_sync(start, ideal, segments, settle=5.0, tempo_tol=0.05, rms_max=0.1, err_max=0.2,
                        ratio=PPQN_MIDI / ppqn)

    def test_07_clock_lost(self):
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(6.0, 120)])
        self.play(clock, ideal[-1], extra=6.0)
        # Free running at last tempo
        t0 = ideal[-1] + server.seconds(1.0)
        tempos = np.array([t for f, t in probe.tempo if f >= t0])
        self.assertLessEqual(np.max(np.abs(tempos - 120)), 0.1)
        intervals = np.diff([f for f in self.out_clock() if f >= t0])
        expected = 60.0 * RATE / (120 * PPQN_MIDI)
        log.info(f"{self.id().split('.')[-1]}: free run tempo [{tempos.min():.3f}..{tempos.max():.3f}],"
                 f" clock interval {np.mean(intervals):.2f} frames (expected {expected:.2f})")
        self.assertAlmostEqual(np.mean(intervals), expected, delta=expected * 0.01)

    def test_08_set_tempo_ignored_while_locked(self):
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(6.0, 120)])
        source.schedule(clock)
        runner.run(int(ideal[0]) - runner.frame_time + server.seconds(3.0))
        lib.setTempo(90.0)
        runner.run(int(ideal[-1]) - runner.frame_time + server.seconds(0.01))
        self.assertAlmostEqual(lib.getTempo(), 120.0, delta=0.5)
        # Once clock is lost, tempo can be set again
        runner.run_seconds(1.0)
        lib.setTempo(90.0)
        self.assertAlmostEqual(lib.getTempo(), 90.0)

    def test_09_start_aligns_bar(self):
        # Clock running and locked, then MIDI START => first pulse after START is bar start
        lib.setMetronomeMode(METRO_MODE_ON)
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(8.0, 120)])
        first = PPQN_MIDI * 8 + 5  # Not on an internal beat
        self.play(clock + [(int(ideal[first]) - 100, MIDI_START)], ideal[-1])
        self.check_beats(ideal, first)

    def test_10_start_before_clock(self):
        # Devices that send clock only while playing: MIDI START, then clock starts => first pulse is bar start
        lib.setMetronomeMode(METRO_MODE_ON)
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(8.0, 120)])
        self.play([(start - 100, MIDI_START)] + clock, ideal[-1])
        self.check_beats(ideal, 0)

    def test_11_start_before_clock_other_tempo(self):
        # As above, with external tempo far from internal tempo => phase error before lock must be corrected
        lib.setMetronomeMode(METRO_MODE_ON)
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(8.0, 80)])
        self.play([(start - 100, MIDI_START)] + clock, ideal[-1])
        self.check_beats(ideal, 0, bpm=80)

    def test_12_missing_pulses(self):
        # Isolated lost pulses (e.g. dropped MIDI bytes) must not shift beats nor change tempo
        lib.setMetronomeMode(METRO_MODE_ON)
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(12.0, 120)])
        first = PPQN_MIDI * 4
        lost = {first + 30, first + 100, first + 101, first + 170}  # Single and double gaps
        events = [ev for i, ev in enumerate(clock) if i not in lost]
        self.play(events + [(int(ideal[first]) - 100, MIDI_START)], ideal[-1])
        self.check_beats(ideal, first, beats=16)
        tempos = np.array([t for f, t in probe.tempo if ideal[first] <= f < ideal[-1]])
        self.assertLessEqual(np.max(np.abs(tempos - 120)), 0.5, "Tempo changed by lost pulses")

    def check_xrun(self, stall):
        """Cycles lost by an xrun must not shift beats

        A client connected to zynseq input blocks a cycle for 'stall' seconds, so zynseq skips cycles (losing clock
        pulses and internal ticks), as in a real xrun. It needs real time processing (not freewheel).
        """
        lib.setMetronomeMode(METRO_MODE_ON)
        start = self.start_frame()
        ideal, clock = clock_pulses(start, [(14.0, 120)])
        first = PPQN_MIDI * 2
        source.schedule(clock + [(int(ideal[first]) - 100, MIDI_START)])
        runner.run(int(ideal[0]) - runner.frame_time + server.seconds(4.0))
        recorder.discontinuities = 0
        xrun_frame = runner.frame_time
        staller.stall(stall)
        time.sleep(0.3)
        self.assertGreater(recorder.discontinuities, 0, "No xrun happened")
        runner.run(int(ideal[-1]) - runner.frame_time + server.seconds(0.5))
        # Beats aligned again 2 seconds after the xrun
        beat = int(np.ceil((np.searchsorted(ideal, xrun_frame + server.seconds(2.0)) - first) / PPQN_MIDI))
        self.check_beats(ideal, first + beat * PPQN_MIDI, beats=8, first_beat=beat)
        tempos = np.array([t for f, t in probe.tempo if xrun_frame + server.seconds(2.0) <= f < ideal[-1]])
        self.assertLessEqual(np.max(np.abs(tempos - 120)), 0.5, "Tempo not recovered after xrun")

    def test_13_xrun(self):
        self.check_xrun(0.02)  # About 4 jack periods, 1 clock pulse lost

    def test_14_long_xrun(self):
        self.check_xrun(0.15)  # About 28 jack periods, 7 clock pulses lost


if __name__ == "__main__":
    unittest.main()
