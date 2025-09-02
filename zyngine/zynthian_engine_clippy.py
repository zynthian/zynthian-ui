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
import socket
import logging
from time import sleep
import soundfile, pyrubberband
from subprocess import Popen, STDOUT, PIPE
import re
from threading import Timer

from zynlibs.zynseq import zynseq
from zynlibs.zynaudioplayer import zynaudioplayer
from zyngine.zynthian_signal_manager import zynsigman

from . import zynthian_engine
from . import zynthian_controller

from zynconf import ServerPort
import zynautoconnect

# ------------------------------------------------------------------------------
# Linuxsampler Exception Classes
# ------------------------------------------------------------------------------


class zyngine_lscp_error(Exception):
    pass


class zyngine_lscp_warning(Exception):
    pass


# ------------------------------------------------------------------------------
# Clippy Engine Class
# ------------------------------------------------------------------------------

MAX_BEATS = 64 # Maximum quantity of beats in a pattern
MAX_DURATION = 30 # Maximum audio duration to warp, in seconds

class zynthian_engine_clippy(zynthian_engine):

    SYMBOLS = ("file", "warp", "beats", "mode", "gain", "crop_start", "crop_end")

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.zynseq = state_manager.zynseq
        self.libseq = self.zynseq.libseq
        self.name = "Clippy"
        self.nickname = "CL"
        self.type = "MIDI Synth"
        self.options["replace"] = False
        self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_clippy.py"
        self.pattern = None
        self.processor = None

        if jackname:
            self.jackname = jackname
        else:
            self.jackname = self.state_manager.chain_manager.get_next_jackname("clippy")

        self._ctrls = []
        self._ctrl_screens = []

        self.tempo_cb_timer = None

        self.sr = zynautoconnect.get_jackd_samplerate()
        if not os.path.exists("/tmp/silence.wav"):
            soundfile.write("/tmp/silence.wav", [0.0], self.sr)

        #zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE, self.on_playstate)

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def start(self, processor):
        try:
            if processor.proc:
                return
        except:
            pass
        logging.info(f"Starting Engine {self.name}")
        try:
            logging.debug(f"Command: {self.command}")
            # Turns out that environment's PWD is not set automatically
            # when cwd is specified for pexpect.spawn(), so do it here.
            if self.command_cwd:
                self.command_env["PWD"] = self.command_cwd
            # Setting cwd is because we've set PWD above. Some engines doesn't
            # care about the process's cwd, but it is more consistent to set
            # cwd when PWD has been set.
            processor.proc = Popen(processor.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                                text=True, bufsize=1, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_bg_task)

        except Exception as err:
            logging.error(f"Can't start engine {self.name} => {err}")

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.start_bg_task)
        for processor in list(self.processors):
            self.remove_processor

    def lscp_connect(self, processor):
        logging.info("Connecting with LinuxSampler Server...")
        self.state_manager.start_busy("clippy")
        processor.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        processor.sock.setblocking(False)
        processor.sock.settimeout(1)
        i = 0
        while i < 20:
            try:
                processor.sock.connect(("127.0.0.1", processor.lscp_port))
                break
            except:
                sleep(0.25)
                i += 1
        return processor.sock

    def lscp_get_result_index(self, result):
        parts = result.split("[")
        if len(parts) > 1:
            parts = parts[1].split("]")
            return int(parts[0])

    def lscp_send_single(self, processor, command):
        # logging.debug("LSCP SEND => %s" % command)
        command = command + "\r\n"
        try:
            processor.sock.send(command.encode())
            line = processor.sock.recv(4096)
        except Exception as err:
            logging.error("FAILED lscp_send_single(%s): %s" % (command, err))
            self.state_manager.end_busy("clippy")
            return None
        line = line.decode()
        # logging.debug("LSCP RECEIVE => %s" % line)
        if line[:2] == "OK":
            parts = line.split("[")
            if len(parts) > 1:
                parts = parts[1].split("]")
                result = int(parts[0])
            else:
                result = None
            self.state_manager.end_busy("clippy")
            return result
        elif line[0:3] == "ERR":
            parts = line.split(":")
            self.state_manager.end_busy("clippy")
            raise zyngine_lscp_error(
                "{} ({} {})".format(parts[2], parts[0], parts[1]))
        elif line[0:3] == "WRN":
            parts = line.split(":")
            self.state_manager.end_busy("clippy")
            raise zyngine_lscp_warning(
                "{} ({} {})".format(parts[2], parts[0], parts[1]))

    def set_scene(self, processor, scene):
        self.processor = processor
        self.scene = scene
        self.pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
        if self.pattern == 4294967295:
            return
        self._ctrl_screens = [["File", [f"file {self.pattern}"]]]
        try:
            if processor.controllers_dict[f"file {self.pattern}"].path:
                self._ctrl_screens = [
                    [f"File", [f"file {self.pattern}", f"warp {self.pattern}", f"beats {self.pattern}", f"mode {self.pattern}"]],
                    [f"Waveform", [f"gain {self.pattern}", f"crop_start {self.pattern}", f"crop_end {self.pattern}"]]
                ]
        except:
            pass
        processor.init_ctrl_screens()

    def write_sfz(self, processor):
        filename = f"/tmp/clippy_{processor.midi_chan}.sfz"
        with open(filename, "w") as file:
            file.write("<global>\n")
            #file.write("ampeg_release=0.01\n")  # Fast fade to reduce risk of clicks
            file.write("loop_mode=one_shot\n") # Loop whilst key pressed
            file.write("<region>\n")
            file.write(f"sample=/tmp/silence.wav\n")
            file.write(f"key=0\n")
            file.write(f"\n")
            for scene in range(self.zynseq.scenes):
                pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
                file_zctrl = processor.controllers_dict[f"file {pattern}"]
                beats_zctrl = processor.controllers_dict[f"beats {pattern}"]
                gain_zctrl = processor.controllers_dict[f"gain {pattern}"]
                crop_start_zctrl = processor.controllers_dict[f"crop_start {pattern}"]
                crop_end_zctrl = processor.controllers_dict[f"crop_end {pattern}"]
                if file_zctrl.value:
                    file.write("<region>\n")
                    file.write(f"sample={file_zctrl.path}\n")
                    file.write(f"key={scene + 1}\n") #TODO: Fixme
                    file.write(f"volume={gain_zctrl.value}\n")
                    file.write(f"offset={crop_start_zctrl.value}\n")
                    file.write(f"end={crop_end_zctrl.value}\n")
                    file.write(f"\n")
        self.lscp_send_single(processor, f"LOAD INSTRUMENT '{filename}' 0 0")

    def get_scene(self, processor, pattern):
        scene = None
        for s in range(self.zynseq.scenes):
            if self.zynseq.libseq.getPattern(s, processor.midi_chan, 0, 0) == pattern:
                scene = s
                break
        return scene

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
            self.start_bg_task()
            return
            #self.set_file(zctrl.processor, pattern)

        self.write_sfz(zctrl.processor)

    def set_mode(self, processor, pattern, mode):
        # mode: 0=disabled. 1=loop. 2..25=play 1..24
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
            # Open file and get frames and samplerate
            data, sr = soundfile.read(path)
            if len(data) < 100 or sr < 100:
                return
            frames = len(data)
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
            frames = zctrl_crop_end.value - zctrl_crop_start.value
            duration = frames / sr

            # Configure pattern with required beats to play whole file at this tempo
            try:
                reconnect = False
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
                factor = beats / whole_beats * tempo / file_tempo

                # File BPM matches current BPM
                if abs(factor - 1.0) < 0.0001:
                    bpm_match = True
                else:
                    bpm_match = False

                if warp_zctrl.value and not bpm_match and can_warp:
                    # Warp audio to fit pattern length, only if short enough to avoid slow warp
                    # Disconnect MIDI to avoid retrigger during warping
                    if self.libseq.getPlayState(scene, processor.midi_chan):
                        reconnect = True
                        self.lscp_send_single(processor, "REMOVE CHANNEL MIDI_INPUT 0 0 0")
                        # Silence existing audio
                        if self.libseq.getPlayState(scene, processor.midi_chan):
                            self.lscp_send_single(processor, "SEND CHANNEL MIDI_DATA CC 0 120 0")
                    # Do warp
                    data, sr = soundfile.read(path)
                    data = pyrubberband.time_stretch(data, sr, factor)
                    path = f"/tmp/clippy_{processor.midi_chan}_{pattern}.flac"
                    soundfile.write(path, data, sr)
                    zctrl_crop_end.value_max = zctrl_crop_end.value_range = data.shape[0]
                else:
                    try:
                        data, sr = soundfile.read(path)
                        os.remove(f"/tmp/clippy_{processor.midi_chan}_{pattern}.flac")
                        zctrl_crop_end.value_max = zctrl_crop_end.value_range = data.shape[0]
                    except:
                        pass
                #TODO: Reset markers if warp changes, or calculate based on change.
                zctrl_crop_end.set_value(min(zctrl_crop_end.value, zctrl_crop_end.value_max))
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
                if reconnect:
                    # Reconnect MIDI
                    self.lscp_send_single(processor, "ADD CHANNEL MIDI_INPUT 0 0 0")
                    self.lscp_send_single(processor, f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {pattern} => {e}")
        else:
            self.libseq.setPlayState(scene, processor.midi_chan, zynseq.SEQ_STOPPED)
            self.reset_pattern(processor, scene)

        file_zctrl.path = path
        self.zynseq.rebuild_launcher_info(scene, processor.midi_chan)
        if path:
            self._ctrl_screens = [
                [f"File", [f"file {pattern}", f"warp {pattern}", f"beats {pattern}", f"mode {pattern}"]],
                [f"Waveform", [f"gain {pattern}", f"crop_start {pattern}", f"crop_end {pattern}"]]
            ]
        else:
            self._ctrl_screens = [["File", [f"file {pattern}"]]]

        processor.init_ctrl_screens()

    def start_bg_task(self, param=None):
        #TODO: This crashes with double free at high tempo
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = Timer(0.5, self.start_bg_task_cb)
        self.tempo_cb_timer.start()

    def start_bg_task_cb(self):
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = None
        do_warp = False
        for processor in self.processors:
            for scene in range(self.zynseq.scenes):
                pattern = self.zynseq.libseq.getPattern(scene, processor.midi_chan, 0, 0)
                if pattern == 4294967295:
                    continue
                symbol = f"warp {pattern}"
                if processor.controllers_dict.get(symbol).value:
                    self.set_file(processor, pattern)
                    do_warp = True
        if do_warp:
            self.write_sfz(processor)

    def on_playstate(self, bank, seq, state, mode, group):
        #TODO: This VERY uneconomical - needs optimsation
        if state != zynseq.SEQ_STOPPED or bank != 1:
            return
        chan = seq % zynseq.LAUNCHER_COLS
        for processor in self.processors:
            if processor.midi_chan != chan:
                continue
            note = seq // zynseq.LAUNCHER_COLS
            ls_chan_id = 0 # TODO
            self.lscp_send_single(processor, f"SEND CHANNEL MIDI_DATA NOTE_OFF {ls_chan_id} {note} 0")
            #logging.warning(f"TODO: Send MIDI note off to chan: {chan} note: {note}")

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
            if not zctrl.name.startswith("file "):
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
        super().add_processor(processor)

        processor.lscp_port = ServerPort["clippy"] + processor.midi_chan
        processor.command = ["linuxsampler", "--lscp-port", str(processor.lscp_port)]
        self.start(processor)
        self.lscp_connect(processor)
        self.ls_init(processor)
        ls_chan_id = self.lscp_send_single(processor, "ADD CHANNEL")
        self.lscp_send_single(processor, "LOAD ENGINE SFZ 0")
        self.lscp_send_single(processor, "SET CHANNEL AUDIO_OUTPUT_DEVICE 0 0")
        self.lscp_send_single(processor, "ADD CHANNEL MIDI_INPUT 0 0 0")
        self.lscp_send_single(processor, f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")

        processor.controllers_dict = {}
        self.update_controllers(processor)

        self.set_scene(processor, 0)
        self.zynseq.libseq.setChannelType(processor.midi_chan, zynseq.CHANNEL_TYPE_CLIPPY)
        for scene in range(self.zynseq.scenes):
            self.zynseq.libseq.setRepeat(scene, processor.midi_chan, 0)

    def remove_processor(self, processor):
        try:
            self.lscp_send_single(processor, "RESET")
            processor.proc.terminate()
            processor.proc = None
            super().remove_processor(processor)
        except Exception as err:
            logging.error("Can't stop processor")

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

    def get_preset_list(self, bank):
        return []
    #    return self._get_preset_list(bank)

    #def set_preset(self, processor, preset, preload=False):
    #    return False

    # ---------------------------------------------------------------------------
    # Specific functions
    # ---------------------------------------------------------------------------

    def ls_init(self, processor):
        try:
            # Reset
            self.lscp_send_single(processor, "RESET")

            # Config Audio JACK Device 0
            self.ls_audio_device_id = self.lscp_send_single(processor,
                f"CREATE AUDIO_OUTPUT_DEVICE JACK ACTIVE='true' CHANNELS='2' NAME='{self.jackname}'")
            """
            self.lscp_send_single(processor,
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 0 NAME='out_l'")
            self.lscp_send_single(processor,
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 1 NAME='out_r'")
            """

            # Config MIDI JACK Device 1
            self.ls_midi_device_id = self.lscp_send_single(processor,
                f"CREATE MIDI_INPUT_DEVICE JACK ACTIVE='true' NAME='{self.jackname}' PORTS='1'")

            # Global volume gain
            self.lscp_send_single(processor, "SET VOLUME 0.95")
            self.lscp_send_single(processor, "SET VOICES 1")

        except zyngine_lscp_error as err:
            logging.error(err)
        except zyngine_lscp_warning as warn:
            logging.warning(warn)

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------


# ******************************************************************************
