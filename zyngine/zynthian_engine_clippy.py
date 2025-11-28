# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Engine (zynthian_engine_clippy)
#
# zynthian_engine implementation for clip launcher
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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
import logging
import re
from threading import Timer
import ctypes
from time import sleep

from zynlibs.zynseq import zynseq
from zyngine.zynthian_signal_manager import zynsigman

from . import zynthian_engine
from . import zynthian_controller

import zynautoconnect


# ------------------------------------------------------------------------------
# Clippy Engine Class
# ------------------------------------------------------------------------------

MAX_BEATS = 64 # Maximum quantity of beats in a pattern
MAX_DURATION = 30 # Maximum audio duration to warp, in seconds
MAX_STORAGE = 500 * 1000 * 1024 # Maximum storage for temporary files

class zynthian_engine_clippy(zynthian_engine):

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.zynseq = state_manager.zynseq
        self.libseq = self.zynseq.libseq
        self.libclippy = ctypes.cdll.LoadLibrary("/zynthian/zynthian-ui/zynlibs/zynclippy/build/libzynclippy.so")
        self.libclippy.init()
        self.libclippy.getGain.restype = ctypes.c_float
        self.libclippy.getJackname.restype = ctypes.c_char_p

        self.name = "Clippy"
        self.nickname = "CL"
        self.type = "Audio Generator"
        self.options["replace"] = False

        self.jackname = self.libclippy.getJackname().decode("utf-8")
        self._ctrls = []
        self._ctrl_screens = []

        self.selected_proc = None
        self.selected_phrase = None
        self.selected_note = None

        self.tempo_timer = None
        self.crop_timer = None
        self.tempo_mutex = False
        self.crop_cb_timer = None
        self.samplerate = zynautoconnect.get_jackd_samplerate()
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_tempo_timer)

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_tempo_timer)
        self.libclippy.end()

    def set_phrase(self, processor, phrase):
        """ Select the phrase for control, etc"""

        self.selected_proc = processor
        self.selected_phrase = phrase
        self.monitors_dict = {}
        try:
            pattern = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
            note = self.selected_note = self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]
            if note == 0xff:
                return
            self._ctrl_screens = [
                ["Clip", [f"file {note}", f"crop_start {note}", f"crop_end {note}", f"zoom {note}"]],
                ["Control", [f"gain {note}", f"warp {note}", f"beats {note}", f"mode {note}"]]
                ]
            # Set processor name for display
            processor.preset_name = processor.controllers_dict[f"file {note}"].value.split("/")[-1]
            for symbol in ["zoom", "crop_start", "crop_end"]:
                self.monitors_dict[symbol] = processor.controllers_dict[f"{symbol} {note}"].value
        except:
            self._ctrl_screens = [["Clip", ["file"]]]
            processor.preset_name = ""
            self.selected_note = 0
        processor.init_ctrl_screens()

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "file":
            # Empty clip
            self.set_file(self.selected_proc, 0, True)
            return
        try:
            note = int(zctrl.symbol.split(" ")[1])
            #beats_zctrl = zctrl.processor.controllers_dict[f"beats {note}"]
            #mode_zctrl = zctrl.processor.controllers_dict[f"mode {note}"]
        except Exception as e:
            logging.error(f"Can't determine sample index {zctrl.symbol} => {e}")
            return
        if zctrl.symbol.startswith("file"):
            self.set_file(zctrl.processor, note, True)
        elif zctrl.symbol.startswith("warp"):
            self.set_file(zctrl.processor, note)
        elif zctrl.symbol.startswith("mode"):
            self.set_mode(note - 1, zctrl.processor.midi_chan, zctrl.value)
        elif zctrl.symbol.startswith("crop_start"):
            zctrl_crop_end = zctrl.processor.controllers_dict[zctrl.symbol.replace("start", "end")]
            zctrl_crop_end.value_min = zctrl.value
            zctrl_crop_end.value_range = zctrl_crop_end.value_max - zctrl_crop_end.value_min
            self.monitors_dict["crop_start"] = zctrl.value
            self.start_crop_timer(zctrl.processor, note)
            return
        elif zctrl.symbol.startswith("crop_end"):
            zctrl_crop_start = zctrl.processor.controllers_dict[zctrl.symbol.replace("end", "start")]
            zctrl_crop_start.value_max = zctrl.value
            zctrl_crop_start.value_range = zctrl_crop_start.value
            self.monitors_dict["crop_end"] = zctrl.value
            self.start_crop_timer(zctrl.processor, note)
            return
        elif zctrl.symbol.startswith("gain"):
            try:
                self.libclippy.setGain(zctrl.processor.midi_chan - 16, note - 1, ctypes.c_float(zctrl.value))
            except Exception as e:
                logging.warning(e)
            return
        elif zctrl.symbol.startswith("zoom"):
            self.update_nudge(zctrl.processor, note)
            self.monitors_dict["zoom"] = zctrl.value
            return

    def update_nudge(self, processor, note):
        zctrl_crop_start = processor.controllers_dict[f"crop_start {note}"]
        zctrl_crop_end = processor.controllers_dict[f"crop_end {note}"]
        zctrl_zoom = processor.controllers_dict[f"zoom {note}"]
        frames = zctrl_crop_end.value_max
        nudge_factor = max(1, frames // (zctrl_zoom.value * 100))
        zctrl_crop_start.nudge_factor = nudge_factor
        zctrl_crop_end.nudge_factor = nudge_factor

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

    def set_file(self, processor, note, reset=False, phrase=None):
        """ Loads a file into a clip. SRC and warp to new file if necessary."""

        if note == 0:
            # No clip loaded
            note = self.libclippy.getFreeClip(processor.midi_chan - 16)
            path = processor.controllers_dict["file"].value
            processor.controllers_dict["file"].value = ""
            beats_value = 0
            warp_value = True
        else:
            path = processor.controllers_dict[f"file {note}"].value
        orig_path = path

        # Find what phrase this note is in...
        if phrase is None:
            phrase = self.selected_phrase
            for phrase_id, phrase_state in enumerate(self.zynseq.state["scenes"][self.zynseq.scene]["phrases"]):
                try:
                    pattern = phrase_state["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
                    if note == self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]:
                        phrase = phrase_id
                        break
                except:
                    pass

        if 0 < note > 127:
            return

        pattern = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
        self.libseq.selectPattern(pattern)
        self.libseq.clearPattern(pattern)
        if path:
            sr = self.libclippy.getFileSamplerate(bytes(path, "utf-8"))
            frames = self.libclippy.getFileFrames(bytes(path, "utf-8"))
            ratio = 1.0
            write_file = (sr != self.samplerate)
            processor.preset_name = path.split("/")[-1] # Used for display purpose only

            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["tempo"]
            if not tempo:
                tempo = self.zynseq.libseq.getTempo()
            regptn = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(regptn, filename)
            try:
                file_tempo = float(matches[0])
            except:
                file_tempo = tempo

            # Configure pattern with required beats to play whole file at this tempo
            try:
                if f"warp {note}" in processor.controllers_dict:
                    warp_zctrl = processor.controllers_dict[f"warp {note}"]
                    beats_zctrl = processor.controllers_dict[f"beats {note}"]
                    mode_zctrl = processor.controllers_dict[f"mode {note}"]
                    beats_value = beats_zctrl.value
                    warp_value = warp_zctrl.value
                    crop_start = processor.controllers_dict[f"crop_start {note}"].value
                    crop_end = processor.controllers_dict[f"crop_end {note}"].value
                else:
                    beats_value = 0
                    warp_value = 1
                    crop_start = 0
                    crop_end = frames

                duration = (crop_end - crop_start) / sr
                beats_per_bar = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sig"]
                if beats_per_bar < 1:
                    beats_per_bar = self.zynseq.libseq.getTimeSig()
                beats = duration * file_tempo / 60
                bars = round(beats / beats_per_bar)

                if beats_value:
                    whole_beats = beats_value
                else:
                    whole_beats = bars * beats_per_bar
                can_warp = whole_beats <= MAX_BEATS and duration <= MAX_DURATION
                factor = (whole_beats * file_tempo) / (beats * tempo)

                # File BPM matches current BPM
                if abs(factor - 1.0) < 0.0001:
                    bpm_match = True
                else:
                    bpm_match = False

                if warp_value and not bpm_match and can_warp:
                    # Warp audio to fit pattern length, only if short enough to avoid slow warp
                    ratio = factor
                    write_file = True

                dst_path = f"/tmp/clippy_{processor.midi_chan}_{note}.wav"
                if write_file and self.libclippy.copyFile(bytes(path, "utf-8"), bytes(dst_path, "utf-8"), 2, ctypes.c_float(ratio), crop_start, crop_end) == 0:
                    path = dst_path
                    #zctrl_crop_end.value_max = zctrl_crop_end.value_range = self.libclippy.getFileFrames(bytes(dst_path, "utf-8"))
                else:
                    try:
                        os.remove(dst_path)
                        #zctrl_crop_end.value_max = zctrl_crop_end.value_range = data.shape[0]
                    except:
                        pass
                if f"beats {note}" in processor.controllers_dict:
                    if can_warp:
                        beats_zctrl.value = whole_beats
                        beats_zctrl.set_readonly(warp_zctrl.value != 0)
                    else:
                        beats_zctrl.value = 0
                        warp_zctrl.value = 0

                # Setup zynseq pattern & sequence
                self.libseq.setStepsPerBeat(1)
                new_note = self.libclippy.loadClip(processor.midi_chan - 16, note, bytes(path, "utf-8"))
                if note != new_note:
                    logging.warning("Clippy error - wrong note assigned!")
                self.libseq.addNote(0, note, 100, 1, 0.0)
                self.zynseq.refresh_state()
                self.add_controllers(processor, note, frames, reset)
                processor.controllers_dict[f"file {note}"].value = orig_path
                processor.controllers_dict[f"file {note}"].path = path
                self.libseq.setBeatsInPattern(pattern, whole_beats)
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", os.path.splitext(filename)[0])
                self.set_mode(phrase, processor.midi_chan, 1) # Default repeat
                if phrase == self.selected_phrase:
                    self.set_phrase(processor, phrase)

            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {pattern} => {e}")
        else:
            self.libseq.setPlayState(self.zynseq.scene, phrase, processor.midi_chan, zynseq.SEQ_STOPPED)
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 0)
            self.libseq.updateSequenceInfo()
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", "")
            self.libclippy.unloadClip(processor.midi_chan - 16, note)
            for symbol in ("file", "warp", "beats", "mode", "gain", "crop_start", "crop_end", "zoom"):
                try:
                    del(processor.controllers_dict[f"{symbol} {note}"])
                except:
                    pass
            self._ctrl_screens = [["Clip", ["file"]]]

        processor.init_ctrl_screens()

    def start_crop_timer(self, processor, note):
        #TODO: This can cause a lot of file writing
        if self.crop_timer:
            self.crop_timer.cancel()
        self.crop_timer = Timer(0.5, self.crop_timer_cb, args=(processor, note))
        self.crop_timer.start()

    def crop_timer_cb(self, processor, note):
        if self.crop_timer:
            self.crop_timer.cancel()
        self.crop_timer = None
        self.set_file(processor, note)

    def start_tempo_timer(self, tempo=None):
        #TODO: This crashes with double free at high tempo
        if self.tempo_timer:
            self.tempo_timer.cancel()
        self.tempo_timer = Timer(0.5, self.tempo_timer_cb)
        self.tempo_timer.start()

    def tempo_timer_cb(self):
        if self.tempo_timer:
            self.tempo_timer.cancel()
        self.tempo_timer = None
        while self.tempo_mutex:
            sleep(0.001)
        self.tempo_mutex = True

        notes = []
        for phrase_state in self.zynseq.state["scenes"][self.zynseq.scene]["phrases"]:
            if phrase_state["tempo"]:
                continue
            for sequence in range(16, 32):
                try:
                    seq_state = phrase_state["sequences"][sequence]
                    pattern = seq_state["tracks"][0]["patns"]["0"]
                    note = self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]
                    if note not in notes:
                        notes.append(note)
                except:
                    continue

        for processor in self.processors:
            for note in notes:
                symbol = f"warp {note}"
                try:
                    if processor.controllers_dict.get(symbol).value:
                        self.set_file(processor, note)
                except:
                    continue
        self.tempo_mutex = False

    def add_controllers(self, processor, note, frames, reset):
        """ Adds a controllers to processor

            processor: Clippy processor object
            note: MIDI note (clip id)
            frames: Quantity of frames in file
        """

        # Add default controllers for each phrase
        zctrls = {}
        if f"file {note}" not in processor.controllers_dict:
            zctrls[f"file {note}"] = zynthian_controller(self, f"file {note}", {
                    "name": "file",
                    "processor": processor,
                    "is_path": True,
                    "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
            })
        if f"warp {note}" not in processor.controllers_dict:
            zctrls[f"warp {note}"] = zynthian_controller(self, f"warp {note}", {
                    "name": "warp",
                    "processor": processor,
                    "is_toggle": True,
                    "labels": ["off", "on"],
                    "value": "on"
            })
        if f"beats {note}" not in processor.controllers_dict:
            zctrls[f"beats {note}"] = zynthian_controller(self, f"beats {note}", {
                "name": "beats",
                "processor": processor,
                "is_integer": True,
                "value": 0,
                "value_min": 0,
                "value_max": MAX_BEATS
            })
        if f"mode {note}" not in processor.controllers_dict:
            zctrls[f"mode {note}"] = zynthian_controller(self, f"mode {note}", {
                "name": "mode",
                "processor": processor,
                "is_integer": True,
                "labels": ["disabled", "loop"] + [f"play {i}" for i in range(1, 25)],
                "value_min": 0,
                "value_max": 25,
                "value": 1
            })
        if f"gain {note}" not in processor.controllers_dict:
            zctrls[f"gain {note}"] = zynthian_controller(self, f"gain {note}", {
                "name": "gain (dB)",
                "processor": processor,
                "value_min": -12.0,
                "value_max": 6.0,
                "value": 0.0,
            })
        if f"crop_start {note}" not in processor.controllers_dict:
            zctrls[f"crop_start {note}"] = zynthian_controller(self, f"crop_start {note}", {
                "name": "crop start",
                "processor": processor,
                "is_integer": True,
                "value_max": frames
            })
        elif reset:
            processor.controllers_dict[f"crop_start {note}"].value_max = frames
            processor.controllers_dict[f"crop_start {note}"].value = 0
        if f"crop_end {note}" not in processor.controllers_dict:
            zctrls[f"crop_end {note}"] = zynthian_controller(self, f"crop_end {note}", {
                "name": "crop end",
                "processor": processor,
                "is_integer": True,
                "value": frames,
                "value_max": frames
            })
        elif reset:
            processor.controllers_dict[f"crop_end {note}"].value_max = frames
            processor.controllers_dict[f"crop_end {note}"].value = frames
        if reset:
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
            zctrls[f"zoom {note}"] = zynthian_controller(self, f"zoom {note}", {
                "name": "zoom",
                "processor": processor,
                "ticks": ticks,
                "labels": labels
            })
        processor.controllers_dict.update(zctrls)
        self.update_nudge(processor, note)


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

        self.zynseq.enable_channel(processor.midi_chan, True)
        processor.controllers_dict = {
            "file": zynthian_controller(self, f"file", {
                "name": "file",
                "is_path": True,
                "value_default": "",
                "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
            })
        }

        zctrls = {}
        for phrase in range(self.zynseq.phrases):
            self.zynseq.libseq.setTrackOutput(self.zynseq.scene, phrase, processor.midi_chan, 0, 0xfe)
            try:
                pattern = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
                note = self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]
                zctrls[f"file {note}"] = zynthian_controller(self, f"file {note}", {
                        "name": "file",
                        "processor": processor,
                        "is_path": True,
                        "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
                })
            except:
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 0)
        processor.controllers_dict.update(zctrls)
        #self.set_phrase(processor, self.zynseq.phrase)

    def remove_processor(self, processor):
        self.zynseq.enable_channel(processor.midi_chan, False)
        if self.libclippy.removePlayer(processor.midi_chan - 16) != 0:
            return
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
    # Specific functions
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------


# ******************************************************************************
