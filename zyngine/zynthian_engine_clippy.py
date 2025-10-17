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
        self.type = "MIDI Synth"
        self.options["replace"] = False
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_clippy.py"
        self.pattern = None
        self.processor = None

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

    def set_scene(self, processor, scene):
        self.processor = processor
        self.scene = scene
        self.pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
        processor.preset_name = ""
        if self.pattern == 4294967295:
            return
        self._ctrl_screens = [["File", [f"file {self.pattern}"]]]
        try:
            if processor.controllers_dict[f"file {self.pattern}"].value:
                self._ctrl_screens = [
                    [f"File", [f"file {self.pattern}", f"warp {self.pattern}", f"beats {self.pattern}", f"mode {self.pattern}"]],
                    [f"Waveform", [f"gain {self.pattern}"], f"crop_start {self.pattern}", f"crop_end {self.pattern}"]
                ]
                processor.preset_name = processor.controllers_dict[f"file {self.pattern}"].value.split("/")[-1]
        except Exception as e:
            logging.warning(f"Can't set scene {scene} for clippy on chan {processor.midi_chan} => {e}")
        processor.init_ctrl_screens()

    def get_scene(self, processor, pattern):
        scene = None
        for s in range(self.zynseq.scenes):
            if self.zynseq.libseq.getPattern(s, processor.midi_chan, 0, 0) == pattern:
                scene = s
                break
        return scene

    def get_pattern(self, processor, scene):
        return self.libseq.getPattern(scene, processor.midi_chan, 0, 0)

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
                zctrl.value = ""   # TODO: This should be fixed in zctrl class
                mode_zctrl.set_value(0)
            else:
                mode_zctrl.set_value(1)
            beats_zctrl.value = 0
            self.set_file(zctrl.processor, pattern, True)
            self.zynseq.rebuild_all_launcher_info()
        elif zctrl.symbol.startswith("warp"):
            self.set_file(zctrl.processor, pattern)
        elif zctrl.symbol.startswith("mode"):
            self.set_mode(zctrl.processor, pattern, zctrl.value)
        elif zctrl.symbol.startswith("crop"):
            return
            #self.set_file(zctrl.processor, pattern)
        elif zctrl.symbol.startswith("gain"):
            pass
            #TODO: Must map clips so that we can access them. Clips may change scene if moved in UI... 
            #self.libclippy.setGain(zctrl.processor.midi_chan, scene, ctypes.c_float(zctrl.value))

        self.write_sfz(zctrl.processor)

    """ Set play mode
    
        processor - processor object
        pattern - pattern id
        mode - play mode [0=disabled, 1=loop, 2..25=play 1..24 times]
    """
    def set_mode(self, processor, pattern, mode):
        scene = self.get_scene(processor, pattern)
        match mode:
            case 0:
                self.libseq.setPlayMode(scene, processor.midi_chan, 0x0001)

            case 1:
                self.libseq.setPlayMode(scene, processor.midi_chan, 0x0101)
                self.libseq.setFollowAction(scene, processor.midi_chan, zynseq.FOLLOW_ACTION_RELATIVE, 0)
            case _:
                self.libseq.setPlayMode(scene, processor.midi_chan, 0x01 | ((mode - 1) << 8))
                self.libseq.setFollowAction(scene, processor.midi_chan, zynseq.FOLLOW_ACTION_NONE, 0)
        self.zynseq.rebuild_launcher_info(processor.midi_chan)

    def set_file(self, processor, pattern, reset=False):
        file_zctrl = processor.controllers_dict[f"file {pattern}"]
        warp_zctrl = processor.controllers_dict[f"warp {pattern}"]
        beats_zctrl = processor.controllers_dict[f"beats {pattern}"]
        # Find what scene this pattern is in...
        scene = self.get_scene(processor, pattern)
        if scene is None:
            logging.error(f"Pattern {pattern} not found in any scene")
            return
        path = file_zctrl.value
        if path:
            sr = self.libclippy.getFileSamplerate(bytes(path, "utf-8"))
            frames = self.libclippy.getFileFrames(bytes(path, "utf-8"))
            ratio = 1.0
            write_file = (sr != self.samplerate)
            processor.preset_name = path.split("/")[-1]

            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.libseq.getTempoAt(scene, zynseq.SCENE_CHANNEL, 1, 0)
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
                beats_per_bar = self.zynseq.libseq.getTimeSigAt(scene, zynseq.SCENE_CHANNEL, 0)
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

                # Setup zynseq pattern & sequence
                pattern = self.libseq.getPattern(scene, processor.midi_chan, 0, 0)
                if pattern == 4294967295:
                    logging.warning(f"Can't find pattern for scene {scene} chan {processor.midi_chan}")
                else:
                    self.libseq.selectPattern(pattern)
                    self.libseq.clearPattern(pattern)
                    self.libseq.setStepsPerBeat(1)
                    self.libseq.setBeatsInPattern(pattern, whole_beats)
                    #TODO: Need to add notes based on scenes
                    self.libseq.addNote(0, scene + 1, 100, 1, 0.0)
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_name(scene, processor.midi_chan, os.path.splitext(filename)[0])
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {pattern} => {e}")
        else:
            self.libseq.setPlayState(scene, processor.midi_chan, zynseq.SEQ_STOPPED)
            self.reset_pattern(processor, scene)

        file_zctrl.path = path
        self.zynseq.rebuild_launcher_info(scene, processor.midi_chan)
        if path:
            self.libclippy.loadClip(processor.midi_chan, scene, bytes(path, "utf-8"))
            self._ctrl_screens = [
                [f"File", [f"file {pattern}", f"warp {pattern}", f"beats {pattern}", f"mode {pattern}"]],
                [f"Waveform", [f"gain {pattern}", f"crop_start {pattern}", f"crop_end {pattern}"]]
            ]
        else:
            self._ctrl_screens = [["File", [f"file {pattern}"]]]
            self.libclippy.unloadClip(processor.midi_chan, scene)

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
            for scene in range(self.zynseq.scenes):
                pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
                if pattern == 4294967295:
                    continue
                symbol = f"warp {pattern}"
                if processor.controllers_dict.get(symbol).value:
                    self.set_file(processor, pattern)

    def update_controllers(self, processor):
        patterns = []
        for scene in range(self.zynseq.scenes):
            pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
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
                self.libseq.setPlayMode(scene, processor.midi_chan, 0x0001)
                self.reset_pattern(processor, scene)
            processor.controllers_dict.update(zctrls)

        # Remove controllers for non-existing patterns
        for zctrl in processor.controllers_dict.values():
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
            except Exception as e:
                logging.warning("Failed to remove controller for pattern %d: %s", pattern, e)

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        if self.libclippy.addPlayer(processor.midi_chan) != 0:
            return
        self.processors.append(processor)
        processor.jackname = f"{self.jackname}:out_{processor.midi_chan + 1 :02d}"

        processor.controllers_dict = {}
        self.update_controllers(processor)

        self.set_scene(processor, 0)
        self.zynseq.libseq.setChannelType(processor.midi_chan, zynseq.CHANNEL_TYPE_CLIPPY)
        for scene in range(self.zynseq.scenes):
            self.zynseq.libseq.setRepeat(scene, processor.midi_chan, 0)

    def remove_processor(self, processor):
        if self.libclippy.removePlayer(processor.midi_chan) != 0:
            return
        super().remove_processor(processor)

    def reset_pattern(self, processor, scene):
            #self.libseq.clearSequence(scene, processor.midi_chan)
            #pattern = self.libseq.getPatternAt(scene, processor.midi_chan, 0, 0)
            #if pattern == 4294967295:
            #    pattern = self.libseq.createPattern()
            #    self.libseq.addPattern(scene, processor.midi_chan, 0, 0, pattern, True)
            #self.libseq.clearPattern(pattern)
            #self.libseq.setStepsPerBeat(1)
            #self.libseq.setBeatsInPattern(pattern, 1)
            self.libseq.setRepeat(scene, processor.midi_chan, 0)
            self.libseq.updateSequenceInfo()
            self.zynseq.set_sequence_name(scene, processor.midi_chan, "")

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
