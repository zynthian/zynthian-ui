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
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)

        except Exception as err:
            logging.error(f"Can't start engine {self.name} => {err}")

    def stop(self):
        logging.info("Stopping Engine " + self.name)
        zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)
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

    def insert_slot(self, slot):
        for processor in self.processors:
            self.insert_proc_slot(processor, slot)

    def insert_proc_slot(self, processor, slot):
        # Create new zctrls
        zctrls = {
            f"file {slot}": zynthian_controller(self, f"file {slot}", {
                "name": "file",
                "is_path": True,
                "value_default": "",
                "path_file_types": ["wav", "ogg", "mp3", "flac", "aac"],
                "processor": processor
            }),
            f"warp {slot}": zynthian_controller(self, f"warp {slot}", {
                "name": "warp",
                "processor": processor,
                "is_toggle": True,
                "labels": ["off", "on"],
                "value": "on"
            }),
            f"beats {slot}": zynthian_controller(self, f"beats {slot}", {
                "name": "beats",
                "processor": processor,
                "is_integer": True,
                "value": 0,
                "value_min": 0,
                "value_max": MAX_BEATS
            }),
            f"mode {slot}": zynthian_controller(self, f"mode {slot}", {
                "name": "mode",
                "processor": processor,
                "is_integer": True,
                "labels": ["disabled", "loop"] + [f"play {i}" for i in range(1, 25)],
                "value_min": 0,
                "value_max": 25,
                "value": 0
            }),
            f"gain {slot}": zynthian_controller(self, f"gain {slot}", {
                "name": "gain (dB)",
                "processor": processor,
                "value_min": -12.0,
                "value_max": 6.0,
                "value": 0.0,
            }),
            f"crop_start {slot}": zynthian_controller(self, f"crop_start {slot}", {
                "name": "crop start",
                "processor": processor,
                "is_integer": True
            }),
            f"crop_end {slot}": zynthian_controller(self, f"crop_end {slot}", {
                "name": "crop end",
                "processor": processor,
                "is_integer": True
            })
        }
        sequence = processor.midi_chan + slot * zynseq.LAUNCHER_COLS
        self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0001)

        # Move zctrls
        for i in range(slot, self.zynseq.slots):
            for name in self.SYMBOLS:
                try:
                    zctrl = processor.controllers_dict.pop(f"{name} {i}")
                    zctrl.symbol = f"{name} {i + 1}"
                    zctrls[zctrl.symbol] = zctrl
                except:
                    break #TODO: Optimise by breaking out of outer loop

        # Merge controller dict
        processor.controllers_dict.update(zctrls)
        processor.controllers_dict["slot"].value_max = self.zynseq.slots

    def set_slot(self, processor, slot):
        processor.controllers_dict["slot"].set_value(slot + 1)

    def remove_slot(self, slot):
        slot += 1
        for processor in self.processors:
            try:
                for symbol in ("file", "gain", "mode", "warp", "beats", "crop_start", "crop_end"):
                    del processor.controllers_dict[f"{symbol} {slot}"]
            except:
                pass # We expect warp and beats to fail sometimes.

            symbols = []
            for symbol in processor.controllers_dict.keys():
                if symbol == "slot":
                    continue
                idx = int(symbol[-2:])
                if idx >= slot:
                    symbols.append(symbol)

            # Move zctrls
            zctrls = {}
            for symbol in symbols:
                zctrl = processor.controllers_dict.pop(symbol)
                idx = int(symbol[-2:])
                new_symbol = f"{symbol[:-2]}{idx - 1}"
                zctrl.symbol = zctrl.name = zctrl.short_name = new_symbol
                zctrls[new_symbol] = zctrl
            processor.controllers_dict.update(zctrls)
            processor.controllers_dict["slot"].value_max = self.zynseq.slots

    def move_slot(self, slot, offset):
        """
        Move slot to +offset
        Nudge slots between slot & offset
        """

        slot += 1
        new_slot = slot + offset
        if offset == 0 or self.zynseq.slots < new_slot < 0:
            return
        for processor in self.processors:
            zctrls = {}
            for symbol in ("file", "gain", "mode", "warp", "beats", "crop_start", "crop_end"):
                try:
                    zctrl = processor.controllers_dict[f"{symbol} {slot}"]
                    new_symbol = f"{symbol} {slot + offset}"
                    zctrl.symbol = zctrl.name = zctrl.short_name = new_symbol
                    zctrls[new_symbol] = zctrl
                except:
                    pass
            if offset > 0:
                for i in range(slot + 1, slot + 1 + offset):
                    for symbol in ("file", "gain", "mode", "warp", "beats", "crop_start", "crop_end"):
                        try:
                            zctrl = processor.controllers_dict[f"{symbol} {i}"]
                            new_symbol = f"{symbol} {i - 1}"
                            zctrl.symbol = zctrl.name = zctrl.short_name = new_symbol
                            zctrls[new_symbol] = zctrl
                        except:
                            pass
            else:
                for i in range(slot + offset, slot):
                    for symbol in ("file", "gain", "mode", "warp", "beats", "crop_start", "crop_end"):
                        try:
                            zctrl = processor.controllers_dict[f"{symbol} {i}"]
                            new_symbol = f"{symbol} {i + 1}"
                            zctrl.symbol = zctrl.name = zctrl.short_name = new_symbol
                            zctrls[new_symbol] = zctrl
                        except:
                            pass
            processor.controllers_dict.update(zctrls)

    # ---------------------------------------------------------------------------
    # Controller Management
    # ---------------------------------------------------------------------------

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
            for slot in range(self.zynseq.slots):
                file_zctrl = processor.controllers_dict[f"file {slot}"]
                beats_zctrl = processor.controllers_dict[f"beats {slot}"]
                gain_zctrl = processor.controllers_dict[f"gain {slot}"]
                crop_start_zctrl = processor.controllers_dict[f"crop_start {slot}"]
                crop_end_zctrl = processor.controllers_dict[f"crop_end {slot}"]
                if file_zctrl.value:
                    file.write("<region>\n")
                    file.write(f"sample={file_zctrl.path}\n")
                    file.write(f"key={slot + 1}\n")
                    file.write(f"volume={gain_zctrl.value}\n")
                    #file.write(f"offset={crop_start_zctrl.value}\n")
                    #file.write(f"end={crop_end_zctrl.value}\n")
                    file.write(f"\n")
        self.lscp_send_single(processor, f"LOAD INSTRUMENT '{filename}' 0 0")

    def send_controller_value(self, zctrl):
        if zctrl.symbol == "slot":
            slot = zctrl.value - 1
            filename = zctrl.processor.controllers_dict[f"file {slot}"].value
            if filename:
                # Sample file loaded so populate sample maniluation controls
                self._ctrl_screens = [
                    [f"sample {slot + 1}", [f"slot", f"file {slot}", f"gain {slot}", f"warp {slot}"]],
                    [f"waveform {slot + 1}", [f"beats {slot}", f"mode {slot}"]] #, f"crop_start {slot}", f"crop_end {slot}"]]
                ]
            else:
                self._ctrl_screens = [[f"sample {slot + 1}", [f"slot", f"file {slot}"]]]
            zctrl.processor.init_ctrl_screens()
            zynsigman.send_queued(zynsigman.S_GUI, zynsigman.SS_GUI_CONTROL_MODE, mode='control')
            return
        try:
            slot = int(zctrl.symbol.split(" ")[1])
            beats_zctrl = zctrl.processor.controllers_dict[f"beats {slot}"]
            mode_zctrl = zctrl.processor.controllers_dict[f"mode {slot}"]
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
            self.set_file(zctrl.processor, slot, True)
            self.send_controller_value(zctrl.processor.controllers_dict["slot"])
            sequence = zctrl.processor.midi_chan + zynseq.LAUNCHER_COLS * slot
            self.zynseq.rebuild_launcher_info(sequence)
        elif zctrl.symbol.startswith("warp"):
            self.set_file(zctrl.processor, slot)
        elif zctrl.symbol.startswith("mode"):
            self.set_mode(zctrl.processor, slot, zctrl.value)
        elif zctrl.symbol.startswith("crop"):
            self.set_file(zctrl.processor, slot)

        self.write_sfz(zctrl.processor)

    def set_mode(self, processor, slot, mode):
        # mode: 0=disabled. 1=loop. 2..25=play 1..24
        sequence = processor.midi_chan + slot * zynseq.LAUNCHER_COLS
        match mode:
            case 0:
                self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0001)

            case 1:
                self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0101)
                self.libseq.setFollowAction(self.zynseq.bank, sequence, zynseq.FOLLOW_ACTION_LOOP, 0)
            case _:
                self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x01 | ((mode - 1) << 8))
                self.libseq.setFollowAction(self.zynseq.bank, sequence, zynseq.FOLLOW_ACTION_NONE, 0)
        self.zynseq.rebuild_launcher_info(sequence)

    def set_file(self, processor, slot, reset=False):
        file_zctrl = processor.controllers_dict[f"file {slot}"]
        warp_zctrl = processor.controllers_dict[f"warp {slot}"]
        beats_zctrl = processor.controllers_dict[f"beats {slot}"]
        sequence = processor.midi_chan + slot * zynseq.LAUNCHER_COLS
        path = file_zctrl.value

        if path:
            # Open file and get frames and samplerate
            data, sr = soundfile.read(path)
            if len(data) < 100 or sr < 100:
                return
            frames = len(data)
            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.launcher_info[slot][zynseq.SCENE_LAUNCHER_COL]["tempo"]
            if not tempo:
                tempo = self.zynseq.get_tempo()
            regptn = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(regptn, filename)
            try:
                file_tempo = int(matches[0])
            except:
                file_tempo = tempo
            
            zctrl_crop_start = processor.controllers_dict[f"crop_start {slot}"]
            zctrl_crop_end = processor.controllers_dict[f"crop_end {slot}"]
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
                #beats_per_bar = self.libseq.getBeatsPerBar()
                beats_per_bar = self.zynseq.launcher_info[slot][zynseq.SCENE_LAUNCHER_COL]["bpb"]
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
                    if self.libseq.getPlayState(self.zynseq.bank, sequence):
                        reconnect = True
                        self.lscp_send_single(processor, "REMOVE CHANNEL MIDI_INPUT 0 0 0")
                        # Silence existing audio
                        if self.libseq.getPlayState(self.zynseq.bank, processor.midi_chan + slot * zynseq.LAUNCHER_COLS):
                            self.lscp_send_single(processor, "SEND CHANNEL MIDI_DATA CC 0 120 0")
                    # Do warp
                    data, sr = soundfile.read(path)
                    data = pyrubberband.time_stretch(data, sr, factor)
                    path = f"/tmp/clippy_{processor.midi_chan}_{sequence}.flac"
                    soundfile.write(path, data, sr)
                else:
                    try:
                        data, sr = soundfile.read(path)
                        os.remove(f"/tmp/clippy{processor.midi_chan}_{sequence}.flac")
                    except:
                        pass
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
                pattern = self.libseq.getPattern(self.zynseq.bank, sequence, 0, 0)
                self.libseq.selectPattern(pattern)
                self.libseq.clearPattern(pattern)
                self.libseq.setStepsPerBeat(1)
                self.libseq.setBeatsInPattern(pattern, whole_beats)
                self.libseq.addNote(0, slot + 1, 100, 1, 0.0)
                #self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0100)
                state = self.libseq.getPlayState(self.zynseq.bank, sequence)
                self.libseq.updateSequenceInfo()
                self.libseq.setChannel(self.zynseq.bank, sequence, 0, processor.midi_chan)
                self.zynseq.set_sequence_name(self.zynseq.bank, sequence, os.path.splitext(filename)[0])
                if reconnect:
                    # Reconnect MIDI
                    self.lscp_send_single(processor, "ADD CHANNEL MIDI_INPUT 0 0 0")
                    self.lscp_send_single(processor, f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {slot} => {e}")
        else:
            self.libseq.setPlayState(self.zynseq.bank, sequence, zynseq.SEQ_STOPPED)
            state = zynseq.SEQ_STOPPED
            self.reset_pattern(processor, slot)

        file_zctrl.path = path
        self.zynseq.rebuild_launcher_info(sequence)
        processor.init_ctrl_screens()

    def on_tempo(self, tempo):
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = Timer(0.5, self.on_tempo_cb)
        self.tempo_cb_timer.start()

    def on_tempo_cb(self):
        if self.tempo_cb_timer:
            self.tempo_cb_timer.cancel()
        self.tempo_cb_timer = None
        do_warp = False
        for processor in self.processors:
            for slot in range(self.zynseq.slots):
                warp_zctrl = processor.controllers_dict[f"warp {slot}"]
                if warp_zctrl.value:
                    self.set_file(processor, slot)
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
            self.lscp_send_single(processor, f"SEND CHANNEL MIDI_DATA NOTE_OFF 0 {note} 0")
            #logging.warning(f"TODO: Send MIDI note off to chan: {chan} note: {note}")

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

        processor.controllers_dict = {f"slot": zynthian_controller(self, f"slot", {
                    "is_integer": True,
                    "value": 2, #TODO: This lets subsequence set_slot work, unless there are only 1 slots
                    "value_min": 1,
                    "value_max": self.zynseq.slots,
                    "processor": processor
                })}

        for slot in range(self.zynseq.slots):
            self.insert_proc_slot(processor, slot)
            self.reset_pattern(processor, slot)
        self.set_slot(processor, 0)

        # Create a stop sequence that runs if playing pattern toggled.
        sequence = processor.midi_chan + 1
        pattern = self.libseq.getPattern(0, sequence, 0, 0)
        if pattern == 4294967295:
            pattern = self.libseq.createPattern()
            self.libseq.addPattern(0, sequence, 0, 0, pattern, True)
        self.libseq.selectPattern(pattern)
        self.libseq.clearPattern(pattern)
        self.libseq.setStepsPerBeat(1)
        self.libseq.setBeatsInPattern(pattern, 1)
        self.libseq.addNote(0, 0, 100, 1, 0.0)
        self.libseq.updateSequenceInfo()
        self.libseq.setChannel(0, sequence, 0, processor.midi_chan)
        self.libseq.setPlayMode(0, sequence, 0x0100)
        self.libseq.setFollowAction(0, sequence, zynseq.FOLLOW_ACTION_NONE, 0)
        self.zynseq.set_sequence_name(0, sequence, "silence")
        processor.stop_seq = sequence

        self.zynseq.rebuild_all_launcher_info() # Need to do this (again!!!) here because called too early when adding chain (before processor is added)

    def remove_processor(self, processor):
        try:
            self.lscp_send_single(processor, "RESET")
            processor.proc.terminate()
            processor.proc = None
            super().remove_processor(processor)
        except Exception as err:
            logging.error("Can't stop processor")

    def reset_pattern(self, processor, slot):
            sequence = processor.midi_chan + slot * zynseq.LAUNCHER_COLS
            self.libseq.clearSequence(self.zynseq.bank, sequence)
            #pattern = self.libseq.getPatternAt(self.zynseq.bank, sequence, 0, 0)
            #if pattern == 4294967295:
            #    pattern = self.libseq.createPattern()
            #    self.libseq.addPattern(self.zynseq.bank, sequence, 0, 0, pattern, True)
            #self.libseq.clearPattern(pattern)
            #self.libseq.setStepsPerBeat(1)
            #self.libseq.setBeatsInPattern(pattern, 1)
            self.libseq.setRepeat(self.zynseq.bank, sequence, 0)
            self.libseq.updateSequenceInfo()
            self.zynseq.set_sequence_name(self.zynseq.bank, sequence, "")

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
