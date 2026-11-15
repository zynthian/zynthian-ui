# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_slicer)
#
# Slicer: splits an audio sample into slices played by consecutive MIDI notes.
# Playback runs in the zynslicer library (zynlibs/zynslicer), which has its
# own JACK client with one player per MIDI channel.
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
import json
import ctypes
import logging
from threading import Timer
from dataclasses import dataclass, field

import zynautoconnect
from zyngine import zynthian_slicer_sfz
from zyngine.zynthian_engine import zynthian_engine
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_slicer_analysis import (
    MAX_SLICES, PLAY_MODES, DEFAULT_PLAY_MODE, make_even_slices, detect_transients, normalize_slices)

# ------------------------------------------------------------------------------
# Constants (keep in sync with zynlibs/zynslicer/slicer.c and slicer.h)
# ------------------------------------------------------------------------------

MAX_VOICES = 16          # Simultaneous voices per slicer player
FADE_FRAMES = 64         # Voice fade-in/out length (SLICE_FADE_FRAMES)
# Player flags per play mode (SLICE_FLAG_GATE / SLICE_FLAG_LOOP)
PLAY_MODE_FLAGS = {"one-shot": 0x00, "gate": 0x01, "loop": 0x02}
MAX_FRAMES = 999999999   # Controller range while restoring state
NO_PLAYER = 255          # addPlayer() argument for "any free player", and its error result
MAX_TUNE = 24            # Tune range in semitones, up or down (slicer.h allows up to MAX_TUNE 48)

DEFAULT_BASE_NOTE = 36   # C2
SLICE_MODES = ("beats", "grid", "transient", "manual")
# Controllers that change how slices are calculated
ANALYSIS_SYMBOLS = {"slice_mode", "slice_count", "slice_beats", "slice_subdivision",
                    "threshold", "min_gap"}


@dataclass
class SlicerState:
    """Per-processor slicer state, stored as processor.slicer."""
    channel: int               # zynslicer player, equal to the MIDI channel
    file: str = ""             # Loaded sample path
    source_frames: int = 0     # Sample length in source-file frames
    slices: list = field(default_factory=list)  # Normalized slices
    manual_edits: bool = False  # True once slices were edited by hand
    audition_note: int = None  # Note auditioned from the widget, until released
    monitors: dict = field(default_factory=dict)  # Data for the audio-file widget


def _ctrl(name, **options):
    return dict(name=name, **options)


SLICER_CTRLS = [
    ["file", _ctrl("sample", is_path=True, path_file_types=["wav", "ogg", "mp3", "flac", "aac"])],
    ["gain", _ctrl("gain (dB)", value_min=-48.0, value_max=12.0, value=0.0)],
    # Tuning changes pitch and playback speed together (+12 = octave up, double speed)
    ["tune", _ctrl("tune", is_integer=True, value_min=-MAX_TUNE, value_max=MAX_TUNE, value=0)],
    ["base_note", _ctrl("base note", is_integer=True, value_min=1, value_max=127, value=DEFAULT_BASE_NOTE)],
    ["polyphony", _ctrl("polyphony", is_integer=True, value_min=1, value_max=MAX_VOICES, value=MAX_VOICES)],
    ["slice_mode", _ctrl("slice mode", is_integer=True, labels=list(SLICE_MODES),
                         ticks=list(range(len(SLICE_MODES))), value=0)],
    ["slice_count", _ctrl("grid slices", is_integer=True, value_min=1, value_max=MAX_SLICES, value=8)],
    ["slice_beats", _ctrl("beats", is_integer=True, value_min=1, value_max=64, value=4)],
    ["slice_subdivision", _ctrl("slices / beat", is_integer=True, value_min=1, value_max=16, value=1)],
    ["threshold", _ctrl("threshold", is_integer=True, value_min=0, value_max=100, value=50)],
    ["min_gap", _ctrl("min gap (ms)", is_integer=True, value_min=10, value_max=2000, value=50)],
    ["detect", _ctrl("detect", is_trigger=True, value_min=0, value_max=1, value=0)],
    ["slice", _ctrl("slice", is_integer=True, value_min=0, value_max=MAX_SLICES - 1, value=0)],
    ["slice_start", _ctrl("slice start", is_integer=True, value_min=0, value_max=MAX_FRAMES, value=0)],
    ["slice_end", _ctrl("slice end", is_integer=True, value_min=0, value_max=MAX_FRAMES, value=MAX_FRAMES)],
    ["play_mode", _ctrl("play mode", is_integer=True, labels=list(PLAY_MODES),
                        ticks=list(range(len(PLAY_MODES))), value=PLAY_MODES.index(DEFAULT_PLAY_MODE))],
    ["zoom", _ctrl("zoom", ticks=[1, 2, 4, 8, 16, 32, 64, 128],
                   labels=["x1", "x2", "x4", "x8", "x16", "x32", "x64", "x128"], value=1)],
    ["export_sfz", _ctrl("export SFZ", is_trigger=True, value_min=0, value_max=1, value=0)],
    # Hidden: slice list saved with snapshots (JSON)
    ["slice_data", _ctrl("slice data", is_path=True, value="")],
]

