#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Slicer engine tests
#
# Unit tests for the slicer engine, its slice analysis and its SFZ export.
# They don't need JACK or the zynslicer library: the engine is built without
# __init__ and talks to a fake library. Run on a Zynthian with:
#
#     python3 zyngine/zynthian_engine_slicer_test.py
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

import json
import os
import sys
import tempfile
import unittest

# Allow running this file directly
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import numpy as np
    import soundfile as sf
    HAVE_AUDIO = True
except ImportError:
    HAVE_AUDIO = False

try:
    from zyngine import zynthian_slicer_sfz
    from zyngine.zynthian_slicer_analysis import (
        MAX_SLICES, make_even_slices, detect_transients, normalize_slices)
    from zyngine.zynthian_engine_slicer import (
        zynthian_engine_slicer, SlicerState, SLICER_CTRLS, SLICER_CTRL_SCREENS, PLAY_MODE_FLAGS)
    IMPORT_ERROR = None
except Exception as e:  # Missing Zynthian dependencies on a development host
    IMPORT_ERROR = str(e)

needs_engine = unittest.skipIf(IMPORT_ERROR, f"Slicer not importable: {IMPORT_ERROR}")
needs_audio = unittest.skipUnless(HAVE_AUDIO, "numpy/soundfile not installed")

# ------------------------------------------------------------------------------
# Fakes
# ------------------------------------------------------------------------------


class FakeController:
    def __init__(self, symbol, options):
        self.symbol = symbol
        self.value = options.get("value", 0)
        self.options = {}

    def set_value(self, value, send=True):
        self.value = value

    def set_options(self, options):
        self.options.update(options)


class FakeZctrl:
    def __init__(self, symbol, processor, value):
        self.symbol = symbol
        self.processor = processor
        self.value = value


class FakeProcessor:
    def __init__(self, engine, channel=0):
        self.engine = engine
        self.chain_id = None
        self.midi_chan = channel
        self.set_state_flag = False
        self.preset_name = None
        self.jackname = None
        self.controllers_dict = {sym: FakeController(sym, opts) for sym, opts in SLICER_CTRLS}
        self.slicer = SlicerState(channel=channel)

    def set_midi_chan(self, midi_chan):
        self.midi_chan = midi_chan
        self.engine.set_midi_chan(self)

    def ctrl(self, symbol):
        return self.controllers_dict[symbol].value


class FakeLib:
    """Records calls to the zynslicer API."""

    def __init__(self, file_frames=1000):
        self.calls = []
        self.file_frames = file_frames
        self.players = set()
        self.refuse_channels = set()  # addPlayer() fails for these

    def _log(self, *call):
        self.calls.append(call)
        return 0

    def calls_named(self, name):
        return [c for c in self.calls if c[0] == name]

    def addPlayer(self, channel):
        self._log("addPlayer", channel)
        if channel in self.refuse_channels:
            return 255
        if channel >= 16 or channel in self.players:
            channel = next((c for c in range(16) if c not in self.players), 255)
        if channel < 16:
            self.players.add(channel)
        return channel

    def removePlayer(self, channel):
        self.players.discard(channel)
        return self._log("removePlayer", channel)

    def setSlice(self, channel, note, start, end, gain, flags):
        return self._log("setSlice", channel, note, start, end, round(gain.value, 4), flags)

    def setSliceTune(self, channel, note, semitones):
        return self._log("setSliceTune", channel, note, round(semitones.value, 4))

    def getFileFrames(self, path):
        return self.file_frames

    def loadSample(self, channel, path, start, end, quality):
        return self._log("loadSample", channel, path.decode(), start, end)

    def getSlicePlayheads(self, channel, notes, progress, order, max_count):
        return 0

    def __getattr__(self, name):
        # Any other API call just gets recorded
        return lambda *args: self._log(name, *args)


def make_engine(file_frames=1000):
    engine = object.__new__(zynthian_engine_slicer)
    engine.libslicer = FakeLib(file_frames)
    engine.monitored_proc = None
    engine.reload_timers = {}
    engine.samplerate = 48000
    engine.name = "Slicer"
    engine.processors = []
    engine.messages = []
    engine._show_message = engine.messages.append
    return engine


