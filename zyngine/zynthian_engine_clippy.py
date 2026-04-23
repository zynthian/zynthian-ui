# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_clippy)
#
# zynthian_engine implementation for clip launcher
#
# Copyright (C) 2015-2026 Brian Walton <brian@riban.co.uk>
#                         Fernando Moyano <jofemodo@zynthian.org>
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
import re
import ctypes
import logging
from threading import Timer
from collections import deque

from zynlibs.zynseq import zynseq
from zyngine.zynthian_engine import zynthian_engine
from zyngine.zynthian_signal_manager import zynsigman
from zyngine.zynthian_controller import zynthian_controller
import zynautoconnect


# ------------------------------------------------------------------------------
# Clippy Engine Class
# ------------------------------------------------------------------------------

MAX_BEATS = 128 # Maximum quantity of beats in a clip
MAX_DURATION = 30 # Maximum audio duration to warp, in seconds
MAX_STORAGE = 500 * 1000 * 1024 # Maximum storage for temporary files

class zynthian_engine_clippy(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.name = "Clip Launcher"
        self.nickname = "CL"
        self.type = "Audio Generator"
        self.options["replace"] = False

        self.zynseq = state_manager.zynseq
        self.libseq = self.zynseq.libseq

        self._ctrls = []
        self._ctrl_screens = []

        self.selected_proc = None
        self.selected_phrase = 0

        self.reload_timers = {}
        self.tempo_timer = None
        self.tempo_deque = deque()
        self.tempo_sum = 0
        self.last_tempo_change = self.zynseq.libseq.getTempo()

        self.samplerate = zynautoconnect.get_jackd_samplerate()

        self.monitors_dict = {}
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audio_file.py"

        self.libclippy =  None
        self.start()

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def start(self):
        self.libclippy = ctypes.cdll.LoadLibrary("/zynthian/zynthian-ui/zynlibs/zynclippy/build/libzynclippy.so")
        self.libclippy.init()
        self.libclippy.getGain.restype = ctypes.c_float
        self.libclippy.getJackname.restype = ctypes.c_char_p
        self.libclippy.getClipPath.restype = ctypes.c_char_p
        self.jackname = self.libclippy.getJackname().decode("utf-8")
        self.zynseq.clippy = self
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.start_tempo_timer)

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        self.zynseq.clippy = None
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynsigman.SS_SEQ_TEMPO, self.start_tempo_timer)
        self.libclippy.end()

    # ---------------------------------------------------------------------------
    # Phrase management => launcher & zynseq integration
    # ---------------------------------------------------------------------------

    def set_phrase(self, processor, phrase):
        """ Select the phrase for control, etc"""

        self.selected_proc = processor
        self.selected_phrase = phrase
        note = phrase + 1
        try:
            file_path = processor.controllers_dict[f"file {note}"].value
            if file_path:
                # Setup controllers screens
                self._ctrl_screens = [
                    ["Clip", [f"file {note}", f"crop_start {note}", f"crop_end {note}", f"zoom {note}"]],
                    ["Control", [f"gain {note}", f"warp {note}", f"beats {note}", f"mode {note}"]],
                    ["Recording", ["record"]]
                ]
                # Set monitor values (for widget)
                for symbol in ["zoom", "crop_start", "crop_end", "warp", "beats"]:
                    self.monitors_dict[symbol] = processor.controllers_dict[f"{symbol} {note}"].value
                # Set processor name for display
                processor.preset_name = file_path.split("/")[-1]
            else:
                self._ctrl_screens = [["Clip", [f"file {note}", "record"]]]
                self.monitors_dict = {}
                processor.preset_name = ""
        except:
            self._ctrl_screens = [["Clip", ["file"]]]
            self.monitors_dict = {}
            processor.preset_name = ""
        processor.init_ctrl_screens(force_refresh=True)

    """ Set play mode

        phrase - Index of phrase
        chan - MIDI channel
        mode - play mode [0=disabled, 1=loop, 2..25=play 1..24 times]
    """
    def set_mode(self, phrase, chan, mode):
        match mode:
            case 0:
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "repeat", 0)
            case 1:
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "mode", 0x01)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followAction", zynseq.FOLLOW_ACTION_RELATIVE)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followParam", 0)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "repeat", 1)
            case _:
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "mode", 0x01)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followAction", zynseq.FOLLOW_ACTION_NONE)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "followParam", 0)
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, chan, "repeat", mode - 1)

    def insert_phrase(self, phrase):
        """ Inserts a new empty phrase immediately before the indexed phrase

        phrase: Index of phrase to insert new phrase before
        """

        for processor in self.processors:
            self.libclippy.insertClip(processor.midi_chan - 16, phrase)
            for idx in range(self.zynseq.phrases, phrase, -1):
                try:
                    for symbol in ("file", "crop_start", "crop_end", "zoom", "gain", "warp", "beats", "mode"):
                        processor.controllers_dict[f"{symbol} {idx}"] = processor.controllers_dict[f"{symbol} {idx - 1}"]
                        processor.controllers_dict[f"{symbol} {idx}"].symbol = f"{symbol} {idx}"
                except:
                    pass # Ignore unpopulated phrases
            self.add_controllers(processor, phrase + 1)
            processor.controllers_dict[f"mode {idx}"].set_value(1)

    def remove_phrase(self, phrase):
        """ Remove a phrase

        phrase: Index of phrase to remove
        """

        for processor in self.processors:
            self.libclippy.removeClip(processor.midi_chan - 16, phrase)
            for idx in range(phrase + 1, self.zynseq.phrases + 1):
                try:
                    for symbol in ("file", "crop_start", "crop_end", "zoom", "gain", "warp", "beats", "mode"):
                        if idx < self.zynseq.phrases:
                            processor.controllers_dict[f"{symbol} {idx}"] = processor.controllers_dict[f"{symbol} {idx + 1}"]
                            processor.controllers_dict[f"{symbol} {idx}"].symbol = f"{symbol} {idx}"
                        else:
                            del processor.controllers_dict[f"{symbol} {idx}"]
                except:
                    pass # Ignore unpopulated phrases

    def duplicate_phrase(self, phrase):
        """ Duplicate a phrase
        Args:
            phrase: Index of phrase to duplicate
        """

        self.insert_phrase(phrase)
        for processor in self.processors:
            for symbol in ("file", "crop_start", "crop_end", "zoom", "gain", "warp", "beats", "mode"):
                try:
                    src_zctrl = processor.controllers_dict[f"{symbol} {phrase + 2}"]
                    dst_zctrl = processor.controllers_dict[f"{symbol} {phrase + 1}"]
                    dst_zctrl.set_value(src_zctrl.value)
                except:
                    pass


    def nudge_phrase(self, phrase, forward):
        """ Move a phrase forward or backward by one position
        Args:
            scene: Index of scene
            phrase: Index of phrase
            forward: True to move forward, else move backwards
        """

        for processor in self.processors:
            self.libclippy.nudgeClip(processor.midi_chan - 16, phrase, forward)
            phrase2 = phrase + 1 if forward else phrase - 1
            try:
                for symbol in ("file", "crop_start", "crop_end", "zoom", "gain", "warp", "beats", "mode"):
                    a = processor.controllers_dict[f"{symbol} {phrase + 1}"]
                    processor.controllers_dict[f"{symbol} {phrase + 1}"] = processor.controllers_dict[f"{symbol} {phrase2 + 1}"]
                    processor.controllers_dict[f"{symbol} {phrase2 + 1}"] = a
                    processor.controllers_dict[f"{symbol} {phrase + 1}"].symbol = f"{symbol} {phrase2 + 1}"
                    processor.controllers_dict[f"{symbol} {phrase + 2}"].symbol = f"{symbol} {phrase2 + 1}"
            except:
                pass # Ignore unpopulated phrases

    # ---------------------------------------------------------------
    # Sample loading, cropping & warping
    # ---------------------------------------------------------------

    def set_file(self, processor, phrase, autoreset=True):
        """ Loads a file into a clip. SRC and warp to new file if necessary

        processor: Clippy processor
        phrase: Phrase index
        autoreset: True to allow resetting crop parameters when loading a new file
        """

        note = phrase + 1
        file_zctrl = processor.controllers_dict[f"file {note}"]
        path = file_zctrl.value
        if path:
            clip_channel = processor.midi_chan - 16
            warp_zctrl = processor.controllers_dict[f"warp {note}"]
            beats_zctrl = processor.controllers_dict[f"beats {note}"]
            crop_start_zctrl = processor.controllers_dict[f"crop_start {note}"]
            crop_end_zctrl = processor.controllers_dict[f"crop_end {note}"]

            quality = 4     # Re-sampling quality (1-4)
            sr = self.libclippy.getFileSamplerate(bytes(path, "utf-8"))
            frames = self.libclippy.getFileFrames(bytes(path, "utf-8"))
            self.update_controllers(processor, note, frames)

            # Try to determine playing tempo
            tempo = self.zynseq.get_sequence_param(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, "tempo")
            if not tempo:
                tempo = self.zynseq.libseq.getTempo()
                tempo_lock = False
            else:
                tempo_lock = True

            # Try to determine sample tempo from filename
            filename = os.path.basename(path)
            regptn = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(regptn, filename)
            try:
                file_tempo = float(matches[0])
            except:
                file_tempo = tempo

            # Configure clip with required beats to play whole file at this tempo
            try:
                reset = False
                if autoreset:
                    current_path = self.libclippy.getClipPath(clip_channel, phrase)
                    if not current_path or current_path.decode("utf-8") != path:
                        reset = True
                if reset:
                    beats_zctrl.value = 0
                    warp_zctrl.value = 1
                    crop_start_zctrl.value = 0
                    crop_end_zctrl.value = frames
                    min_duration = (60 / file_tempo)
                else:
                    min_duration = (15 / file_tempo)

                beats_value = beats_zctrl.value
                warp_value = warp_zctrl.value
                crop_start = crop_start_zctrl.value
                crop_end = crop_end_zctrl.value

                duration = (crop_end - crop_start) / sr
                beats_per_bar = self.zynseq.get_sequence_param(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, "bpb")
                if beats_per_bar < 1:
                    beats_per_bar = self.zynseq.bpb
                beats = duration * file_tempo / 60
                bars = round(beats / beats_per_bar)

                if beats_value:
                    whole_beats = beats_value
                else:
                    #whole_beats = bars * beats_per_bar
                    whole_beats = int(round(beats))
                    if whole_beats < 1:
                        whole_beats = 1
                    beats_zctrl.value = whole_beats

                if whole_beats <= MAX_BEATS and min_duration <= duration <= MAX_DURATION:
                    can_warp = True
                else:
                    can_warp = False
                    warp_zctrl.value = 0

                if not warp_zctrl.value:
                    tempo = 0.0

                #logging.debug(f"LOAD SAMPLE ({whole_beats} BEATS): [{crop_start} - {crop_end}] {tempo}BPM => {path}")
                # Setup clippy note
                new_note = self.libclippy.loadClip(clip_channel, note, bytes(path, "utf-8"), whole_beats,
                                                   crop_start, crop_end, quality, ctypes.c_float(tempo), tempo_lock)
                if new_note == 0:
                    logging.warning(f"Can't load/process sample file!")
                elif note != new_note:
                    logging.warning(f"Wrong note assigned ({note}!={new_note})!")

                # Setup zynseq sequence
                self.libseq.setSequenceLength(self.zynseq.scene, phrase, processor.midi_chan, whole_beats * self.zynseq.PPQN)
                self.set_mode(phrase, processor.midi_chan, 1) # Default repeat
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", os.path.splitext(filename)[0])
                self.libseq.updateSequenceInfo()

                #zctrl_crop_end.value_max = zctrl_crop_end.value_range = self.libclippy.getFileFrames(bytes(dst_path, "utf-8"))

                # Refresh UI
                if phrase == self.selected_phrase:
                    self.set_phrase(processor, phrase)
                #else:
                    # Used for display purpose only
                    #processor.preset_name = path.split("/")[-1]

            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {note} => {e}")
        else:
            self.libseq.setPlayState(self.zynseq.scene, phrase, processor.midi_chan, zynseq.SEQ_STOPPED)
            #self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 1)
            self.set_mode(phrase, processor.midi_chan, 1)
            self.libseq.updateSequenceInfo()
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", "")
            self.libclippy.unloadClip(processor.midi_chan - 16, note)
            if phrase == self.selected_phrase:
                self._ctrl_screens = [["Clip", [f"file {note}", "record"]]]
                processor.preset_name = ""
                processor.init_ctrl_screens(force_refresh=True)

    # ---------------------------------------------------------------
    # Callbacks to re-warp sample file when needed (on-the-fly)
    # ---------------------------------------------------------------

    def start_reload_timer(self, processor, phrase):
        if processor.set_state_flag:
            return
        try:
            self.reload_timers[(processor, phrase)].cancel()
            self.reload_timers.pop((processor, phrase), None)
        except:
            pass
        reload_timer = Timer(0.5, self.reload_timer_cb, args=(processor, phrase))
        self.reload_timers[(processor, phrase)] = reload_timer
        reload_timer.start()

    def reload_timer_cb(self, processor, phrase):
        try:
            self.reload_timers[(processor, phrase)].cancel()
        except:
            pass
        if not processor.set_state_flag:
            self.set_file(processor, phrase)
        self.reload_timers.pop((processor, phrase), None)

    def start_tempo_timer(self, tempo=None):
        # When synced to external clock => add some hysteresis to avoid spurious rewarping: +-3%
        if zynautoconnect.get_ext_clock_zmip() >= 0:
            # Calculate tempo average
            self.tempo_deque.append(tempo)
            self.tempo_sum += tempo
            if len(self.tempo_deque) > 10:
                self.tempo_sum -= self.tempo_deque.popleft()
            else:
                return
            tempo_avg = self.tempo_sum / len(self.tempo_deque)
            tempo_delta = abs(self.last_tempo_change - tempo_avg) / self.last_tempo_change
            #logging.debug(f"TEMPO AVG = {tempo_avg}, TEMPO DELTA = {tempo_delta}")
            if tempo_delta < 0.03:
                return
            self.last_tempo_change = tempo_avg
        else:
            self.last_tempo_change = tempo

        if self.tempo_timer:
            self.tempo_timer.cancel()
        self.tempo_timer = Timer(0.5, self.tempo_timer_cb)
        self.tempo_timer.start()
        # Silence (IDLE) players that need to rewarp:
        self.libclippy.idlePlayers()

    def tempo_timer_cb(self):
        if self.tempo_timer:
            self.tempo_timer.cancel()
        self.libclippy.changeTempo(ctypes.c_float(self.last_tempo_change))
        self.tempo_timer = None

    def rewarp_phrase(self, phrase):
        for proc in self.processors:
            try:
                if proc.controllers_dict[f"warp {phrase + 1}"].get_value():
                    self.set_file(proc, phrase)
            except:
                continue

    def tempo_average():

        d = deque(itertools.islice(it, n-1))
        d.appendleft(0)
        s = sum(d)
        for elem in it:
            s += elem - d.popleft()
            d.append(elem)
            yield s / n

    # ---------------------------------------------------------------
    # Controller management
    # ---------------------------------------------------------------

    def add_record_controller(self, processor):
        zctrls = {
            "record": zynthian_controller(self, "record", {
                    "name": "record",
                    "processor": processor,
                    "is_toggle": True,
                    "labels": ["stopped", "recording"],
                    "ticks": [0, 1],
                    "value": "stopped"
                })
        }
        processor.controllers_dict.update(zctrls)

    def add_controllers(self, processor, note):
        """ Adds controllers to processor

            processor: Clippy processor object
            note: MIDI note (clip id)
        """

        # Add default controllers for each phrase
        zctrls = {
            f"file {note}": zynthian_controller(self, f"file {note}", {
                    "name": "file",
                    "processor": processor,
                    "is_path": True,
                    "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"]
                }),
            f"warp {note}": zynthian_controller(self, f"warp {note}", {
                    "name": "warp",
                    "processor": processor,
                    "is_toggle": True,
                    "labels": ["off", "on"],
                    "ticks": [0, 1],
                    "value": "on"
                }),
            f"beats {note}": zynthian_controller(self, f"beats {note}", {
                    "name": "beats",
                    "processor": processor,
                    "is_integer": True,
                    "value": 1,
                    "value_min": 1,
                    "value_max": MAX_BEATS
                }),
            f"mode {note}": zynthian_controller(self, f"mode {note}", {
                    "name": "mode",
                    "processor": processor,
                    "is_integer": True,
                    "labels": ["disabled", "loop"] + [f"play {i}" for i in range(1, 25)],
                    "value_min": 0,
                    "value_max": 25,
                    "value": 1
                }),
            f"gain {note}": zynthian_controller(self, f"gain {note}", {
                    "name": "gain (dB)",
                    "processor": processor,
                    "value_min": -12.0,
                    "value_max": 6.0,
                    "value": 0.0
                }),
            f"crop_start {note}": zynthian_controller(self, f"crop_start {note}", {
                    "name": "crop start",
                    "processor": processor,
                    "is_integer": True,
                    "value_max": 999999999,
                    "value": 0
                }),
            f"crop_end {note}": zynthian_controller(self, f"crop_end {note}", {
                    "name": "crop end",
                    "processor": processor,
                    "is_integer": True,
                    "value_max": 999999999,
                    "value": 999999999
                }),
            f"zoom {note}": zynthian_controller(self, f"zoom {note}", {
                    "name": "zoom",
                    "processor": processor,
                    "ticks": [1, 2, 4, 8, 16, 32, 64, 128, 256],
                    "labels": ["x1", "x2", "x4", "x8", "x16", "x32", "x64", "x128", "x256"]
                })
        }
        processor.controllers_dict.update(zctrls)

    def update_controllers(self, processor, note, frames=100, reset=False):
        crop_start_options = {"value_max": frames}
        crop_end_options =  {"value_max": frames}
        if reset:
            crop_start_options["value"] = 0
            crop_end_options["value"] = frames
        processor.controllers_dict[f"crop_start {note}"].set_options(crop_start_options)
        processor.controllers_dict[f"crop_end {note}"].set_options(crop_end_options)
        ticks = []
        labels = []
        i = 0
        while True:
            val = 2 ** i
            if val > frames / 40:
                break
            ticks.append(val)
            labels.append(f"x{ticks[i]}")
            i += 1
        processor.controllers_dict[f"zoom {note}"].set_options({
            "ticks": ticks,
            "labels": labels
        })
        self.update_nudge(processor, note)

    def update_nudge(self, processor, note):
        zctrl_crop_start = processor.controllers_dict[f"crop_start {note}"]
        zctrl_crop_end = processor.controllers_dict[f"crop_end {note}"]
        zctrl_zoom = processor.controllers_dict[f"zoom {note}"]
        frames = zctrl_crop_end.value_max
        zoom_val = zctrl_zoom.value
        nudge_factor = frames // (100 * zoom_val)
        if nudge_factor < 1:
            nudge_factor = 1
        nudge_factor_fine = nudge_factor // 100
        if nudge_factor_fine < 1:
            nudge_factor_fine = 1
        zctrl_crop_start.nudge_factor = nudge_factor
        zctrl_crop_start.nudge_factor_fine = nudge_factor_fine
        zctrl_crop_end.nudge_factor = nudge_factor
        zctrl_crop_end.nudge_factor_fine = nudge_factor_fine

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "record":
            if zctrl.value:
                self.state_manager.audio_recorder.start_recording()
            else:
                self.state_manager.audio_recorder.stop_recording()
            return

        proc = zctrl.processor
        try:
            symparts = zctrl.symbol.split(" ")
            symbol = symparts[0]
            note = int(symparts[1])
            phrase = note - 1
        except Exception as e:
            logging.error(f"Can't determine sample index for '{zctrl.symbol}' => {e}")
            return

        #logging.debug(f"ZCTRL {symbol}, {note} => {zctrl.value}")
        match symbol:
            case "file":
                self.start_reload_timer(proc, phrase)
            case "warp":
                self.monitors_dict["warp"] = zctrl.value
                self.start_reload_timer(zctrl.processor, phrase)
            case "mode":
                self.set_mode(phrase, zctrl.processor.midi_chan, zctrl.value)
            case "crop_start":
                zctrl_crop_end = zctrl.processor.controllers_dict[f"crop_end {note}"]
                if zctrl.value >= zctrl_crop_end.value:
                    zctrl.set_value(zctrl.crop_end.value - 1)
                    return
                self.monitors_dict["crop_start"] = zctrl.value

                self.start_reload_timer(zctrl.processor, phrase)
                return
            case "crop_end":
                zctrl_crop_start = zctrl.processor.controllers_dict[f"crop_start {note}"]
                if zctrl.value <= zctrl_crop_start.value:
                    zctrl.set_value(zctrl_crop_start.value + 1)
                    return
                self.monitors_dict["crop_end"] = zctrl.value
                self.start_reload_timer(zctrl.processor, phrase)
                return
            case "beats":
                zctrl_warp = zctrl.processor.controllers_dict[f"warp {note}"]
                self.monitors_dict["beats"] = zctrl.value
                if zctrl_warp.value == 0:
                    self.libseq.setSequenceLength(self.zynseq.scene, phrase, proc.midi_chan, zctrl.value * self.zynseq.PPQN)
                    self.libseq.updateSequenceInfo()
                else:
                    self.start_reload_timer(zctrl.processor, phrase)
            case "gain":
                try:
                    self.libclippy.setGain(zctrl.processor.midi_chan - 16, phrase, ctypes.c_float(zctrl.value))
                except Exception as e:
                    logging.warning(e)
                return
            case "zoom":
                self.update_nudge(zctrl.processor, note)
                self.monitors_dict["zoom"] = zctrl.value
                return

    def set_state_pre(self, processor):
        # Set crop and zoom limits to big-enough values so it can receive the new state values
        note = 1
        while True:
            try:
                crop_start_zctrl = processor.controllers_dict[f"crop_start {note}"]
                crop_end_zctrl = processor.controllers_dict[f"crop_end {note}"]
                zoom_zctrl = processor.controllers_dict[f"zoom {note}"]
            except:
                break
            crop_start_options = {"value_max": 999999999}
            crop_end_options =  {"value_max": 999999999}
            crop_start_zctrl.set_options(crop_start_options)
            crop_end_zctrl.set_options(crop_end_options)
            zoom_options = {
                "ticks": [1, 2, 4, 8, 16, 32, 64, 128, 256],
                "labels": ["x1", "x2", "x4", "x8", "x16", "x32", "x64", "x128", "x256"]
            }
            zoom_zctrl.set_options(zoom_options)
            note += 1

    def set_state_post(self, processor):
        note = 1
        while True:
            try:
                file_zctrl = processor.controllers_dict[f"file {note}"]
            except:
                break
            phrase = note - 1
            self.set_file(processor, phrase, autoreset=False)
            note += 1
        self.last_tempo_change = self.zynseq.libseq.getTempo()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        """
            Add a processor (clip player channel)

            processor: zynthian_processor object
        """

        if processor.midi_chan is None:
            midi_chan = self.libclippy.addPlayer(255)
        else:
            midi_chan = self.libclippy.addPlayer(processor.midi_chan)
        if midi_chan > 15:
            return
        #processor.midi_chan = midi_chan + 16
        self.processors.append(processor)
        self.state_manager.chain_manager.set_midi_chan(processor.chain_id, midi_chan + 16)
        processor.jackname = f"{self.jackname}:out_{midi_chan + 1 :02d}"

        self.add_record_controller(processor)
        self.zynseq.enable_channel(processor.midi_chan, True)
        for phrase in range(self.zynseq.phrases):
            note = phrase + 1
            self.add_controllers(processor, note)
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 1)
        self.set_phrase(processor, self.zynseq.phrase)

    def remove_processor(self, processor):
        self.zynseq.enable_channel(processor.midi_chan, False)
        if self.libclippy.removePlayer(processor.midi_chan - 16) != 0:
            return
        for phrase in range(self.zynseq.phrases):
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", "")
            self.set_mode(phrase, processor.midi_chan, 1)
        super().remove_processor(processor)


    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return []

    #def set_bank(self, processor, bank):
    #    return True

    # ---------------------------------------------------------------------------
    # Preset Management
    # ---------------------------------------------------------------------------

    #def get_preset_list(self, bank, processor=None):
    #    return []

    #def set_preset(self, processor, preset, preload=False):
    #    return False

    # ---------------------------------------------------------------------------
    # Name & path methods
    # ---------------------------------------------------------------------------

    def get_name(self, processor=None):
        name = self.name
        if not processor:
            processor = self.selected_proc
        if processor:
            name += f" {processor.midi_chan - 15}"
        return name

    def get_path(self, processor=None):
        return self.get_name(processor) + f"/{self.selected_phrase + 1}"

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------


# ******************************************************************************
