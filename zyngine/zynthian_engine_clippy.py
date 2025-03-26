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
import math
import socket
import logging
from time import sleep
import soundfile, pyrubberband
from subprocess import Popen, STDOUT, PIPE

from zynlibs.zynseq import zynseq
from zynlibs.zynaudioplayer import zynaudioplayer
from zyngine.zynthian_signal_manager import zynsigman

from . import zynthian_engine
from zynconf import ServerPort

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

        self._ctrls = []
        self._ctrl_screens = []
        for i in range(1, 9):
            # MIDI Controllers
            self._ctrls.append([
                f"file {i:02}", {
                    'is_path': True,
                    'path_file_types': ['wav', 'ogg', 'mp3', 'flac', 'aac']
                }
            ])
            self._ctrls.append([
                f"bars {i:02}", {
                    'is_integer': True,
                    'value_min': 1,
                    'value_max': 32,
                    'value': 4
                }
            ])
            # Controller Screens
            self._ctrl_screens.append([
                f'sample {i:02}',
                [f'file {i:02}', f'bars {i:02}']
            ])

        self.patterns = []

        if not os.path.exists("/tmp/silence.wav"):
            soundfile.write("/tmp/silence.wav", [0.0], 48000)

    # ---------------------------------------------------------------------------
    # Subproccess Management & IPC
    # ---------------------------------------------------------------------------

    def start(self):
        if not self.proc:
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
                self.proc = Popen(self.command, env=self.command_env, cwd=self.command_cwd, shell=False,
                                  text=True, bufsize=1, stdout=PIPE, stderr=STDOUT, stdin=PIPE)
            except Exception as err:
                logging.error(f"Can't start engine {self.name} => {err}")

    def stop(self):
        if self.proc:
            try:
                logging.info("Stopping Engine " + self.name)
                self.proc.terminate()
                self.proc = None
            except Exception as err:
                logging.error(
                    "Can't stop engine {} => {}".format(self.name, err))

    def lscp_connect(self):
        logging.info("Connecting with LinuxSampler Server...")
        self.state_manager.start_busy("clippy")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(False)
        self.sock.settimeout(1)
        i = 0
        while i < 20:
            try:
                self.sock.connect(("127.0.0.1", self.lscp_port))
                break
            except:
                sleep(0.25)
                i += 1
        return self.sock

    def lscp_get_result_index(self, result):
        parts = result.split('[')
        if len(parts) > 1:
            parts = parts[1].split(']')
            return int(parts[0])

    def lscp_send_single(self, command):
        # logging.debug("LSCP SEND => %s" % command)
        command = command + "\r\n"
        try:
            self.sock.send(command.encode())
            line = self.sock.recv(4096)
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

    # ---------------------------------------------------------------------------
    # Controller Management
    # ---------------------------------------------------------------------------

    def write_sfz(self):
        with open("/tmp/clippy.sfz", "w") as file:
            file.write("<global>\n")
            #file.write("ampeg_release=0.01\n")  # Fast fade to reduce risk of clicks
            file.write("loop_mode=one_shot\n") # Loop whilst key pressed
            file.write("<region>\n")
            file.write(f"sample=/tmp/silence.wav\n")
            file.write(f"key=36\n")
            file.write(f"\n")
            for i in range(1, 9):
                zctrl = self.processors[0].controllers_dict[f"file {i:02}"]
                if zctrl.value:
                    file.write("<region>\n")
                    file.write(f"sample={zctrl.value}\n")
                    file.write(f"key={47 + i}\n")
                    file.write(f"\n")
        self.lscp_send_single(f"LOAD INSTRUMENT '/tmp/clippy.sfz' 0 0")

    def send_controller_value(self, zctrl):
        if zctrl.symbol.startswith("file"):
            if zctrl.value == 0 or zctrl.value == "0":
                zctrl.value = ""   # TODO: This should be fixed in zctrl class
            try:
                sample_i = int(zctrl.symbol.split(" ")[1]) - 1
                sequence = self.sequence_offset + sample_i
            except Exception as e:
                sample_i = None
                logging.error(f"Can't determine sample index {zctrl.symbol} => {e}")

            if zctrl.value and sample_i is not None:
                logging.debug(f"SETTING UP SAMPLE '{zctrl.symbol}' ({sample_i}) => {zctrl.value} ...")

                self.write_sfz()

                logging.debug(f"SETTING UP SAMPLE '{zctrl.symbol}' ({sample_i}) => sequence & pattern info ...")
                try:
                    mode = zynseq.SEQ_LOOPALL
                    tempo = self.zynseq.get_tempo()
                    spb = 60 / tempo
                    duration = zynaudioplayer.get_file_duration(zctrl.value)
                    beats = round(duration / spb)
                    """
                    factor = round(beats) / beats
                    filename = os.path.basename(zctrl.value)
                    data, sr = soundfile.read(zctrl.value)
                    data = pyrubberband.time_stretch(data, sr, factor)
                    path = f"/tmp/{filename}"
                    soundfile.write(path, data, sr)"
                    """

                    logging.debug(f"\tDuration = {duration}s => {beats} beats")

                    #bpb = self.libseq.getBeatsPerBar()
                    # Setup zynseq pattern & sequence
                    pattern = self.libseq.getPattern(zynseq.LAUNCHER_SEQ_BANK, sequence, 0, 0)
                    self.libseq.selectPattern(pattern)
                    self.libseq.clear()
                    steps_per_beat = self.libseq.getStepsPerBeat()
                    self.libseq.setBeatsInPattern(beats)
                    self.libseq.addNote(0, 48 + sample_i, 100, 1, 0.0)
                    self.libseq.setPlayMode(zynseq.LAUNCHER_SEQ_BANK, sequence, mode)
                    state = self.libseq.getPlayState(zynseq.LAUNCHER_SEQ_BANK, sequence)
                    group = self.libseq.getGroup(zynseq.LAUNCHER_SEQ_BANK, sequence)
                    self.libseq.updateSequenceInfo()

                except Exception as e:
                    logging.error(f"Can't setup sequencer for clip {sample_i} => {e}")
            else:
                mode = zynseq.SEQ_DISABLED
                self.reset_pattern(sample_i)

            zynsigman.send(zynsigman.S_STEPSEQ, self.zynseq.SS_SEQ_PLAY_STATE,
                           bank=zynseq.LAUNCHER_SEQ_BANK, seq=sequence, state=state, mode=mode, group=group)

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
        if self.processors:
            return # Only support single processor
        super().add_processor(processor)
        self.lscp_port = ServerPort["clippy"] + processor.id
        self.command = ["linuxsampler", "--lscp-port", str(self.lscp_port)]
        self.start()
        self.lscp_connect()
        self.ls_init()
        ls_chan_id = self.lscp_send_single("ADD CHANNEL")
        self.lscp_send_single("LOAD ENGINE SFZ 0")
        self.lscp_send_single("SET CHANNEL AUDIO_OUTPUT_DEVICE 0 0")
        self.lscp_send_single("ADD CHANNEL MIDI_INPUT 0 0 0")
        self.lscp_send_single(f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")

        self.sequence_offset = processor.midi_chan * 8

        for i in range(8):
            pattern = self.libseq.getPatternAt(255, self.sequence_offset + i, 0, 0)
            self.patterns.append(pattern)
            self.reset_pattern(i)

    def reset_pattern(self, slot):
            pattern = self.patterns[slot]
            self.libseq.selectPattern(pattern)
            self.libseq.clear()
            self.libseq.setStepsPerBeat(1)
            self.libseq.setBeatsInPattern(1)
            self.libseq.addNote(0, 36, 100, 1, 0)
            self.libseq.setPlayMode(zynseq.LAUNCHER_SEQ_BANK, self.sequence_offset + slot, zynseq.SEQ_ONESHOT)
            self.libseq.updateSequenceInfo()


    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    #def get_bank_list(self, processor=None):
    #    return self.get_bank_dirlist(recursion=2)

    #def set_bank(self, processor, bank):
    #    return True

    # ---------------------------------------------------------------------------
    # Preset Management
    # ---------------------------------------------------------------------------

    #def get_preset_list(self, bank):
    #    return self._get_preset_list(bank)

    #def set_preset(self, processor, preset, preload=False):
    #    return False

    # ---------------------------------------------------------------------------
    # Specific functions
    # ---------------------------------------------------------------------------

    def ls_init(self):
        try:
            # Reset
            self.lscp_send_single("RESET")

            # Config Audio JACK Device 0
            self.ls_audio_device_id = self.lscp_send_single(
                f"CREATE AUDIO_OUTPUT_DEVICE JACK ACTIVE='true' CHANNELS='2' NAME='{self.jackname}'")
            self.lscp_send_single(
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 0 NAME='out_l'")
            self.lscp_send_single(
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 1 NAME='out_r'")

            # Config MIDI JACK Device 1
            self.ls_midi_device_id = self.lscp_send_single(
                f"CREATE MIDI_INPUT_DEVICE JACK ACTIVE='true' NAME='{self.jackname}' PORTS='1'")

            # Global volume level
            self.lscp_send_single("SET VOLUME 0.95")
            self.lscp_send_single("SET VOICES 1")

        except zyngine_lscp_error as err:
            logging.error(err)
        except zyngine_lscp_warning as warn:
            logging.warning(warn)

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------


# ******************************************************************************
