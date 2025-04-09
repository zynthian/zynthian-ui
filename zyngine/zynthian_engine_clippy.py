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
NUM_SPLICES = 128 // zynseq.MIN_LAUNCHER_SLOTS # Quantity of slices to split audio to spread across pattern

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
                    'value_default': "",
                    'value': "",
                    'path_file_types': ['wav', 'ogg', 'mp3', 'flac', 'aac']
                }
            ])
            self._ctrls.append([
                f"warp {i:02}", {
                    'is_toggle': True,
                    'labels': ["off", "on"]
                }
            ])
            self._ctrls.append([
                f"beats {i:02}", {
                    "is_integer": True,
                    "value_min": 0,
                    "value_max": MAX_BEATS
                }
            ])

            # Controller Screens
            self._ctrl_screens.append([
                f'sample {i:02}',
                [f'file {i:02}']
            ])

        self.patterns = []
        self.tempo_cb_timer = None

        self.sr = zynautoconnect.get_jackd_samplerate()
        if not os.path.exists("/tmp/silence.wav"):
            soundfile.write("/tmp/silence.wav", [0.0], self.sr)

        self.slot_info = []
        for i in range(zynseq.MIN_LAUNCHER_SLOTS):
            self.slot_info.append(
                {
                    "path": "",
                    "frames": 0
                }
            )

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
                zynsigman.register_queued(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)

            except Exception as err:
                logging.error(f"Can't start engine {self.name} => {err}")

    def stop(self):
        if self.proc:
            try:
                zynsigman.unregister(zynsigman.S_STEPSEQ, zynseq.SS_TEMPO, self.on_tempo)
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
            """
            file.write("<region>\n")
            file.write(f"sample=/tmp/silence.wav\n")
            file.write(f"key=0\n")
            file.write(f"\n")
            """
            for slot in range(zynseq.MIN_LAUNCHER_SLOTS):
                file_zctrl = self.processors[0].controllers_dict[f"file {slot+1:02}"]
                beats_zctrl = self.processors[0].controllers_dict[f"beats {slot+1:02}"]
                if file_zctrl.value:
                    if beats_zctrl.value:
                        for splice in range(NUM_SPLICES):
                            file.write("<region>\n")
                            file.write(f"sample={file_zctrl.path}\n")
                            file.write(f"key={slot * NUM_SPLICES + splice}\n")
                            file.write(f"offset={int(splice * self.slot_info[slot]['frames'] / NUM_SPLICES)}\n")
                            file.write(f"end={int((splice + 1) * self.slot_info[slot]['frames'] / NUM_SPLICES) - 1}\n")
                            file.write(f"\n")
                    else:
                        file.write("<region>\n")
                        file.write(f"sample={file_zctrl.path}\n")
                        file.write(f"key={slot * NUM_SPLICES}\n")
                        file.write(f"\n")
        self.lscp_send_single(f"LOAD INSTRUMENT '/tmp/clippy.sfz' 0 0")

    def send_controller_value(self, zctrl):
        try:
            slot = int(zctrl.symbol.split(" ")[1]) - 1
            beats_zctrl = self.processors[0].controllers_dict[f"beats {slot + 1:02}"]
        except Exception as e:
            logging.error(f"Can't determine sample index {zctrl.symbol} => {e}")
            return
        if zctrl.symbol.startswith("file"):
            if zctrl.value == 0 or zctrl.value == "0":
                zctrl.value = ""   # TODO: This should be fixed in zctrl class
            beats_zctrl.value = 0
            self.set_file(slot, zctrl.value)
        elif zctrl.symbol.startswith("warp"):
            self.set_file(slot, zctrl.processor.controllers_dict[f"file {slot + 1:02}"].value)
        self.write_sfz()

    def set_file(self, slot, path):
        processor = self.processors[0]
        file_zctrl = processor.controllers_dict[f"file {slot + 1:02}"]
        warp_zctrl = processor.controllers_dict[f"warp {slot + 1:02}"]
        beats_zctrl = processor.controllers_dict[f"beats {slot + 1:02}"]
        sequence = self.sequence_offset + slot
        self.slot_info[slot]["path"] = path
        self._ctrl_screens[slot] = [f'sample {slot + 1:02}', [f'file {slot + 1:02}']]

        if path:
            # Try to determine tempo from filename
            filename = os.path.basename(path)
            tempo = self.zynseq.launcher_info[slot][zynseq.SCENE_LAUNCHER_COL]["tempo"]
            if not tempo:
                tempo = self.zynseq.get_tempo()
            pattern = r"(\d+)\s*(?=bpm|BPM)"
            matches = re.findall(pattern, filename)
            duration = zynaudioplayer.get_file_duration(path)
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
                        self.lscp_send_single("REMOVE CHANNEL MIDI_INPUT 0 0 0")
                        # Silence existing audio
                        if self.libseq.getPlayState(self.zynseq.bank, self.sequence_offset + slot):
                            self.lscp_send_single("SEND CHANNEL MIDI_DATA CC 0 120 0")
                    # Do warp
                    data, sr = soundfile.read(path)
                    data = pyrubberband.time_stretch(data, sr, factor)
                    path = f"/tmp/clippy{sequence}.flac"
                    soundfile.write(path, data, sr)
                else:
                    try:
                        os.remove(f"/tmp/clippy{sequence}.flac")
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
                self.slot_info[slot]["frames"] = soundfile.info(path).frames

                # Setup zynseq pattern & sequence
                pattern = self.libseq.getPattern(self.zynseq.bank, sequence, 0, 0)
                self.libseq.selectPattern(pattern)
                self.libseq.clearPattern(pattern)
                self.libseq.setStepsPerBeat(pattern, 1)
                self.libseq.setBeatsInPattern(pattern, whole_beats)
                if beats_zctrl.value:
                    note_len = whole_beats // NUM_SPLICES
                    for pos in range(NUM_SPLICES):
                        self.libseq.addNote(note_len * pos, NUM_SPLICES * slot + pos, 100, 1, 0.0)
                else:
                    self.libseq.addNote(0, NUM_SPLICES * slot, 100, 1, 0.0)
                #self.libseq.setPlayMode(self.zynseq.bank, sequence, 0x0100)
                state = self.libseq.getPlayState(self.zynseq.bank, sequence)
                self.libseq.updateSequenceInfo()
                self.zynseq.set_sequence_name(self.zynseq.bank, sequence, os.path.splitext(filename)[0])
                if reconnect:
                    # Reconnect MIDI
                    self.lscp_send_single("ADD CHANNEL MIDI_INPUT 0 0 0")
                    self.lscp_send_single(f"SET CHANNEL MIDI_INPUT_CHANNEL 0 {processor.midi_chan}")
                self.libseq.setRepeat(self.zynseq.bank, self.sequence_offset + slot, 1)
            except Exception as e:
                logging.error(f"Can't setup sequencer for clip {slot} => {e}")
        else:
            self.libseq.setRepeat(self.zynseq.bank, self.sequence_offset + slot, 0)
            state = self.libseq.getPlayState(self.zynseq.bank, sequence)
            #self.reset_pattern(slot)

        zynsigman.send(zynsigman.S_STEPSEQ, zynseq.SS_SEQ_PLAY_STATE,
                       bank=self.zynseq.bank, seq=sequence, state=state, mode=0x0100, group=self.processors[0].midi_chan)
        self.processors[0].init_ctrl_screens()

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
        for slot in range(zynseq.MIN_LAUNCHER_SLOTS):
            warp_zctrl = self.processors[0].controllers_dict[f"warp {slot + 1:02}"]
            if warp_zctrl.value:
                path = self.processors[0].controllers_dict[f"file {slot + 1:02}"].value
                self.set_file(slot, path)
                do_warp = True
        if do_warp:
            self.write_sfz()

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

        for slot in range(8):
            self.reset_pattern(slot)

    def reset_pattern(self, slot):
            pattern = self.libseq.getPatternAt(255, self.sequence_offset + slot, 0, 0)
            self.libseq.clearPattern(pattern)
            self.libseq.setStepsPerBeat(pattern, 1)
            self.libseq.setBeatsInPattern(pattern, 1)
            self.libseq.setRepeat(self.zynseq.bank, self.sequence_offset + slot, 0)
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
            """
            self.lscp_send_single(
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 0 NAME='out_l'")
            self.lscp_send_single(
                f"SET AUDIO_OUTPUT_CHANNEL_PARAMETER {self.ls_audio_device_id} 1 NAME='out_r'")
            """

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
