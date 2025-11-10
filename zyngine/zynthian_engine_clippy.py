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
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_clippy.py"

        self.jackname = self.libclippy.getJackname().decode("utf-8")

        self._ctrls = []
        self._ctrl_screens = []

        self.tempo_cb_timer = None
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

        self.phrase = phrase # Only used by GUI widget
        processor.pattern = self.zynseq.libseq.getPattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)

        processor.preset_name = ""
        if processor.pattern == 4294967295:
            return
        self._ctrl_screens = [["File", [f"file {processor.pattern}"]]]
        try:
            if processor.controllers_dict[f"file {processor.pattern}"].value:
                self._ctrl_screens = [
                    [f"File", [f"file {processor.pattern}", f"warp {processor.pattern}", f"beats {processor.pattern}", f"mode {processor.pattern}"]],
                    [f"Waveform", [f"gain {processor.pattern}", f"crop_start {processor.pattern}", f"crop_end {processor.pattern}", f"zoom {processor.pattern}"]]
                ]
                processor.preset_name = processor.controllers_dict[f"file {processor.pattern}"].value.split("/")[-1]
        except Exception as e:
            logging.warning(f"Can't set phrase {phrase} for clippy on chan {processor.midi_chan} => {e}")
        processor.init_ctrl_screens()

    def get_phrase(self, processor, pattern):
        phrase = None
        for s in range(self.zynseq.phrases):
            if self.zynseq.libseq.getPattern(self.zynseq.scene, s, processor.midi_chan, 0, 0) == pattern:
                phrase = s
                break
        return phrase

    def send_controller_value(self, zctrl):
        try:
            pattern = int(zctrl.symbol.split(" ")[1])
            beats_zctrl = zctrl.processor.controllers_dict[f"beats {pattern}"]
            mode_zctrl = zctrl.processor.controllers_dict[f"mode {pattern}"]
        except Exception as e:
            logging.error(f"Can't determine sample index {zctrl.symbol} => {e}")
            return
        if zctrl.symbol.startswith("file"):
            if zctrl.value == 0 or zctrl.value == "0" or zctrl.value == "":
                zctrl.value = "" # TODO: This should be fixed in zctrl class
                mode_zctrl.set_value(0)
            else:
                mode_zctrl.set_value(1)
            beats_zctrl.value = 0
            self.set_file(zctrl.processor, pattern, True)
        elif zctrl.symbol.startswith("warp"):
            self.set_file(zctrl.processor, pattern)
        elif zctrl.symbol.startswith("mode"):
            self.set_mode(self.get_phrase(zctrl.processor, pattern), zctrl.processor.midi_chan, zctrl.value)
        elif zctrl.symbol.startswith("crop_start"):
            zctrl_crop_end = zctrl.processor.controllers_dict[zctrl.symbol.replace("start", "end")]
            zctrl_crop_end.value_min = zctrl.value
            zctrl_crop_end.value_range = zctrl_crop_end.value_max - zctrl_crop_end.value_min
            #TODO: Change file crop
            return
        elif zctrl.symbol.startswith("crop_end"):
            zctrl_crop_start = zctrl.processor.controllers_dict[zctrl.symbol.replace("end", "start")]
            zctrl_crop_start.value_max = zctrl.value
            zctrl_crop_start.value_range = zctrl_crop_start.value
            return
        elif zctrl.symbol.startswith("gain"):
            return
            #TODO: Must map clips so that we can access them. Clips may change phrase if moved in UI... 
            #self.libclippy.setGain(zctrl.processor.midi_chan, phrase, ctypes.c_float(zctrl.value))
        elif zctrl.symbol.startswith("zoom"):
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

    def set_file(self, processor, pattern, reset=False):
        file_zctrl = processor.controllers_dict[f"file {pattern}"]
        warp_zctrl = processor.controllers_dict[f"warp {pattern}"]
        beats_zctrl = processor.controllers_dict[f"beats {pattern}"]
        mode_zctrl = processor.controllers_dict[f"mode {pattern}"]
        processor.pattern = pattern
        # Find what phrase this pattern is in...
        phrase = self.get_phrase(processor, pattern)
        if phrase is None:
            logging.error(f"Pattern {pattern} not found in any phrase")
            return
        note = self.libseq.getNoteAtIndex(pattern, 0)
        if note > 127:
            note = 0
        path = file_zctrl.value
        if path:
            sr = self.libclippy.getFileSamplerate(bytes(path, "utf-8"))
            frames = self.libclippy.getFileFrames(bytes(path, "utf-8"))
            ratio = 1.0
            write_file = (sr != self.samplerate)
            processor.preset_name = path.split("/")[-1]

            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.libseq.getTempoAt(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, 1, 0)
            if not tempo:
                tempo = self.zynseq.libseq.getTempo()
            regptn = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(regptn, filename)
            try:
                file_tempo = int(matches[0])
            except:
                file_tempo = tempo
            
            zctrl_crop_start = processor.controllers_dict[f"crop_start {pattern}"]
            zctrl_crop_end = processor.controllers_dict[f"crop_end {pattern}"]
            if reset:
                # Use full file duration
                nudge_factor = frames / 1000
                zctrl_crop_start.value_max = zctrl_crop_start.value_range = frames
                zctrl_crop_start.value = 0
                zctrl_crop_start.nudge_factor = nudge_factor
                zctrl_crop_end.value = zctrl_crop_end.value_max = zctrl_crop_end.value_range = frames
                zctrl_crop_end.nudge_factor = nudge_factor
            #frames = zctrl_crop_end.value - zctrl_crop_start.value
            duration = frames / sr

            # Configure pattern with required beats to play whole file at this tempo
            try:
                #beats_per_bar = self.libseq.getTimeSig()
                beats_per_bar = self.zynseq.libseq.getTimeSigAt(self.zynseq.scene, phrase, zynseq.PHRASE_CHANNEL, 0)
                if beats_per_bar < 1:
                    beats_per_bar = 4
                beats = duration * file_tempo / 60
                bars = round(beats / beats_per_bar)
                if beats_zctrl.value:
                    whole_beats = beats_zctrl.value
                else:
                    whole_beats = bars * beats_per_bar
                can_warp = whole_beats <= MAX_BEATS and duration <= MAX_DURATION
                factor = (whole_beats * file_tempo) / (beats * tempo)

                # File BPM matches current BPM
                if abs(factor - 1.0) < 0.0001:
                    bpm_match = True
                else:
                    bpm_match = False

                if warp_zctrl.value and not bpm_match and can_warp:
                    # Warp audio to fit pattern length, only if short enough to avoid slow warp
                    ratio = factor
                    write_file = True

                dst_path = f"/tmp/clippy_{processor.midi_chan}_{pattern}.wav"
                if write_file:
                    self.libclippy.copyFile(bytes(path, "utf-8"), bytes(dst_path, "utf-8"), 2, ctypes.c_float(ratio))
                    path = dst_path
                    zctrl_crop_end.value_max = zctrl_crop_end.value_range = self.libclippy.getFileFrames(bytes(dst_path, "utf-8"))
                else:
                    try:
                        os.remove(dst_path)
                        #zctrl_crop_end.value_max = zctrl_crop_end.value_range = data.shape[0]
                    except:
                        pass
                #TODO: Reset markers if warp changes, or calculate based on change.
                #zctrl_crop_end.set_value(min(zctrl_crop_end.value, zctrl_crop_end.value_max))
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
                processor.controllers_dict[f"zoom {pattern}"].ticks = ticks
                processor.controllers_dict[f"zoom {pattern}"].labels = labels

                # Setup zynseq pattern & sequence
                pattern = self.libseq.getPattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)
                if pattern == 4294967295:
                    logging.warning(f"Can't find pattern for phrase {phrase} chan {processor.midi_chan}")
                else:
                    self.libseq.selectPattern(pattern)
                    self.libseq.clearPattern(pattern)
                    self.libseq.setStepsPerBeat(1)
                    self.libseq.setBeatsInPattern(pattern, whole_beats)
                    #TODO: Need to add notes based on phrases
                    note = self.libclippy.loadClip(processor.midi_chan - 16, note, bytes(path, "utf-8"))
                    self.libseq.addNote(0, note, 100, 1, 0.0)
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "name", os.path.splitext(filename)[0])
                self.set_mode(phrase, processor.midi_chan, mode_zctrl.value)
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {pattern} => {e}")
        else:
            self.libseq.setPlayState(self.zynseq.scene, phrase, processor.midi_chan, zynseq.SEQ_STOPPED)
            self.reset_pattern(processor, phrase)

        file_zctrl.path = path
        if path:
            self._ctrl_screens = [
                [f"File", [f"file {pattern}", f"warp {pattern}", f"beats {pattern}", f"mode {pattern}"]],
                [f"Waveform", [f"gain {pattern}", f"crop_start {pattern}", f"crop_end {pattern}", f"zoom {pattern}"]]
            ]
        else:
            self._ctrl_screens = [["File", [f"file {pattern}"]]]
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
            for phrase in range(self.zynseq.phrases):
                pattern = self.zynseq.libseq.getPattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)
                if pattern == 4294967295:
                    continue
                symbol = f"warp {pattern}"
                if processor.controllers_dict.get(symbol).value:
                    self.set_file(processor, pattern)

    def update_controllers(self, processor):
        patterns = []
        for phrase in range(self.zynseq.phrases):
            pattern = self.zynseq.libseq.getPattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)
            if pattern == 4294967295:
                continue
            patterns.append(pattern)
            # Add missing controllers
            zctrls = {}
            if f"file {pattern}" not in processor.controllers_dict:
                zctrls[f"file {pattern}"] = zynthian_controller(self, f"file {pattern}", {
                        "name": "file",
                        "is_path": True,
                        "value_default": "",
                        "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
                        "processor": processor
                    })
                zctrls[f"file {pattern}"].path = ""
                zctrls[f"warp {pattern}"] = zynthian_controller(self, f"warp {pattern}", {
                        "name": "warp",
                        "processor": processor,
                        "is_toggle": True,
                        "labels": ["off", "on"],
                        "value": "on"
                    })
                zctrls[f"beats {pattern}"] = zynthian_controller(self, f"beats {pattern}", {
                    "name": "beats",
                    "processor": processor,
                    "is_integer": True,
                    "value": 0,
                    "value_min": 0,
                    "value_max": MAX_BEATS
                })
                zctrls[f"mode {pattern}"] = zynthian_controller(self, f"mode {pattern}", {
                    "name": "mode",
                    "processor": processor,
                    "is_integer": True,
                    "labels": ["disabled", "loop"] + [f"play {i}" for i in range(1, 25)],
                    "value_min": 0,
                    "value_max": 25,
                    "value": 0
                })
                zctrls[f"gain {pattern}"] = zynthian_controller(self, f"gain {pattern}", {
                    "name": "gain (dB)",
                    "processor": processor,
                    "value_min": -12.0,
                    "value_max": 6.0,
                    "value": 0.0,
                })
                zctrls[f"crop_start {pattern}"] = zynthian_controller(self, f"crop_start {pattern}", {
                    "name": "crop start",
                    "processor": processor,
                    "is_integer": True
                })
                zctrls[f"crop_end {pattern}"] = zynthian_controller(self, f"crop_end {pattern}", {
                    "name": "crop end",
                    "processor": processor,
                    "is_integer": True
                })
                ticks = []
                labels = []
                for i in range(10):
                    ticks.append(2 ** i)
                    labels.append(f"x{ticks[i]}")
                zctrls[f"zoom {pattern}"] = zynthian_controller(self, f"zoom {pattern}", {
                    "name": "zoom",
                    "processor": processor,
                    "ticks": ticks,
                    "labels": labels
                })
                self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "mode", 0x0001)
                self.reset_pattern(processor, phrase)
            processor.controllers_dict.update(zctrls)

        # Remove controllers for non-existing patterns
        for zctrl in list(processor.controllers_dict.values()):
            if not zctrl.symbol.startswith("file "):
                continue
            pattern = int(zctrl.symbol.split(" ")[1])
            if pattern in patterns:
                continue
            try:
                processor.controllers_dict.pop(f"file {pattern}", None)
                processor.controllers_dict.pop(f"warp {pattern}", None)
                processor.controllers_dict.pop(f"beats {pattern}", None)
                processor.controllers_dict.pop(f"mode {pattern}", None)
                processor.controllers_dict.pop(f"gain {pattern}", None)
                processor.controllers_dict.pop(f"crop_start {pattern}", None)
                processor.controllers_dict.pop(f"crop_end {pattern}", None)
                processor.controllers_dict.pop(f"zoom {pattern}", None)
            except Exception as e:
                logging.warning("Failed to remove controller for pattern %d: %s", pattern, e)

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        """
            Add a processor (clip player channel)

            processor: zynthian_processor object
        """
        
        midi_chan = self.libclippy.addPlayer(255)
        if midi_chan > 15:
            return
        self.processors.append(processor)
        self.state_manager.chain_manager.set_midi_chan(processor.chain_id, midi_chan + 16)
        processor.jackname = f"{self.jackname}:out_{midi_chan + 1 :02d}"

        processor.controllers_dict = {}
        self.update_controllers(processor)

        self.zynseq.enable_channel(processor.midi_chan, True)
        for phrase in range(self.zynseq.phrases):
            self.zynseq.set_sequence_param(self.zynseq.scene, phrase, processor.midi_chan, "repeat", 0)
            self.zynseq.libseq.setTrackOutput(self.zynseq.scene, phrase, processor.midi_chan, 0, 0xfe)
        self.set_phrase(processor, 0)

    def remove_processor(self, processor):
        self.zynseq.enable_channel(processor.midi_chan, False)
        if self.libclippy.removePlayer(processor.midi_chan - 16) != 0:
            return
        super().remove_processor(processor)

    def reset_pattern(self, processor, phrase):
            #self.libseq.clearSequence(self.zynseq.scene, phrase, processor.midi_chan)
            #pattern = self.libseq.getPatternAt(self.zynseq.scene, phrase, processor.midi_chan, 0, 0)
            #if pattern == 4294967295:
            #    pattern = self.libseq.createPattern()
            #    self.libseq.addPattern(self.zynseq.scene, phrase, processor.midi_chan, 0, 0, pattern, True)
            #self.libseq.clearPattern(pattern)
            #self.libseq.setStepsPerBeat(1)
            #self.libseq.setBeatsInPattern(pattern, 1)
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
