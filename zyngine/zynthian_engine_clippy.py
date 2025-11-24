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
        #self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_clippy.py"

        self.jackname = self.libclippy.getJackname().decode("utf-8")
        self._ctrls = []
        self._ctrl_screens = []

        self.selected_proc = None
        self.selected_phrase = None
        self.selected_note = None

        self.tempo_cb_timer = None
        self.crop_cb_timer = None
        self.samplerate = zynautoconnect.get_jackd_samplerate()
        zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_bg_task)

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_bg_task)
        self.libclippy.end()

    def set_phrase(self, processor, phrase):
        """ Select the phrase for control, etc"""

        self.selected_proc = processor
        self.selected_phrase = phrase
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
        except:
            self._ctrl_screens = [["Clip", ["file"]]]
            processor.preset_name = ""
            self.selected_note = 0
        processor.init_ctrl_screens()

    def get_phrase(self, chan, note):
        """ Get the phrase index from a MIDI note

            chan: MIDI channel (16..31)
            note: MIDI note
            returns: Phrase index or None on error
        """

        for id, phrase in enumerate(self.zynseq.state["scenes"][self.zynseq.scene]["phrases"]):
            try:
                pattern = phrase["sequences"][chan]["tracks"][0]["patns"]["0"]
                if note == self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]:
                    return id
            except:
                pass
        logging.warning(f"Failed to get phrase for clippy note {note}")
        return None

    def get_note(self, symbol):
        """ Get the the MIDI note from a controller symbol

            symbol: Controller symbol
            returns: MIDI note of clip or None if invalid
        """

        try:
            return int(symbol.split(" ")[1])
        except:
            return None

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
            return
        elif zctrl.symbol.startswith("crop_end"):
            zctrl_crop_start = zctrl.processor.controllers_dict[zctrl.symbol.replace("end", "start")]
            zctrl_crop_start.value_max = zctrl.value
            zctrl_crop_start.value_range = zctrl_crop_start.value
            self.monitors_dict["crop_end"] = zctrl.value
            return
        elif zctrl.symbol.startswith("gain"):
            try:
                self.libclippy.setGain(zctrl.processor.midi_chan - 16, note - 1, ctypes.c_float(zctrl.value))
            except Exception as e:
                logging.warning(e)
            return
        elif zctrl.symbol.startswith("zoom"):
            zctrl_crop_start = zctrl.processor.controllers_dict[zctrl.symbol.replace("zoom", "crop_start")]
            zctrl_crop_end = zctrl.processor.controllers_dict[zctrl.symbol.replace("zoom", "crop_end")]
            frames = zctrl_crop_end.value_max
            nudge_factor = max(1, frames // (zctrl.value * 100))
            zctrl_crop_start.nudge_factor = nudge_factor
            zctrl_crop_end.nudge_factor = nudge_factor
            self.monitors_dict["zoom"] = zctrl.value
            return

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

    def set_file(self, processor, note, reset=False):
        """ Loads a file into a clip. SRC and warp to new file if necessary."""

        """
        if note == 0:
            # No clip loaded so create controllers
            self.add_controllers(processor, note)

        """
        if note == 0:
            # No clip loaded
            beats_value = 0
            warp_value = True
            file_zctrl = processor.controllers_dict["file"]
        else:
            file_zctrl = processor.controllers_dict[f"file {note}"]
            warp_zctrl = processor.controllers_dict[f"warp {note}"]
            beats_zctrl = processor.controllers_dict[f"beats {note}"]
            mode_zctrl = processor.controllers_dict[f"mode {note}"]
            beats_value = beats_zctrl.value
            warp_value = warp_zctrl.value

        # Find what phrase this note is in...
        phrase = self.get_phrase(processor.midi_chan, note)
        if phrase is None:
            phrase = self.selected_phrase

        if 0 < note > 127:
            note = 0
        path = file_zctrl.value
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
            
            """
            zctrl_crop_start = processor.controllers_dict[f"crop_start {note}"]
            zctrl_crop_end = processor.controllers_dict[f"crop_end {note}"]
            if reset:
                # Use full file duration
                nudge_factor = frames // 1000
                zctrl_crop_start.value_max = zctrl_crop_start.value_range = frames
                zctrl_crop_start.value = 0
                zctrl_crop_start.nudge_factor = nudge_factor
                zctrl_crop_end.value = zctrl_crop_end.value_max = zctrl_crop_end.value_range = frames
                zctrl_crop_end.nudge_factor = nudge_factor
            #frames = zctrl_crop_end.value - zctrl_crop_start.value
            """
            duration = frames / sr

            # Configure pattern with required beats to play whole file at this tempo
            try:
                #beats_per_bar = self.libseq.getTimeSig()
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
                crop_start = 0
                crop_end = frames
                if write_file and self.libclippy.copyFile(bytes(path, "utf-8"), bytes(dst_path, "utf-8"), 2, ctypes.c_float(ratio), crop_start, crop_end) == 0:
                    path = dst_path
                    #zctrl_crop_end.value_max = zctrl_crop_end.value_range = self.libclippy.getFileFrames(bytes(dst_path, "utf-8"))
                else:
                    try:
                        os.remove(dst_path)
                        #zctrl_crop_end.value_max = zctrl_crop_end.value_range = data.shape[0]
                    except:
                        pass
                #TODO: Reset markers if warp changes, or calculate based on change.
                #zctrl_crop_end.set_value(min(zctrl_crop_end.value, zctrl_crop_end.value_max))
                """
                if bpm_match:
                    #TODO: Remove this when finished design - don't need to show user that warp is not changing file
                    warp_zctrl.labels = ["off", f"{tempo:.1f}*\nBPM"]
                else:
                    warp_zctrl.labels = ["off", f"{tempo:.1f}\nBPM"]
                if can_warp:
                    beats_zctrl.value = whole_beats
                    beats_zctrl.set_readonly(warp_zctrl.value != 0)
                else:
                    beats_zctrl.value = 0
                    warp_zctrl.value = 0
                """

                # Setup zynseq pattern & sequence
                pattern = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
                self.libseq.selectPattern(pattern)
                self.libseq.clearPattern(pattern)
                self.libseq.setStepsPerBeat(1)
                self.libseq.setBeatsInPattern(pattern, whole_beats)
                note = self.libclippy.loadClip(processor.midi_chan - 16, note, bytes(path, "utf-8"))
                self.libseq.addNote(0, note, 100, 1, 0.0)
                self.zynseq.refresh_state()
                self.add_controllers(processor, note, frames)
                processor.controllers_dict[f"file {note}"].value = file_zctrl.value
                file_zctrl.value = ""
                file_zctrl = processor.controllers_dict[f"file {note}"]
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", os.path.splitext(filename)[0])
                self.set_mode(phrase, processor.midi_chan, 1) # Default repeat
                if phrase == self.selected_phrase:
                    self.selected_note = note

            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {pattern} => {e}")
        else:
            self.libseq.setPlayState(self.zynseq.scene, phrase, processor.midi_chan, zynseq.SEQ_STOPPED)
            self.reset_sequence(processor, phrase)

        file_zctrl.path = path
        if path:
            #TODO: This is duplicate / redundant code
            self._ctrl_screens = [
                ["Clip", [f"file {note}", f"crop_start {note}", f"crop_end {note}", f"zoom {note}"]],
                ["Control", [f"gain {note}", f"warp {note}", f"beats {note}", f"mode {note}"]]
                ]
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
            processor.controllers_dict[f"zoom {note}"].ticks = ticks
            processor.controllers_dict[f"zoom {note}"].labels = labels
            processor.controllers_dict[f"zoom {note}"].value_max = val / 2
        else:
            self._ctrl_screens = [["Clip", ["file"]]]
            self.libclippy.unloadClip(processor.midi_chan - 16, note)

        processor.init_ctrl_screens()

    def start_bg_task(self, tempo=None):
        #TODO: This crashes with double free at high tempo
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = Timer(0.5, self.start_bg_task_cb)
        self.tempo_cb_timer.start()

    def start_bg_task_cb(self):
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = None
        for processor in self.processors:
            #TODO: This is wrong...
            for note in range(1, self.zynseq.phrases + 1):
                # There should only be notes 1..num of phrases
                symbol = f"warp {note}"
                if processor.controllers_dict.get(symbol).value:
                    self.set_file(processor, note)

    def add_controllers(self, processor, note, frames):
        """ Adds a controllers to processor

            processor: Clippy processor object
            note: MIDI note (clip id)
            frames: Quantity of frames in file
        """

        # Add default controllers for each phrase
        zctrls = {}
        zctrls[f"file {note}"] = zynthian_controller(self, f"file {note}", {
                "name": "file",
                "processor": processor,
                "is_path": True,
                "value_default": "",
                "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
                "value": ""
        })
        zctrls[f"warp {note}"] = zynthian_controller(self, f"warp {note}", {
                "name": "warp",
                "processor": processor,
                "is_toggle": True,
                "labels": ["off", "on"],
                "value": "on"
        })
        zctrls[f"beats {note}"] = zynthian_controller(self, f"beats {note}", {
            "name": "beats",
            "processor": processor,
            "is_integer": True,
            "value": 0,
            "value_min": 0,
            "value_max": MAX_BEATS
        })
        zctrls[f"mode {note}"] = zynthian_controller(self, f"mode {note}", {
            "name": "mode",
            "processor": processor,
            "is_integer": True,
            "labels": ["disabled", "loop"] + [f"play {i}" for i in range(1, 25)],
            "value_min": 0,
            "value_max": 25,
            "value": 1
        })
        zctrls[f"gain {note}"] = zynthian_controller(self, f"gain {note}", {
            "name": "gain (dB)",
            "processor": processor,
            "value_min": -12.0,
            "value_max": 6.0,
            "value": 0.0,
        })
        zctrls[f"crop_start {note}"] = zynthian_controller(self, f"crop_start {note}", {
            "name": "crop start",
            "processor": processor,
            "is_integer": True,
            "value_max": frames
        })
        zctrls[f"crop_end {note}"] = zynthian_controller(self, f"crop_end {note}", {
            "name": "crop end",
            "processor": processor,
            "is_integer": True,
            "value": frames,
            "value_max": frames
        })
        ticks = []
        labels = []
        for i in range(10):
            ticks.append(2 ** i)
            labels.append(f"x{ticks[i]}")
        zctrls[f"zoom {note}"] = zynthian_controller(self, f"zoom {note}", {
            "name": "zoom",
            "processor": processor,
            "ticks": ticks,
            "labels": labels
        })
        self.zynseq.set_sequence_param(self.zynseq.scene, note - 1, processor.midi_chan, "mode", 0x0001)
        self.reset_sequence(processor, note - 1)
        processor.controllers_dict.update(zctrls)


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
        for phrase in range(self.zynseq.phrases):
            self.zynseq.libseq.setTrackOutput(self.zynseq.scene, phrase, processor.midi_chan, 0, 0xfe)
            try:
                pattern = self.zynseq.state["scenes"][self.zynseq.scene]["phrases"][phrase]["sequences"][processor.midi_chan]["tracks"][0]["patns"]["0"]
                note = self.zynseq.state["patns"][str(pattern)]["events"][0]["val1Start"]
                self.add_controllers(processor, note)
            except:
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 0)

        self.set_phrase(processor, self.zynseq.phrase)

    def remove_processor(self, processor):
        self.zynseq.enable_channel(processor.midi_chan, False)
        if self.libclippy.removePlayer(processor.midi_chan - 16) != 0:
            return
        super().remove_processor(processor)

    def reset_sequence(self, processor, phrase):
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 0)
            self.libseq.updateSequenceInfo()
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", "")

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