# The control screen shows up to four controllers per page
SLICER_CTRL_SCREENS = [
    ["Sample", ["file", "gain", "tune", "base_note"]],
    ["Slice", ["slice_mode", "slice_count", "slice_beats", "slice_subdivision"]],
    ["Detect", ["threshold", "min_gap", "detect"]],
    ["Edit", ["slice", "slice_start", "slice_end", "play_mode"]],
    ["View", ["zoom", "polyphony"]],
    ["Export", ["export_sfz"]],
]


class zynthian_engine_slicer(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.name = "Slicer"
        self.nickname = "SC"
        self.type = "MIDI Synth"

        self._ctrls = SLICER_CTRLS
        self._ctrl_screens = SLICER_CTRL_SCREENS
        self.custom_gui_fpath = self.ui_dir + "/zyngui/zynthian_widget_audio_file.py"

        self.samplerate = zynautoconnect.get_jackd_samplerate()
        self.monitored_proc = None
        self.reload_timers = {}
        self.libslicer = None
        self.start()

    def start(self):
        lib = ctypes.cdll.LoadLibrary(self.ui_dir + "/zynlibs/zynslicer/build/libzynslicer.so")
        c_u8, c_u32, c_float = ctypes.c_uint8, ctypes.c_uint32, ctypes.c_float
        lib.getJackname.restype = ctypes.c_char_p
        lib.addPlayer.argtypes = [c_u8]
        lib.addPlayer.restype = c_u8
        lib.removePlayer.argtypes = [c_u8]
        lib.getFileFrames.argtypes = [ctypes.c_char_p]
        lib.getFileFrames.restype = c_u32
        lib.setPolyphony.argtypes = [c_u8, c_u8]
        lib.loadSample.argtypes = [c_u8, ctypes.c_char_p, c_u32, c_u32, c_u8]
        lib.unloadSample.argtypes = [c_u8]
        lib.setSlice.argtypes = [c_u8, c_u8, c_u32, c_u32, c_float, c_u8]
        lib.setSliceTune.argtypes = [c_u8, c_u8, c_float]
        lib.clearSlices.argtypes = [c_u8]
        lib.auditionSlice.argtypes = [c_u8, c_u8, c_u8]
        lib.releaseSlice.argtypes = [c_u8, c_u8]
        lib.stopSlices.argtypes = [c_u8]
        lib.getSlicePlayheads.argtypes = [
            c_u8, ctypes.POINTER(c_u8), ctypes.POINTER(c_float), ctypes.POINTER(c_u32), c_u8]
        lib.getSlicePlayheads.restype = c_u8
        lib.init()
        self.libslicer = lib
        self.jackname = lib.getJackname().decode("utf-8")

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        for timer in self.reload_timers.values():
            timer.cancel()
        self.reload_timers = {}
        self.libslicer.end()

    # ---------------------------------------------------------------------------
    # Processor management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        channel = self._add_player(processor.midi_chan)
        if channel is None:
            logging.error(f"Can't allocate slicer player for MIDI channel {processor.midi_chan}")
            return
        processor.slicer = SlicerState(channel=channel)
        processor.jackname = self._get_player_jackname(channel)
        self.processors.append(processor)
        processor.refresh_controllers()
        self._follow_player_channel(processor)
        self._update_monitors(processor)

    def remove_processor(self, processor):
        self._cancel_reload_timer(processor)
        self.libslicer.removePlayer(processor.slicer.channel)
        if processor == self.monitored_proc:
            self.monitored_proc = None
        super().remove_processor(processor)

    def set_midi_chan(self, processor):
        """Move the player when the chain's MIDI channel changes."""
        state = getattr(processor, "slicer", None)
        new_chan = processor.midi_chan
        if state is None or not self._is_midi_chan(new_chan) or new_chan == state.channel:
            return
        old_chan = state.channel
        self.libslicer.removePlayer(old_chan)
        channel = self._add_player(new_chan)
        if channel is None:
            logging.error(f"Can't move slicer to MIDI channel {new_chan + 1}")
            channel = self._add_player(old_chan)  # Just freed, so it is available
        state.channel = channel
        processor.jackname = self._get_player_jackname(channel)
        # The new player is empty => reload sample and slices
        self.load_sample(processor, autoreset=False)
        self._follow_player_channel(processor)

    def _add_player(self, midi_chan):
        """Create a player, on midi_chan if free. Returns its channel or None."""
        requested = midi_chan if self._is_midi_chan(midi_chan) else NO_PLAYER
        channel = self.libslicer.addPlayer(requested)
        return channel if 0 <= channel < 16 else None

    def _follow_player_channel(self, processor):
        """Set the chain's MIDI channel to the player index.

        The C MIDI handler routes notes by MIDI channel, so they must match.
        When the requested channel was taken (e.g. by another slicer chain),
        the player was created on another channel and the chain follows it.
        """
        channel = processor.slicer.channel
        if processor.midi_chan == channel:
            return
        if processor.chain_id is not None:
            self.state_manager.chain_manager.set_midi_chan(processor.chain_id, channel)
        else:
            processor.set_midi_chan(channel)

    def _get_player_jackname(self, channel):
        return f"{self.jackname}:out_{channel + 1:02d}"

    @staticmethod
    def _is_midi_chan(midi_chan):
        return isinstance(midi_chan, int) and 0 <= midi_chan < 16

    # ---------------------------------------------------------------------------
    # Name & bank methods
    # ---------------------------------------------------------------------------

    def get_name(self, processor=None):
        state = getattr(processor, "slicer", None)
        if state is None:
            return self.name
        return f"{self.name} {state.channel + 1}"

    def get_path(self, processor=None):
        return self.get_name(processor)

    def get_bank_list(self, processor=None):
        return []

    # ---------------------------------------------------------------------------
    # State management
    # ---------------------------------------------------------------------------

    def set_state_pre(self, processor):
        # Allow any saved boundary value before the sample length is known
        for symbol in ("slice_start", "slice_end"):
            processor.controllers_dict[symbol].set_options({"value_max": MAX_FRAMES})

    def set_state_post(self, processor):
        self.load_sample(processor, autoreset=False)

    # ---------------------------------------------------------------------------
    # Controllers
    # ---------------------------------------------------------------------------

    def send_controller_value(self, zctrl):
        proc = zctrl.processor
        if getattr(proc, "slicer", None) is None:
            return
        symbol = zctrl.symbol
        try:
            if symbol in ANALYSIS_SYMBOLS:
                if self._can_auto_slice(proc):
                    self.detect_slices(proc)
                return
            match symbol:
                case "file":
                    self._start_reload_timer(proc)
                case "gain" | "tune":
                    for sl in proc.slicer.slices:
                        self._send_slice(proc, sl)
                    self._update_monitors(proc)
                case "base_note":
                    self.apply_slices(proc, proc.slicer.slices)
                case "polyphony":
                    self.libslicer.setPolyphony(proc.slicer.channel, int(zctrl.value))
                case "zoom":
                    self._update_monitors(proc)
                case "detect":
                    if zctrl.value:
                        self.detect_slices(proc)
                case "export_sfz":
                    if zctrl.value:
                        self.export_sfz(proc)
                case "slice":
                    self.select_slice(proc, int(zctrl.value))
                case "slice_start":
                    self.set_slice_boundary(proc, start=zctrl.value)
                case "slice_end":
                    self.set_slice_boundary(proc, end=zctrl.value)
                case "play_mode":
                    self.set_selected_slice_play_mode(proc, zctrl.value)
        except Exception as e:
            logging.error(f"Can't process slicer controller '{symbol}': {e}")

    def _ctrl_value(self, processor, symbol):
        return processor.controllers_dict[symbol].value

    def _set_ctrl_value(self, processor, symbol, value):
        """Update a controller without sending it back to the engine."""
        zctrl = processor.controllers_dict[symbol]
        if zctrl.value != value:
            zctrl.set_value(value, send=False)

    def _get_base_note(self, processor):
        return int(self._ctrl_value(processor, "base_note"))

    def _get_master_gain(self, processor):
        return 10.0 ** (float(self._ctrl_value(processor, "gain")) / 20.0)

    def _get_master_tune(self, processor):
        return max(-MAX_TUNE, min(int(self._ctrl_value(processor, "tune")), MAX_TUNE))

    def _get_selected_index(self, processor):
        slices = processor.slicer.slices
        if not slices:
            return 0
        return max(0, min(int(self._ctrl_value(processor, "slice")), len(slices) - 1))

    # ---------------------------------------------------------------------------
    # Sample loading
    # ---------------------------------------------------------------------------

    def load_sample(self, processor, autoreset=True):
        """Load the sample selected by the file controller.

        processor: Slicer processor
        autoreset: True to detect slices when no saved slices match the file
        """
        state = processor.slicer
        fpath = self._ctrl_value(processor, "file")
        if not fpath:
            self.libslicer.unloadSample(state.channel)
            state.file = ""
            state.source_frames = 0
            processor.preset_name = ""
            self.apply_slices(processor, [], manual_edits=False)
            return
        if not os.path.isfile(fpath):
            logging.warning(f"Slicer file not found: {fpath}")
            return
        frames = int(self.libslicer.getFileFrames(bytes(fpath, "utf-8")))
        if frames <= 0 or self.libslicer.loadSample(state.channel, bytes(fpath, "utf-8"), 0, frames, 4):
            logging.warning(f"Can't load slicer sample: {fpath}")
            return
        self.libslicer.setPolyphony(state.channel, int(self._ctrl_value(processor, "polyphony")))
        state.file = fpath
        state.source_frames = frames
        processor.preset_name = os.path.basename(fpath)
        for symbol in ("slice_start", "slice_end"):
            processor.controllers_dict[symbol].set_options({"value_max": frames})
        self._set_ctrl_value(processor, "zoom", 1)

        saved = self._load_slice_data(processor)
        if saved and saved.get("path") == fpath:
            # Saved slices from before the edit flag existed count as edited,
            # so changing analysis settings can't silently discard them.
            self.apply_slices(processor, saved["slices"], manual_edits=saved.get("manual_edits", True))
        elif autoreset:
            self.detect_slices(processor)
        else:
            self.apply_slices(processor, [], manual_edits=False)

    def _start_reload_timer(self, processor):
        """Load the sample shortly after the file changes (debounce)."""
        if processor.set_state_flag:
            return
        self._cancel_reload_timer(processor)
        timer = Timer(0.5, self._reload_timer_cb, args=(processor,))
        self.reload_timers[processor] = timer
        timer.start()

    def _cancel_reload_timer(self, processor):
        timer = self.reload_timers.pop(processor, None)
        if timer:
            timer.cancel()

    def _reload_timer_cb(self, processor):
        self.reload_timers.pop(processor, None)
        if not processor.set_state_flag:
            self.load_sample(processor)

    # ---------------------------------------------------------------------------
    # Slices
    # ---------------------------------------------------------------------------

    def _can_auto_slice(self, processor):
        """Return True if analysis changes may rebuild the slices.

        Only while the slices haven't been edited by hand, never in manual
        mode, and not while restoring state (the sample isn't loaded yet).
        """
        mode = SLICE_MODES[int(self._ctrl_value(processor, "slice_mode"))]
        return not (processor.set_state_flag or processor.slicer.manual_edits or mode == "manual")

    def detect_slices(self, processor):
        """Rebuild the slices from the sample using the current slice mode."""
        state = processor.slicer
        frames = state.source_frames
        if not state.file or frames <= 0:
            return
        mode = SLICE_MODES[int(self._ctrl_value(processor, "slice_mode"))]
        grid_count = self._ctrl_value(processor, "slice_count")
        if mode == "beats":
            beats = int(self._ctrl_value(processor, "slice_beats"))
            subdivision = int(self._ctrl_value(processor, "slice_subdivision"))
            slices = make_even_slices(frames, beats * subdivision)
        elif mode == "transient":
            slices = detect_transients(state.file, frames,
                                       self._ctrl_value(processor, "threshold"),
                                       self._ctrl_value(processor, "min_gap"))
            if len(slices) < 2:
                # No meaningful transients => fall back to a grid
                slices = make_even_slices(frames, grid_count)
        elif mode == "manual" and state.slices:
            # Keep the hand-edited slices (and their edit flag)
            self.apply_slices(processor, state.slices)
            return
        else:
            slices = make_even_slices(frames, grid_count)
        self.apply_slices(processor, slices, manual_edits=False)

    def apply_slices(self, processor, slices, manual_edits=None):
        """Normalize slices, send them to the player and save them.

        manual_edits: New value for the edit flag, or None to keep it
        """
        state = processor.slicer
        state.slices = normalize_slices(slices, state.source_frames, self._get_base_note(processor))
        if manual_edits is not None:
            state.manual_edits = manual_edits
        self.libslicer.clearSlices(state.channel)
        for sl in state.slices:
            self._send_slice(processor, sl)
        processor.controllers_dict["slice"].set_options(
            {"value_min": 0, "value_max": max(0, len(state.slices) - 1)})
        self._save_slice_data(processor)
        self.select_slice(processor, self._get_selected_index(processor))

    def select_slice(self, processor, index):
        """Select a slice for editing and show its settings."""
        slices = processor.slicer.slices
        if slices:
            index = max(0, min(int(index), len(slices) - 1))
            sl = slices[index]
            values = {"slice": index, "slice_start": sl["start"], "slice_end": sl["end"],
                      "play_mode": PLAY_MODES.index(sl["mode"])}
        else:
            values = {"slice": 0, "slice_start": 0, "slice_end": 0,
                      "play_mode": PLAY_MODES.index(DEFAULT_PLAY_MODE)}
        for symbol, value in values.items():
            self._set_ctrl_value(processor, symbol, value)
        self._update_monitors(processor)

    def set_slice_boundary(self, processor, start=None, end=None):
        """Move the selected slice's start or end.

        Slices stay contiguous: moving a start also moves the previous
        slice's end, and moving an end also moves the next slice's start.
        The first start and the last end can move freely within the sample.
        """
        slices = processor.slicer.slices
        if not slices:
            return
        frames = processor.slicer.source_frames
        index = self._get_selected_index(processor)
        sl = slices[index]
        changed = {index}
        if start is not None:
            min_start = slices[index - 1]["start"] + 1 if index > 0 else 0
            max_start = sl["end"] - 1
            if max_start >= min_start:
                sl["start"] = max(min_start, min(int(start), max_start))
                if index > 0:
                    slices[index - 1]["end"] = sl["start"]
                    changed.add(index - 1)
        if end is not None:
            min_end = sl["start"] + 1
            max_end = slices[index + 1]["end"] - 1 if index < len(slices) - 1 else frames
            if max_end >= min_end:
                sl["end"] = max(min_end, min(int(end), max_end))
                if index < len(slices) - 1:
                    slices[index + 1]["start"] = sl["end"]
                    changed.add(index + 1)
        for i in changed:
            self._send_slice(processor, slices[i])
        self._mark_edited(processor)
        self._set_ctrl_value(processor, "slice_start", sl["start"])
        self._set_ctrl_value(processor, "slice_end", sl["end"])

    def set_selected_slice_play_mode(self, processor, value):
        """Set the selected slice's play mode (index into PLAY_MODES)."""
        slices = processor.slicer.slices
        if not slices:
            return
        sl = slices[self._get_selected_index(processor)]
        sl["mode"] = PLAY_MODES[int(value)]
        self._send_slice(processor, sl)
        self._mark_edited(processor)

    def audition_selected_slice(self, processor):
        """Play the selected slice, as if its key was pressed."""
        slices = processor.slicer.slices
        if slices:
            self.release_audition(processor)
            note = slices[self._get_selected_index(processor)]["note"]
            self.libslicer.auditionSlice(processor.slicer.channel, note, 127)
            processor.slicer.audition_note = note

    def release_audition(self, processor):
        """Release the auditioned slice, as if its key was released."""
        state = processor.slicer
        if state.audition_note is not None:
            self.libslicer.releaseSlice(state.channel, state.audition_note)
            state.audition_note = None

    def _send_slice(self, processor, sl):
        """Send one slice to the player.

        Updating an existing slice doesn't stop its voices, and playing
        voices follow tuning changes immediately.
        """
        channel = processor.slicer.channel
        gain = sl["gain"] * self._get_master_gain(processor)
        flags = PLAY_MODE_FLAGS[sl["mode"]]
        self.libslicer.setSlice(channel, sl["note"], sl["start"], sl["end"],
                                ctypes.c_float(gain), flags)
        tune = self._get_master_tune(processor)
        self.libslicer.setSliceTune(channel, sl["note"], ctypes.c_float(tune))

    def _mark_edited(self, processor):
        """Record a manual edit: stop auto-slicing and save the slices."""
        processor.slicer.manual_edits = True
        self._save_slice_data(processor)
        self._update_monitors(processor)

    # ---------------------------------------------------------------------------
    # Persistence (hidden slice_data controller)
    # ---------------------------------------------------------------------------

    def _save_slice_data(self, processor):
        state = processor.slicer
        data = {
            "path": state.file,
            "manual_edits": state.manual_edits,
            "slices": state.slices,
        }
        self._set_ctrl_value(processor, "slice_data", json.dumps(data))

    def _load_slice_data(self, processor):
        """Return saved slice data, or None if missing or invalid."""
        try:
            raw = self._ctrl_value(processor, "slice_data")
            data = json.loads(raw) if raw else None
            if isinstance(data, dict) and data.get("slices"):
                return data
        except Exception as e:
            logging.warning(f"Can't decode slicer data: {e}")
        return None

    # ---------------------------------------------------------------------------
    # Monitors (audio-file widget)
    # ---------------------------------------------------------------------------

    def set_monitored_processor(self, processor):
        self.monitored_proc = processor

    def get_monitors_dict(self):
        processor = self.monitored_proc
        if getattr(processor, "slicer", None) is None:
            return {}
        self._update_playheads(processor)
        return processor.slicer.monitors

    def _update_monitors(self, processor):
        state = processor.slicer
        selected = self._get_selected_index(processor)
        state.monitors.update({
            "slices": [{"start": sl["start"], "end": sl["end"], "note": sl["note"],
                        "selected": i == selected}
                       for i, sl in enumerate(state.slices)],
            "base_note": self._get_base_note(processor),
            "gain": self._ctrl_value(processor, "gain"),
            "zoom": int(self._ctrl_value(processor, "zoom")),
        })

    def _update_playheads(self, processor):
        """Publish the playing slices and the latest voice's position."""
        state = processor.slicer
        notes = (ctypes.c_uint8 * MAX_VOICES)()
        progress = (ctypes.c_float * MAX_VOICES)()
        order = (ctypes.c_uint32 * MAX_VOICES)()
        count = self.libslicer.getSlicePlayheads(state.channel, notes, progress, order, MAX_VOICES)
        slices_by_note = {sl["note"]: sl for sl in state.slices}
        active_notes = []
        latest_frame = None
        latest_order = -1
        for i in range(count):
            sl = slices_by_note.get(notes[i])
            if sl is None:
                continue
            active_notes.append(notes[i])
            if order[i] > latest_order:
                latest_order = order[i]
                latest_frame = int(sl["start"] + progress[i] * (sl["end"] - sl["start"]))
        state.monitors["active_notes"] = active_notes
        state.monitors["playhead_frame"] = latest_frame

    # ---------------------------------------------------------------------------
    # SFZ export
    # ---------------------------------------------------------------------------

    def export_sfz(self, processor, output_dir=None):
        """Export the slices as an SFZ instrument in the user's sfizz banks.

        Returns: Path of the .sfz file, or None on failure
        """
        state = processor.slicer
        if not state.file or not state.slices:
            self._show_message("SFZ export failed: no slices")
            return None
        try:
            sfz_path = zynthian_slicer_sfz.export_sfz(
                state.file, state.slices,
                output_dir or os.path.join(self.my_data_dir, "soundfonts", "sfz"),
                gain_db=float(self._ctrl_value(processor, "gain")),
                tune=self._get_master_tune(processor),
                polyphony=int(self._ctrl_value(processor, "polyphony")),
                fade_seconds=FADE_FRAMES / float(self.samplerate or 48000))
        except Exception as e:
            logging.error(f"Can't export SFZ: {e}")
            self._show_message("SFZ export failed")
            return None
        logging.info(f"Exported slicer SFZ: {sfz_path}")
        self._show_message(f"SFZ exported: {os.path.basename(sfz_path)}")
        return sfz_path

    @staticmethod
    def _show_message(message):
        zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_SHOW_MESSAGE, message=message)

# ******************************************************************************