def make_slices(*bounds, **fields):
    fields.setdefault("mode", "one-shot")
    return [dict(start=s, end=e, gain=1.0, **fields) for s, e in bounds]


# ------------------------------------------------------------------------------
# Slice analysis
# ------------------------------------------------------------------------------


@needs_engine
class TestAnalysis(unittest.TestCase):

    def test_make_even_slices(self):
        slices = make_even_slices(1000, 4)
        self.assertEqual([(s["start"], s["end"]) for s in slices],
                         [(0, 250), (250, 500), (500, 750), (750, 1000)])

    def test_make_even_slices_limits(self):
        self.assertEqual(make_even_slices(0, 4), [])
        self.assertEqual(len(make_even_slices(1000, 0)), 1)
        self.assertEqual(len(make_even_slices(1000, MAX_SLICES + 50)), MAX_SLICES)

    def test_normalize_makes_slices_contiguous(self):
        slices = make_slices((0, 400), (300, 700), (900, 950))
        normalized = normalize_slices(slices, 1000, base_note=36)
        self.assertEqual([(s["start"], s["end"], s["note"]) for s in normalized],
                         [(0, 300, 36), (300, 900, 37), (900, 950, 38)])

    def test_normalize_clamps_and_skips_invalid(self):
        slices = make_slices((-10, 2000), (500, 400), (800, 900))
        normalized = normalize_slices(slices, 1000, base_note=36)
        self.assertEqual([(s["start"], s["end"], s["note"]) for s in normalized],
                         [(0, 800, 36), (800, 900, 37)])

    def test_normalize_assigns_notes_from_base_note(self):
        # Stored notes are ignored: slice i always plays base_note + i
        slices = make_slices((0, 400), (400, 1000), note=60)
        normalized = normalize_slices(slices, 1000, base_note=48)
        self.assertEqual([s["note"] for s in normalized], [48, 49])

    def test_normalize_converts_legacy_one_shot_flag(self):
        slices = [{"start": 0, "end": 500, "one_shot": True},
                  {"start": 500, "end": 1000, "one_shot": False},
                  {"start": 1000, "end": 1500}]
        normalized = normalize_slices(slices, 2000, base_note=36)
        self.assertEqual([s["mode"] for s in normalized], ["one-shot", "gate", "one-shot"])
        self.assertTrue(all("one_shot" not in s for s in normalized))

    def test_new_slices_default_to_gate(self):
        for slices in (make_even_slices(1000, 4), normalize_slices(make_even_slices(1000, 4), 1000, 36)):
            self.assertEqual({s["mode"] for s in slices}, {"gate"})

    def test_normalize_drops_slices_above_top_note(self):
        slices = make_even_slices(1000, 10)
        with self.assertLogs(level="WARNING"):
            normalized = normalize_slices(slices, 1000, base_note=120)
        self.assertEqual([s["note"] for s in normalized], list(range(120, 128)))

    @needs_audio
    def test_detect_transients_click_track(self):
        samplerate = 48000
        frames = samplerate * 2
        signal = np.zeros(frames, dtype=np.float32)
        signal[::samplerate // 2] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "click.wav")
            sf.write(path, signal, samplerate)
            slices = detect_transients(path, frames, threshold=50, min_gap_ms=100)
        starts = [s["start"] for s in slices]
        for pos in range(0, frames, samplerate // 2):
            self.assertTrue(any(abs(start - pos) <= samplerate // 20 for start in starts),
                            f"No transient near frame {pos}: {starts}")
        self.assertEqual(slices[-1]["end"], frames)

    @needs_audio
    def test_detect_transients_silence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "silence.wav")
            sf.write(path, np.zeros(48000, dtype=np.float32), 48000)
            self.assertEqual(detect_transients(path, 48000), [])

    @needs_audio
    def test_detect_transients_scales_to_source_frames(self):
        signal = np.zeros(96000, dtype=np.float32)
        signal[::24000] = 1.0
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "click.wav")
            sf.write(path, signal, 48000)
            slices = detect_transients(path, 24000, threshold=50, min_gap_ms=100)
        self.assertTrue(slices)
        self.assertEqual(slices[-1]["end"], 24000)


# ------------------------------------------------------------------------------
# SFZ export
# ------------------------------------------------------------------------------


@needs_engine
class TestSfz(unittest.TestCase):

    def setUp(self):
        self.slices = [
            {"start": 100, "end": 200, "note": 36, "gain": 1.0, "mode": "one-shot"},
            {"start": 200, "end": 300, "note": 37, "gain": 0.5, "mode": "gate"},
        ]

    def test_regions_use_inclusive_end_and_play_modes(self):
        text = zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav", gain_db=-3.0)
        for opcode in ("offset=100", "end=199", "offset=200", "end=299",
                       "lokey=36", "hikey=36", "pitch_keycenter=36",
                       "loop_mode=one_shot", "loop_mode=no_loop",
                       "volume=-3.00", "volume=-9.02"):
            self.assertIn(opcode, text)

    def test_loop_region_loops_whole_slice(self):
        self.slices[1]["mode"] = "loop"
        text = zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav")
        region = text.split("// slice 1")[1]
        for opcode in ("loop_mode=loop_continuous", "loop_start=200", "loop_end=299"):
            self.assertIn(opcode, region)
        self.assertNotIn("loop_start", text.split("// slice 1")[0])

    def test_global_header_matches_player(self):
        text = zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav", polyphony=1,
                                            fade_seconds=64 / 48000)
        self.assertIn("polyphony=1", text)
        self.assertIn("ampeg_attack=0.0013", text)
        self.assertIn("ampeg_release=0.0013", text)
        self.assertLess(text.index("<global>"), text.index("<region>"))
        # sfizz prepends default_path verbatim, which breaks sample paths
        self.assertNotIn("default_path", text)

    def test_tune_is_a_cc_control(self):
        text = zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav", tune=-3)
        control, rest = text.split("<global>")
        self.assertIn("<control>\nlabel_cc20=Tune\nset_cc20=61\n", control)
        # 100 cents per CC step, no change at CC 64
        global_section = rest.split("<region>")[0]
        self.assertIn("transpose=-64", global_section)
        self.assertIn("pitch_oncc20=12700", global_section)
        self.assertEqual(text.count("transpose"), 1)  # Not repeated per region
        self.assertLess(text.index("<control>"), text.index("<global>"))

    def test_tune_cc_value_is_clamped(self):
        self.assertIn("set_cc20=64\n", zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav"))
        self.assertIn("set_cc20=127\n", zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav", tune=99))
        self.assertIn("set_cc20=0\n", zynthian_slicer_sfz.build_sfz(self.slices, "clip.wav", tune=-99))

    def test_controller_yaml_defines_tune_knob(self):
        text = zynthian_slicer_sfz.build_controller_yaml(tune=7)
        try:
            import yaml
        except ImportError:
            self.assertIn("midi_cc: 20", text)
            return
        tune = yaml.safe_load(text)["controllers"]["slicer"]["tune"]
        self.assertEqual(tune, {"midi_cc": 20, "value_min": -64, "value_max": 63,
                                "value": 7, "is_integer": True})

    def test_rejects_empty_slices(self):
        with self.assertRaises(ValueError):
            zynthian_slicer_sfz.build_sfz([], "clip.wav")

    @needs_audio
    def test_export_creates_self_contained_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "clip.flac")
            sf.write(source, np.zeros(1000, dtype=np.float32), 48000)
            sfz_path = zynthian_slicer_sfz.export_sfz(source, self.slices, os.path.join(tmp, "out"))
            self.assertEqual(sfz_path, os.path.join(tmp, "out", "clip", "clip.sfz"))
            wav_path = os.path.join(tmp, "out", "clip", "clip.wav")
            self.assertEqual(sf.info(wav_path).frames, 1000)
            with open(sfz_path, encoding="utf-8") as fh:
                self.assertIn("sample=clip.wav", fh.read())
            # The sfizz engine reads <name>.yml for the chain's controls
            with open(os.path.join(tmp, "out", "clip", "clip.yml"), encoding="utf-8") as fh:
                self.assertIn("midi_cc: 20", fh.read())

    @needs_audio
    def test_export_handles_name_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out")
            sources = []
            for sub in ("a", "b"):
                os.makedirs(os.path.join(tmp, sub))
                sources.append(os.path.join(tmp, sub, "clip.wav"))
                sf.write(sources[-1], np.zeros(1000, dtype=np.float32), 48000)
            first = zynthian_slicer_sfz.export_sfz(sources[0], self.slices, out)
            again = zynthian_slicer_sfz.export_sfz(sources[0], self.slices, out)
            second = zynthian_slicer_sfz.export_sfz(sources[1], self.slices, out)
        self.assertEqual(first, os.path.join(out, "clip", "clip.sfz"))
        self.assertEqual(again, first)
        self.assertEqual(second, os.path.join(out, "clip_2", "clip_2.sfz"))


# ------------------------------------------------------------------------------
# Engine
# ------------------------------------------------------------------------------


@needs_engine
class TestEngineSlices(unittest.TestCase):

    def setUp(self):
        self.engine = make_engine()
        self.proc = FakeProcessor(self.engine)
        self.proc.slicer.file = "/tmp/clip.wav"
        self.proc.slicer.source_frames = 1000
        self.lib = self.engine.libslicer

    def send(self, symbol, value):
        self.proc.controllers_dict[symbol].value = value
        self.engine.send_controller_value(FakeZctrl(symbol, self.proc, value))

    def apply(self, *bounds, **kwargs):
        self.engine.apply_slices(self.proc, make_slices(*bounds), **kwargs)
        self.lib.calls.clear()

    def test_apply_sends_slices_and_saves_them(self):
        self.engine.apply_slices(self.proc, make_slices((0, 500), (500, 1000)))
        self.assertEqual(self.lib.calls[0], ("clearSlices", 0))
        self.assertEqual(self.lib.calls_named("setSlice"),
                         [("setSlice", 0, 36, 0, 500, 1.0, 0), ("setSlice", 0, 37, 500, 1000, 1.0, 0)])
        data = json.loads(self.proc.ctrl("slice_data"))
        self.assertEqual(data["path"], "/tmp/clip.wav")
        self.assertEqual([s["note"] for s in data["slices"]], [36, 37])

    def test_base_note_change_remaps_slices(self):
        self.apply((0, 500), (500, 1000))
        self.send("base_note", 48)
        self.assertEqual([s["note"] for s in self.proc.slicer.slices], [48, 49])
        self.assertEqual([c[2] for c in self.lib.calls_named("setSlice")], [48, 49])

    def test_gain_scales_all_slices_without_clearing(self):
        self.apply((0, 500), (500, 1000))
        self.send("gain", -6.0)
        self.assertEqual(self.lib.calls_named("clearSlices"), [])
        self.assertEqual([c[5] for c in self.lib.calls_named("setSlice")], [0.5012, 0.5012])

    def test_play_mode_changes_selected_slice_only(self):
        self.apply((0, 500), (500, 1000))
        self.send("slice", 1)
        self.send("play_mode", 1)
        self.assertEqual([s["mode"] for s in self.proc.slicer.slices], ["one-shot", "gate"])
        self.assertEqual(self.lib.calls_named("setSlice")[-1],
                         ("setSlice", 0, 37, 500, 1000, 1.0, PLAY_MODE_FLAGS["gate"]))
        self.assertTrue(self.proc.slicer.manual_edits)

    def test_loop_mode_sends_loop_flag_and_is_saved(self):
        self.apply((0, 500), (500, 1000))
        self.send("slice", 0)
        self.send("play_mode", 2)
        self.assertEqual(self.proc.slicer.slices[0]["mode"], "loop")
        self.assertEqual(self.lib.calls_named("setSlice")[-1],
                         ("setSlice", 0, 36, 0, 500, 1.0, PLAY_MODE_FLAGS["loop"]))
        saved = json.loads(self.proc.ctrl("slice_data"))
        self.assertEqual([s["mode"] for s in saved["slices"]], ["loop", "one-shot"])

    def test_play_mode_controller_lists_all_modes(self):
        options = dict(SLICER_CTRLS)["play_mode"]
        self.assertEqual(options["labels"], ["one-shot", "gate", "loop"])
        self.assertEqual(options["ticks"], [0, 1, 2])
        self.assertEqual(options["value"], 1)  # gate

    def test_detected_slices_play_gated(self):
        self.engine.detect_slices(self.proc)
        flags = {c[6] for c in self.lib.calls_named("setSlice")}
        self.assertEqual(flags, {PLAY_MODE_FLAGS["gate"]})

    def test_select_slice_shows_its_settings(self):
        self.apply((0, 300), (300, 1000))
        self.proc.slicer.slices[1]["mode"] = "loop"
        self.send("slice", 1)
        self.assertEqual((self.proc.ctrl("slice_start"), self.proc.ctrl("slice_end"),
                          self.proc.ctrl("play_mode")), (300, 1000, 2))

    def test_tune_applies_to_every_slice_without_clearing(self):
        self.apply((0, 500), (500, 1000))
        self.send("tune", -2)
        self.assertEqual(self.lib.calls_named("clearSlices"), [])
        self.assertEqual(self.lib.calls_named("setSliceTune"),
                         [("setSliceTune", 0, 36, -2.0), ("setSliceTune", 0, 37, -2.0)])
        self.assertFalse(self.proc.slicer.manual_edits)

    def test_new_slices_get_the_current_tune(self):
        self.proc.controllers_dict["tune"].value = 7
        self.engine.apply_slices(self.proc, make_slices((0, 500), (500, 1000)))
        self.assertEqual(self.lib.calls_named("setSliceTune"),
                         [("setSliceTune", 0, 36, 7.0), ("setSliceTune", 0, 37, 7.0)])

    def test_tune_is_clamped(self):
        self.proc.controllers_dict["tune"].value = 99
        self.engine.apply_slices(self.proc, make_slices((0, 1000)))
        self.assertEqual(self.lib.calls_named("setSliceTune"), [("setSliceTune", 0, 36, 24.0)])

    def test_tune_is_on_the_sample_screen(self):
        screens = dict(SLICER_CTRL_SCREENS)
        self.assertEqual(screens["Sample"], ["file", "gain", "tune", "base_note"])
        self.assertEqual(screens["View"], ["zoom", "polyphony"])
        self.assertNotIn("Tune", screens)
        self.assertTrue(all(len(ctrls) <= 4 for ctrls in screens.values()))
        # Every controller except the hidden slice data is on a screen
        shown = {symbol for ctrls in screens.values() for symbol in ctrls}
        self.assertEqual({symbol for symbol, _ in SLICER_CTRLS} - shown, {"slice_data"})

    def test_boundary_move_updates_adjacent_slices(self):
        self.apply((0, 300), (300, 600), (600, 1000))
        self.send("slice", 1)
        self.send("slice_start", 350)
        self.send("slice_end", 500)
        self.assertEqual([(s["start"], s["end"]) for s in self.proc.slicer.slices],
                         [(0, 350), (350, 500), (500, 1000)])
        self.assertTrue(self.proc.slicer.manual_edits)
        saved = json.loads(self.proc.ctrl("slice_data"))
        self.assertEqual(saved["slices"][1]["start"], 350)

    def test_boundary_move_clamps_to_neighbors(self):
        self.apply((0, 300), (300, 600), (600, 1000))
        self.send("slice", 1)
        self.send("slice_start", 0)
        self.send("slice_end", 1000)
        self.assertEqual([(s["start"], s["end"]) for s in self.proc.slicer.slices],
                         [(0, 1), (1, 999), (999, 1000)])

    def test_first_start_and_last_end_are_not_locked(self):
        self.apply((0, 300), (300, 600), (600, 1000))
        self.send("slice", 0)
        self.send("slice_start", 100)
        self.send("slice", 2)
        self.send("slice_end", 900)
        slices = self.proc.slicer.slices
        self.assertEqual((slices[0]["start"], slices[-1]["end"]), (100, 900))

    def test_audition_plays_selected_note(self):
        self.apply((0, 500), (500, 1000))
        self.send("slice", 1)
        self.engine.audition_selected_slice(self.proc)
        self.assertEqual(self.lib.calls_named("auditionSlice"), [("auditionSlice", 0, 37, 127)])

    def test_audition_release_stops_like_note_off(self):
        self.apply((0, 500), (500, 1000))
        self.send("slice", 1)
        self.engine.audition_selected_slice(self.proc)
        self.engine.release_audition(self.proc)
        self.engine.release_audition(self.proc)  # Second release does nothing
        self.assertEqual(self.lib.calls_named("releaseSlice"), [("releaseSlice", 0, 37)])


@needs_engine
class TestEngineDetection(unittest.TestCase):

    def setUp(self):
        self.engine = make_engine()
        self.proc = FakeProcessor(self.engine)
        self.proc.slicer.file = "/tmp/clip.wav"
        self.proc.slicer.source_frames = 1000

    def set_ctrls(self, **values):
        for symbol, value in values.items():
            self.proc.controllers_dict[symbol].value = value

    def bounds(self):
        return [(s["start"], s["end"]) for s in self.proc.slicer.slices]

    def test_beats_mode(self):
        self.set_ctrls(slice_mode=0, slice_beats=2, slice_subdivision=3)
        self.engine.detect_slices(self.proc)
        self.assertEqual(len(self.bounds()), 6)

    def test_grid_mode(self):
        self.set_ctrls(slice_mode=1, slice_count=4)
        self.engine.detect_slices(self.proc)
        self.assertEqual(self.bounds(), [(0, 250), (250, 500), (500, 750), (750, 1000)])

    def test_manual_mode_keeps_existing_slices(self):
        self.engine.apply_slices(self.proc, make_slices((0, 300), (300, 1000)), manual_edits=True)
        self.set_ctrls(slice_mode=3, slice_count=8)
        self.engine.detect_slices(self.proc)
        self.assertEqual(self.bounds(), [(0, 300), (300, 1000)])
        self.assertTrue(self.proc.slicer.manual_edits)

    @needs_audio
    def test_transient_mode_falls_back_to_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "silence.wav")
            sf.write(path, np.zeros(48000, dtype=np.float32), 48000)
            self.proc.slicer.file = path
            self.set_ctrls(slice_mode=2, slice_count=3)
            self.engine.detect_slices(self.proc)
        self.assertEqual(len(self.bounds()), 3)

    def test_detect_overwrites_manual_edits(self):
        self.engine.apply_slices(self.proc, make_slices((0, 300), (300, 1000)), manual_edits=True)
        self.set_ctrls(slice_mode=1, slice_count=4)
        self.engine.send_controller_value(FakeZctrl("detect", self.proc, 1))
        self.assertEqual(len(self.bounds()), 4)
        self.assertFalse(self.proc.slicer.manual_edits)


