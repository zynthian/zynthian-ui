#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian Core
#
# Zynthian Audio Recorder Class
#
# Copyright (C) 2015-2022 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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
from subprocess import Popen
from datetime import datetime

# Zynthian specific modules
from zyngine.zynthian_signal_manager import zynsigman
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian Audio Recorder Class
# ------------------------------------------------------------------------------


class zynthian_audio_recorder:

    # Subsignals are defined inside each module. Here we define audio_recorder subsignals:
    SS_AUDIO_RECORDER_STATE = 1
    SS_AUDIO_RECORDER_ARM = 2

    capture_dir_sdc = os.environ.get('ZYNTHIAN_MY_DATA_DIR', "/zynthian/zynthian-my-data") + "/capture"
    ex_data_dir = os.environ.get('ZYNTHIAN_EX_DATA_DIR', "/media/root")

    def __init__(self, state_manager):
        self.rec_proc = None
        self.status = False
        self.state_manager = state_manager
        self.filename = None

    def get_new_filename(self):
        exdirs = zynthian_gui_config.get_external_storage_dirs(self.ex_data_dir)
        if exdirs:
            path = exdirs[0]
            filename = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        else:
            path = self.capture_dir_sdc
            filename = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        if self.state_manager.last_snapshot_fpath and len(self.state_manager.last_snapshot_fpath) > 4:
            filename += "_" + os.path.basename(self.state_manager.last_snapshot_fpath[:-4])
        filename = filename.replace("/", ";").replace(">", ";").replace(" ; ", ";")
        return "{}/{}.wav".format(path, filename)

    def start_recording(self, processor=None):
        if self.rec_proc:
            # Already recording
            return False

        cmd = ["/usr/local/bin/jack_capture", "--daemon", "--bitdepth", "16", "--bufsize", "30", "--maxbufsize", "120"]
        single_chan = True
        for chain in self.state_manager.chain_manager.chains.values():
            if chain.zynmixer_proc and chain.zynmixer_proc.controllers_dict["record"].value:
                single_chan = False
                if chain.zynmixer_proc.eng_code == "MI":
                    port = f"zynmixer_chan:output_{chain.zynmixer_proc.mixer_chan:02d}"
                else:
                    port = f"zynmixer_bus:output_{chain.zynmixer_proc.mixer_chan:02d}"
                cmd.append("--port")
                cmd.append(f"{port}a")
                cmd.append("--port")
                cmd.append(f"{port}b")
        if single_chan:
            cmd.append("--port")
            cmd.append("zynmixer_bus:output_00a")
            cmd.append("--port")
            cmd.append("zynmixer_bus:output_00b")

        self.filename = self.state_manager.get_new_capture_fpath("wav")
        cmd.append(self.filename)

        logging.info(f"STARTING NEW AUDIO RECORD '{self.filename}'...")
        # logging.debug(f"COMMAND => {cmd}")
        try:
            self.rec_proc = Popen(cmd)
        except Exception as e:
            logging.error(f"ERROR STARTING AUDIO RECORD => {e}")
            logging.error(f"COMMAND => {cmd}")
            self.rec_proc = None
            return False

        self.status = True
        zynsigman.send(zynsigman.S_AUDIO_RECORDER, self.SS_AUDIO_RECORDER_STATE, state=True)

        # Should this be implemented using signals?
        if processor:
            processor.controllers_dict['record'].set_value("recording", False)

        return True

    def stop_recording(self, player=None):
        if self.rec_proc:
            logging.info("STOPPING AUDIO RECORD ...")
            try:
                self.rec_proc.terminate()
                self.rec_proc = None
            except Exception as e:
                logging.error("ERROR STOPPING AUDIO RECORD: %s" % e)
                return False

            self.status = False
            zynsigman.send(zynsigman.S_AUDIO_RECORDER, self.SS_AUDIO_RECORDER_STATE, state=False)

            # Should this be implemented using signals? => YES!!
            #if player is None:
            #    self.state_manager.audio_player.engine.load_latest(self.state_manager.audio_player)
            #else:
            #    self.state_manager.audio_player.engine.load_latest(player)

            self.state_manager.sync = True
            return True

        return False

    def toggle_recording(self, player=None):
        logging.info("TOGGLING AUDIO RECORDING ...")
        if self.status:
            self.stop_recording(player)
            return False
        else:
            self.start_recording(player)
            return True

# ------------------------------------------------------------------------------
