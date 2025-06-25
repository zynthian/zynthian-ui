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

    # ---------------------------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------------------------

    def __init__(self, state_manager=None, jackname=None):
        super().__init__(state_manager)
        self.zynseq = state_manager.zynseq
        self.libseq = state_manager.zynseq.libseq
        self.name = "Clippy"
        self.nickname = "CL"
        self.type = "MIDI Synth"
        self.options['replace'] = False

        if jackname:
            self.jackname = jackname
        else:
            self.jackname = self.state_manager.chain_manager.get_next_jackname("clippy")

        #self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"

        self.slots = 0
        self._ctrls = []
        self._ctrl_screens = []

        self.tempo_cb_timer = None

        self.sr = zynautoconnect.get_jackd_samplerate()
        if not os.path.exists("/tmp/silence.wav"):
            soundfile.write("/tmp/silence.wav", [0.0], self.sr)

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
                self.command_env['PWD'] = self.command_cwd
            # Setting cwd is because we've set PWD above. Some engines doesn't
            # care about the process's cwd, but it is more consistent to set
            # cwd when PWD has been set.
            processor.proc = Popen(processor.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                                text=True, bufsize=1, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
            zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)

        except Exception as err:
            logging.error(f"Can't start engine {self.name} => {err}")

    def stop(self):
        #TODO: How do we stop a single processor?
        for processor in self.processors:
            try:
                zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)
                logging.info("Stopping Engine " + self.name)
                processor.proc.terminate()
                processor.proc = None
            except Exception as err:
                logging.error(
                    "Can't stop engine {} => {}".format(self.name, err))

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
        parts = result.split('[')
        if len(parts) > 1:
            parts = parts[1].split(']')
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
            parts = line.split('[')
            if len(parts) > 1:
                parts = parts[1].split(']')
                result = int(parts[0])
            else:
                result = None
            self.state_manager.end_busy("clippy")
            return result
        elif line[0:3] == "ERR":
            parts = line.split(':')
            self.state_manager.end_busy("clippy")
            raise zyngine_lscp_error(
                "{} ({} {})".format(parts[2], parts[0], parts[1]))
        elif line[0:3] == "WRN":
            parts = line.split(':')
            self.state_manager.end_busy("clippy")
            raise zyngine_lscp_warning(
                "{} ({} {})".format(parts[2], parts[0], parts[1]))

    def insert_slot(self, slot):
        for processor in self.processors:
            max_slot = 1
            # Get symbols to move
            symbols = []
            for symbol in processor.controllers_dict.keys():
                idx = int(symbol[-2:]) - 1
                if idx >= slot:
                    symbols.append(symbol)
                if idx >= max_slot:
                    max_slot = idx + 1

            # Create new zctrls
            zctrls = {
                f"file {slot + 1:02}": zynthian_controller(self, f"file {slot + 1:02}", {
                    'is_path': True,
                    'value_default': "",
                    'path_file_types': ['wav', 'ogg', 'mp3', 'flac', 'aac'],
                    'processor': processor
                }),
                f"warp {slot + 1:02}": zynthian_controller(self, f"warp {slot + 1:02}", {
                    'processor': processor,
                    'is_toggle': True,
                    'labels': ["off", "on"],
                    'value': "on"
                }),
                f"beats {slot + 1:02}": zynthian_controller(self, f"beats {slot + 1:02}", {
                    'processor': processor,
                    'is_integer': True,
                    'value_min': 0,
                    'value_max': MAX_BEATS
                })
            }

            # Move zctrls
            for symbol in symbols:
                zctrl = processor.controllers_dict.pop(symbol)
                idx = int(symbol[-2:]) + 1
                new_symbol = f"{symbol[:-2]}{idx}"
                zctrl.symbol = new_symbol
                zctrls[symbol] = zctrl
            processor.controllers_dict.update(zctrls)

            # Update screens
            self._ctrl_screens = []
            for idx in range(1, max_slot + 1):
                cfg = [f'file {idx:02}']
                if processor.controllers_dict[f"file {idx:02}"].value:
                    cfg.append(f'warp {idx:02}')
                    cfg.append(f'beats {idx:02}')
                self._ctrl_screens.append([f'sample {idx:02}', cfg])
            processor.init_ctrl_screens()
            self.slots += 1


    def set_slots(self, slots):
        if self.slots == slots:
            return

        # Add missing slots
        for slot in range(self.slots, slots + 1):
            self.insert_slot(slot)

    # ---------------------------------------------------------------------------
    # Controller Management
    # ---------------------------------------------------------------------------

    def write_sfz(self, processor):
        filename = f"/tmp/clippy_{processor.id}.sfz"
        with open(filename, "w") as file:
            file.write("<global>\n")
            #file.write("ampeg_release=0.01\n")  # Fast fade to reduce risk of clicks
            file.write("loop_mode=one_shot\n") # Loop whilst key pressed
            """
            file.write("<region>\n")
            file.write(f"sample=/tmp/silence.wav\n")
            file.write(f"key=0\n")
            file.write(f"\n")
            """
            for slot in range(self.slots):
                file_zctrl = processor.controllers_dict[f"file {slot+1:02}"]
                beats_zctrl = processor.controllers_dict[f"beats {slot+1:02}"]
                if file_zctrl.value:
                    file.write("<region>\n")
                    file.write(f"sample={file_zctrl.path}\n")
                    file.write(f"key={slot}\n")
                    file.write(f"\n")
        self.lscp_send_single(processor, f"LOAD INSTRUMENT '{filename}' 0 0")

    def send_controller_value(self, zctrl):
        try:
            slot = int(zctrl.symbol.split(" ")[1]) - 1
            beats_zctrl = zctrl.processor.controllers_dict[f"beats {slot + 1:02}"]
        except Exception as e:
            logging.error(f"Can't determine sample index {zctrl.symbol} => {e}")
            return
        if zctrl.symbol.startswith("file"):
            if zctrl.value == 0 or zctrl.value == "0":
                zctrl.value = ""   # TODO: This should be fixed in zctrl class
            beats_zctrl.value = 0
            self.set_file(zctrl.processor, slot)
        elif zctrl.symbol.startswith("warp"):
            self.set_file(zctrl.processor, slot)
        self.write_sfz(zctrl.processor)

    def set_file(self, processor, slot):
        file_zctrl = processor.controllers_dict[f"file {slot + 1:02}"]
        warp_zctrl = processor.controllers_dict[f"warp {slot + 1:02}"]
        beats_zctrl = processor.controllers_dict[f"beats {slot + 1:02}"]
        sequence = self.sequence_offset + slot * zynseq.LAUNCHER_COLS
        self._ctrl_screens[slot] = [f'sample {slot + 1:02}', [f'file {slot + 1:02}']]
        path = file_zctrl.value

        if path:
            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.launcher_info[slot][zynseq.SCENE_LAUNCHER_COL]["tempo"]
            if not tempo:
                tempo = self.zynseq.get_tempo()
            pattern = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(pattern, filename)
            duration = zynaudioplayer.get_file_duration(path)
            if not duration:
                return
            try:
                file_tempo = int(matches[0])
            except:
                file_tempo = tempo

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
                        if self.libseq.getPlayState(self.zynseq.bank, self.sequence_offset + slot * zynseq.LAUNCHER_COLS):
                            self.lscp_send_single(processor, "SEND CHANNEL MIDI_DATA CC 0 120 0")
                    # Do warp
                    data, sr = soundfile.read(path)
                    data = pyrubberband.time_stretch(data, sr, factor)
                    path = f"/tmp/clippy_{processor.id}_{sequence}.flac"
                    soundfile.write(path, data, sr)
                else:
                    try:
                        os.remove(f"/tmp/clippy{processor.id}_{sequence}.flac")
                    except:
                        pass
                if bpm_match:
                    #TODO: Remove this when finished design - don't need to show user that warp is not changing file
                    warp_zctrl.labels = ["off", f"{tempo:.1f}*\nBPM"]
                else:
                    warp_zctrl.labels = ["off", f"{tempo:.1f}\nBPM"]
                if can_warp:
                    self._ctrl_screens[slot] = [f'sample {slot + 1:02}', [f'file {slot + 1:02}', f'warp {slot + 1:02}', f'beats {slot + 1:02}']]
                    beats_zctrl.value = whole_beats
                    beats_zctrl.set_readonly(warp_zctrl.value != 0)
                else:
                    beats_zctrl.value = 0
                    warp_zctrl.value = 0
                file_zctrl.path = path

                # Setup zynseq pattern & sequence
                pattern = self.libseq.getPattern(self.zynseq.bank, sequence, 0, 0)
                self.libseq.selectPattern(pattern)
                self.libseq.clearPattern(pattern)
                self.libseq.setStepsPerBeat(pattern, 1)
                self.libseq.setBeatsInPattern(pattern, whole_beats)
                self.libseq.addNote(0, slot, 100, 1, 0.0)
                #self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0100)
                state = self.libseq.getPlayState(self.zynseq.bank, sequence)
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_name(self.zynseq.bank, sequence, os.path.splitext(filename)[0])
                if reconnect:
                    # Reconnect MIDI
                    self.lscp_send_single(processor, "ADD CHANNEL MIDI_INPUT 0 0 0")
                    self.lscp_send_single(processor, f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")
                self.libseq.setRepeat(self.zynseq.bank, sequence, 1)
                self.zynseq.rebuild_launcher_info(sequence)
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {slot} => {e}")
        else:
            self.libseq.setRepeat(self.zynseq.bank, self.sequence_offset + slot * zynseq.LAUNCHER_COLS, 0)
            state = self.libseq.getPlayState(self.zynseq.bank, sequence)
            #self.reset_pattern(slot)

        zynsigman.send(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE,
                       bank=self.zynseq.bank, seq=sequence, state=state, mode=0x0100, group=processor.midi_chan)
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
            for slot in range(self.slots):
                warp_zctrl = processor.controllers_dict[f"warp {slot + 1:02}"]
                if warp_zctrl.value:
                    self.set_file(processor, slot)
                    do_warp = True
        if do_warp:
            self.write_sfz(processor)

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        super().add_processor(processor)
        self.set_slots(self.zynseq.slots)

        processor.lscp_port = ServerPort["clippy"] + processor.id
        processor.command = ["linuxsampler", "--lscp-port", str(processor.lscp_port)]
        self.start(processor)
        self.lscp_connect(processor)
        self.ls_init(processor)
        ls_chan_id = self.lscp_send_single(processor, "ADD CHANNEL")
        self.lscp_send_single(processor, "LOAD ENGINE SFZ 0")
        self.lscp_send_single(processor, "SET CHANNEL AUDIO_OUTPUT_DEVICE 0 0")
        self.lscp_send_single(processor, "ADD CHANNEL MIDI_INPUT 0 0 0")
        self.lscp_send_single(processor, f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")

        self.sequence_offset = processor.midi_chan

        for slot in range(self.slots):
            self.reset_pattern(slot)
        self.zynseq.rebuild_all_launcher_info() # Need to do this (again!!!) here because called too early when adding chain (before processor is added)

    def reset_pattern(self, slot):
            pattern = self.libseq.getPatternAt(255, self.sequence_offset + slot * zynseq.LAUNCHER_COLS, 0, 0)
            self.libseq.clearPattern(pattern)
            self.libseq.setStepsPerBeat(pattern, 1)
            self.libseq.setBeatsInPattern(pattern, 1)
            self.libseq.setRepeat(self.zynseq.bank, self.sequence_offset + slot * zynseq.LAUNCHER_COLS, 0)
            self.libseq.updateSequenceInfo()

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

            # Global volume level
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