@needs_engine
class TestEngineAutoSlice(unittest.TestCase):
    """Analysis settings rebuild the slices only while that is safe."""

    def setUp(self):
        self.engine = make_engine()
        self.proc = FakeProcessor(self.engine)
        self.detected = []
        self.engine.detect_slices = self.detected.append

    def send(self, symbol, value):
        self.engine.send_controller_value(FakeZctrl(symbol, self.proc, value))

    def test_rebuilds_while_untouched(self):
        self.send("slice_count", 5)
        self.assertEqual(self.detected, [self.proc])

    def test_not_after_manual_edit(self):
        self.proc.slicer.manual_edits = True
        self.send("slice_mode", 1)
        self.assertEqual(self.detected, [])

    def test_not_in_manual_mode(self):
        self.proc.controllers_dict["slice_mode"].value = 3
        self.send("slice_count", 5)
        self.assertEqual(self.detected, [])

    def test_not_during_state_restore(self):
        self.proc.set_state_flag = True
        self.send("slice_count", 5)
        self.assertEqual(self.detected, [])


@needs_engine
class TestEngineSample(unittest.TestCase):

    def setUp(self):
        self.engine = make_engine(file_frames=1000)
        self.proc = FakeProcessor(self.engine)
        self.lib = self.engine.libslicer
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "clip.wav")
        open(self.path, "wb").close()
        self.proc.controllers_dict["file"].value = self.path

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, **data):
        self.proc.controllers_dict["slice_data"].value = json.dumps(data)

    def test_load_detects_slices_for_new_file(self):
        self.proc.controllers_dict["slice_mode"].value = 1
        self.engine.load_sample(self.proc)
        self.assertEqual(self.lib.calls_named("loadSample"), [("loadSample", 0, self.path, 0, 1000)])
        self.assertEqual(len(self.proc.slicer.slices), 8)
        self.assertEqual(self.proc.preset_name, "clip.wav")
        self.assertEqual(self.proc.controllers_dict["slice_end"].options["value_max"], 1000)

    def test_load_restores_saved_slices(self):
        self.save(path=self.path, manual_edits=False, slices=make_slices((0, 400), (400, 1000)))
        self.engine.load_sample(self.proc, autoreset=False)
        self.assertEqual([(s["start"], s["end"]) for s in self.proc.slicer.slices], [(0, 400), (400, 1000)])
        self.assertFalse(self.proc.slicer.manual_edits)

    def test_legacy_saved_slices_count_as_edited(self):
        self.save(path=self.path, slices=make_slices((0, 400), (400, 1000)))
        self.engine.load_sample(self.proc, autoreset=False)
        self.assertTrue(self.proc.slicer.manual_edits)

    def test_saved_slices_for_another_file_are_ignored(self):
        self.save(path="/other.wav", slices=make_slices((0, 400), (400, 1000)))
        self.engine.load_sample(self.proc, autoreset=False)
        self.assertEqual(self.proc.slicer.slices, [])

    def test_invalid_saved_data_is_ignored(self):
        for raw in ("", "not json", '{"slices": []}'):
            self.proc.controllers_dict["slice_data"].value = raw
            self.assertIsNone(self.engine._load_slice_data(self.proc))

    def test_empty_file_unloads_sample(self):
        self.proc.controllers_dict["file"].value = ""
        self.engine.load_sample(self.proc)
        self.assertEqual(self.lib.calls_named("unloadSample"), [("unloadSample", 0)])
        self.assertEqual((self.proc.slicer.file, self.proc.slicer.slices), ("", []))

    def test_export_sfz_reports_missing_slices(self):
        self.assertIsNone(self.engine.export_sfz(self.proc))
        self.assertEqual(self.engine.messages, ["SFZ export failed: no slices"])


