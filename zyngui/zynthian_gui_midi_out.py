#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-Out Selector Class
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

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
import zynconf

# ------------------------------------------------------------------------------
# Zynthian MIDI-Out Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_out(zynthian_gui_selector):

    def __init__(self):
        self.chain = None
        self.chain_manager = zynthian_gui_config.zyngui.chain_manager
        super().__init__('MIDI Output Devices', True)

    def set_chain(self, chain):
        self.chain = chain
        self.set_select_path()

    def fill_list(self):
        self.list_data = []

        def append_device(i, port):
            if self.chain is None:
                self.list_data.append((port.aliases[0], i, f"{port.aliases[1]}", port))
            elif port.name in self.chain.midi_out:
                self.list_data.append((port.name, i, f"\u2612 {port.aliases[1]}", port))
            else:
                self.list_data.append((port.name, i, f"\u2610 {port.aliases[1]}", port))

        int_devices = []
        usb_devices = []
        ble_devices = []
        for i in range(zynautoconnect.max_num_devs):
            dev = zynautoconnect.devices_out[i]
            if dev:
                if dev.aliases[0].startswith("USB:"):
                    usb_devices.append((i, dev))
                elif dev.aliases[0].startswith("BLE:"):
                    ble_devices.append((i, dev))
                else:
                    int_devices.append((i, dev))

        if int_devices:
            self.list_data.append((None, None, "Internal Devices"))
            for i in int_devices:
                append_device(i[0], i[1])
            append_device(zynautoconnect.max_num_devs + 1, zynautoconnect.get_port_from_name("ZynMaster:midi_in"))

        if usb_devices:
            self.list_data.append((None, None, "USB Devices"))
            for i in usb_devices:
                append_device(i[0], i[1])

        if ble_devices:
            self.list_data.append((None, None, "BLE Devices"))
            for i in ble_devices:
                append_device(i[0], i[1])

        self.list_data.append((None, None, "Network Devices"))
        net = False
        if zynconf.is_service_active("jackrtpmidid"):
            self.list_data.append(("stop_rtpmidi", None, "\u2612 RTP-MIDI"))
            net = True
        else:
            self.list_data.append(("start_rtpmidi", None, "\u2610 RTP-MIDI"))
        if zynconf.is_service_active("qmidinet"):
            self.list_data.append(("stop_qmidinet", None, "\u2612 QmidiNet (IP Multicast)"))
            net = True
        else:
            self.list_data.append(("start_qmidinet", None, "\u2610 QmidiNet (IP Multicast)"))
        if zynconf.is_service_active("touchosc2midi"):
            self.list_data.append(("stop_touchosc", None, "\u2612 TouchOSC MIDI Bridge"))
            net = True
        else:
            self.list_data.append(("start_touchosc", None, "\u2610 TouchOSC MIDI Bridge"))
        if net:
            append_device(zynautoconnect.max_num_devs,zynautoconnect.get_port_from_name("ZynMidiRouter:net_in"))

        if self.chain:
            self.list_data.append((None, None, "Chain inputs"))
            for chain_id, chain in self.chain_manager.chains.items():
                if chain.is_midi() and chain != self.chain:
                    if self.chain_manager.will_route_howl(self.chain_manager.active_chain_id, chain_id):
                        append_device(None, chain_id, f"∞Chain {chain_id}")
                    else:
                        append_device(None, chain_id, f"Chain {chain_id}")

        super().fill_list()

    def fill_listbox(self):
        super().fill_listbox()

    def select_action(self, i, t='S'):
        if t == 'S':
            if self.list_data[i][0] == "stop_rtpmidi":
                self.zyngui.state_manager.stop_rtpmidi()
            elif self.list_data[i][0] == "start_rtpmidi":
                self.zyngui.state_manager.start_rtpmidi()
            if self.list_data[i][0] == "stop_qmidinet":
                self.zyngui.state_manager.stop_qmidinet()
            elif self.list_data[i][0] == "start_qmidinet":
                self.zyngui.state_manager.start_qmidinet()
            if self.list_data[i][0] == "stop_touchosc":
                self.zyngui.state_manager.stop_touchosc2midi()
            elif self.list_data[i][0] == "start_touchosc":
                self.zyngui.state_manager.start_touchosc2midi()
            elif self.chain:
                try:
                    self.chain_manager.get_active_chain().toggle_midi_out(self.list_data[i][0])
                    self.fill_list()
                except Exception as e:
                    logging.error(e)
        elif t == 'B' and self.list_data[i][1] is not None:
            self.zyngui.show_keyboard(self.rename_device, self.list_data[i][3].aliases[1])


    def rename_device(self, name):
        zynautoconnect.set_port_friendly_name(self.list_data[self.index][0], name)
        self.fill_list()

    def set_select_path(self):
        if self.chain:
            self.select_path.set(f"Chain {self.chain.chain_id} MIDI Output")
        else:
            self.select_path.set("MIDI Output Devices")

# ------------------------------------------------------------------------------
