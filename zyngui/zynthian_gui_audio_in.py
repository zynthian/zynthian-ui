#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio-In Selector Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
from time import sleep

# Zynthian specific modules
import zynautoconnect
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info

# ------------------------------------------------------------------------------
# Zynthian Audio-In Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_audio_in(zynthian_gui_selector_info):

    def __init__(self):
        self.chain = None
        super().__init__('Audio In')

    def set_chain(self, chain):
        self.chain = chain

    def build_view(self):
        self.check_ports = 0
        self.capture_ports = zynautoconnect.get_audio_capture_ports()
        return super().build_view()

    def refresh_status(self):
        super().refresh_status()
        self.check_ports += 1
        if self.check_ports > 10:
            self.check_ports = 0
            ports = zynautoconnect.get_audio_capture_ports()
            if self.capture_ports != ports:
                self.capture_ports = ports
                self.fill_list()

    def fill_list(self):
        self.list_data = []

        for i, scp in enumerate(self.capture_ports):
            if scp.aliases:
                suffix = f" ({scp.aliases[0]})"
            else:
                suffix = ""
            if i + 1 in self.chain.audio_in:
                self.list_data.append(
                    (i + 1, scp.name, f"\u2612 Audio input {i + 1}{suffix}",
                    [f"Audio input {i + 1} is connected to this chain.", "audio_input.png"]))
            else:
                self.list_data.append(
                    (i + 1, scp.name, f"\u2610 Audio input {i + 1}{suffix}", 
                    [f"Audio input {i + 1} is disconnected from this chain.", "audio_input.png"]))

        super().fill_list()

    def fill_listbox(self):
        super().fill_listbox()

    def select_action(self, i, t='S'):
        if t == 'S':
            self.chain.toggle_audio_in(self.list_data[i][0])
            self.fill_list()
        elif t == "B":
            if not self.list_data[i][1].startswith("system:"):
                return
            self.zyngui.state_manager.start_busy("alsa_input", "Getting audio level parameters...")
            sleep(0.1)
            ctrl_list = []
            try:
                sel_chan = int(self.list_data[i][1].split("_")[-1]) - 1
                zctrls = self.zyngui.state_manager.alsa_mixer_processor.engine.get_controllers_dict()
                for symbol, zctrl in zctrls.items():
                    if zctrl.graph_path[4]:
                        chan = zctrl.graph_path[1]
                    else:
                        chan = zctrl.graph_path[2]
                    if chan == sel_chan:
                        ctrl_list.append(symbol)
                    sleep(0.01)
            except:
                pass
            self.zyngui.state_manager.end_busy("alsa_input")
            if ctrl_list:
                self.zyngui.show_screen("alsa_mixer", params=ctrl_list)

    def set_select_path(self):
        self.select_path.set("Capture Audio from ...")

# ------------------------------------------------------------------------------