@needs_engine
class TestEnginePlayers(unittest.TestCase):

    def setUp(self):
        self.engine = make_engine()
        self.lib = self.engine.libslicer
        self.engine.jackname = "zynslicer"

    def add(self, midi_chan):
        proc = FakeProcessor(self.engine, midi_chan)
        del proc.slicer
        proc.refresh_controllers = lambda: None
        self.engine.add_processor(proc)
        return proc

    def test_player_follows_requested_channel(self):
        proc = self.add(3)
        self.assertEqual((proc.slicer.channel, proc.midi_chan), (3, 3))
        self.assertEqual(proc.jackname, "zynslicer:out_04")

    def test_chain_follows_player_when_channel_is_taken(self):
        self.lib.players.add(3)  # e.g. used by another slicer chain
        proc = self.add(3)
        self.assertEqual((proc.slicer.channel, proc.midi_chan), (0, 0))

    def test_failed_channel_move_restores_working_player(self):
        proc = self.add(2)
        proc.controllers_dict["file"].value = ""
        self.lib.refuse_channels.add(5)
        self.lib.calls.clear()
        proc.set_midi_chan(5)
        self.assertEqual((proc.slicer.channel, proc.midi_chan), (2, 2))
        self.assertEqual(self.lib.calls_named("addPlayer"), [("addPlayer", 5), ("addPlayer", 2)])
        self.assertEqual(proc.jackname, "zynslicer:out_03")

    def test_monitors_belong_to_monitored_processor(self):
        proc_a = self.add(0)
        proc_b = self.add(1)
        proc_a.slicer.source_frames = proc_b.slicer.source_frames = 1000
        self.engine.apply_slices(proc_a, make_slices((0, 500), (500, 1000)))
        self.engine.apply_slices(proc_b, make_slices((0, 1000)))
        self.engine.set_monitored_processor(proc_a)
        self.assertEqual(len(self.engine.get_monitors_dict()["slices"]), 2)
        self.engine.set_monitored_processor(proc_b)
        self.assertEqual(len(self.engine.get_monitors_dict()["slices"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
