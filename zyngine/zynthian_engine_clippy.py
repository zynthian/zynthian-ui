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

import logging
import socket
from time import sleep
from subprocess import Popen, STDOUT, PIPE

from . import zynthian_engine
from zynconf import ServerPort
from zyncoder.zyncore import lib_zyncore

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
        self.name = "Clippy"
        self.nickname = "CL"
        self.type = "MIDI Synth"
        self.options['replace'] = False

        if jackname:
            self.jackname = jackname
        else:
            self.jackname = self.state_manager.chain_manager.get_next_jackname("clippy")

        #self.custom_gui_fpath = "/zynthian/zynthian-ui/zyngui/zynthian_widget_audioplayer.py"

        # MIDI Controllers
        self._ctrls = []
        for i in range(1, 9):
            self._ctrls.append(
                [
                    f"sample {i}", {
                        'is_path': True,
                        #'path_dir_names': ['/zynthian/zynthian-my-data/files/Samples'],
                        #'path_file_types': ['wav', 'ogg', 'mp3', 'flac', 'aac']
                    }
                ]
            )

        # Controller Screens
        self._ctrl_screens = [
            ['samples 1-4', ['sample 1', 'sample 2', 'sample 3', 'sample 4']],
            ['samples 5-8', ['sample 5', 'sample 6', 'sample 7', 'sample 8']]
        ]

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
            for i, zctrl in enumerate(self.processors[0].controllers_dict.values()):
                if zctrl.value and zctrl.value != '0':
                    file.write("<region>\n")
                    file.write(f"sample={zctrl.value and zctrl.value}\n")
                    file.write(f"key={48 + i}")
                    file.write(f"\n")
        self.lscp_send_single(f"LOAD INSTRUMENT '/tmp/clippy.sfz' 0 0")

    def send_controller_value(self, zctrl):
        if zctrl.symbol.startswith("sample"):
            self.write_sfz()

    # ---------------------------------------------------------------------------
    # Processor Management
    # ---------------------------------------------------------------------------

    def add_processor(self, processor):
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

    # ---------------------------------------------------------------------------
    # MIDI Channel Management
    # ---------------------------------------------------------------------------

    # ---------------------------------------------------------------------------
    # Bank Management
    # ---------------------------------------------------------------------------

    def get_bank_list(self, processor=None):
        return self.get_bank_dirlist(recursion=2)

    def set_bank(self, processor, bank):
        return True

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
            self.lscp_send_single("SET VOLUME 0.45")

        except zyngine_lscp_error as err:
            logging.error(err)
        except zyngine_lscp_warning as warn:
            logging.warning(warn)

    # ---------------------------------------------------------------------------
    # API methods
    # ---------------------------------------------------------------------------


# ******************************************************************************
