#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI config Class
# 
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
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
import re
import logging
from time import sleep
from threading import Thread
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Mini class to allow use of audio_in gui
# ------------------------------------------------------------------------------


class aubio_inputs():
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.audio_in = state_manager.aubio_in

    def toggle_audio_in(self, input):
        if input in self.audio_in:
            self.audio_in.remove(input)
        else:
            self.audio_in.append(input)
        self.state_manager.aubio_in = self.audio_in
        zynautoconnect.request_audio_connect()

# ------------------------------------------------------------------------------
# Zynthian MIDI config GUI Class
# ------------------------------------------------------------------------------

ZMIP_MODE_CONTROLLER = "⌨" #\u2328
ZMIP_MODE_ACTIVE = "⇥" #\u21e5
ZMIP_MODE_MULTI = "⇶" #\u21f6


class zynthian_gui_midi_config(zynthian_gui_selector):

    def __init__(self):
        self.chain = None      # Chain object
        self.input = True      # True to process MIDI inputs, False for MIDI outputs
        self.thread = None
        super().__init__('MIDI Devices', True)

    def build_view(self):
        # Enable background scan for MIDI devices
        self.midi_scan = True
        self.thread = Thread(target=self.process_dynamic_ports, name="MIDI port scan")
        self.thread.start()
        return super().build_view()

    def hide(self):
        if self.shown:
            self.midi_scan = False
            self.thread = None
            super().hide()

    def set_chain(self, chain):
        self.chain = chain
        self.set_select_path()

    def fill_list(self):
        """Populate data list used for display and configuration.
        Different display mode for admin view (no chain) and chain view (i/o routing)
        List of lists, each consisting of elements based on the display mode and entry type.
        
        Elements in jack port:
        0: Port UID (or service name if service disabled)
        0: For services this is the name of function to start/stop service
        1: ZMIP/ZMOP index on None if not connected
        2: Display text
        """

        self.list_data = []

        def get_mode_str(idev):
            mode_str = ""
            """Get input mode prefix"""
            if self.input:
                if zynautoconnect.get_midi_in_dev_mode(idev):
                    mode_str += ZMIP_MODE_ACTIVE
                else:
                    mode_str += ZMIP_MODE_MULTI
                if idev in self.zyngui.state_manager.ctrldev_manager.drivers:
                    mode_str += f" {ZMIP_MODE_CONTROLLER}"
            if mode_str:
                mode_str += " "
            return mode_str

        def append_port(idev):
            """Add a port to list"""
            if self.input:
                port = zynautoconnect.devices_in[idev]
                mode = get_mode_str(idev)
                if self.chain is None:
                    self.list_data.append((port.aliases[0], idev, f"{mode}{port.aliases[1]}"))
                elif not self.zyngui.state_manager.ctrldev_manager.is_input_device_available_to_chains(idev):
                    self.list_data.append((port.aliases[0], idev, f"    {mode}{port.aliases[1]}"))
                else:
                    if lib_zyncore.zmop_get_route_from(self.chain.zmop_index, idev):
                        self.list_data.append((port.aliases[0], idev, f"\u2612 {mode}{port.aliases[1]}"))
                    else:
                        self.list_data.append((port.aliases[0], idev, f"\u2610 {mode}{port.aliases[1]}"))
            else:
                port = zynautoconnect.devices_out[idev]
                if self.chain is None:
                    self.list_data.append((port.aliases[0], idev, f"{port.aliases[1]}"))
                elif port.aliases[0] in self.chain.midi_out:
                    self.list_data.append((port.aliases[0], idev, f"\u2612 {port.aliases[1]}"))
                else:
                    self.list_data.append((port.aliases[0], idev, f"\u2610 {port.aliases[1]}"))

        def append_service_device(dev_name, obj):
            """Add service (that is also a port) to list"""
            if isinstance(obj, int):
                if self.input:
                    port = zynautoconnect.devices_in[obj]
                else:
                    port = zynautoconnect.devices_out[obj]
                if port:
                    mode = get_mode_str(obj)
                    self.list_data.append((f"stop_{dev_name}", obj, f"\u2612 {mode}{port.aliases[1]}"))
            else:
                self.list_data.append((f"start_{dev_name}", None, f"\u2610 {obj}"))

        def atoi(text):
            return int(text) if text.isdigit() else text

        def natural_keys(t):
            return [atoi(c) for c in re.split(r'(\d+)', t[0].lower())]

        # Lists of zmop/zmip indicies
        int_devices = []    # Internal MIDI ports
        usb_devices = []    # USB MIDI ports
        ble_devices = []    # BLE MIDI ports
        aubio_devices = []  # Aubio MIDI ports
        net_devices = {}    # Network MIDI ports, indexed by jack port name
        for i in range(zynautoconnect.max_num_devs):
            if self.input:
                dev = zynautoconnect.devices_in[i]
            else:
                dev = zynautoconnect.devices_out[i]
            if dev and len(dev.aliases) > 1:
                if dev.aliases[0].startswith("USB:"):
                    usb_devices.append((dev.aliases[1], i))
                elif dev.aliases[0].startswith("BLE:"):
                    ble_devices.append((dev.aliases[1], i))
                elif dev.aliases[0].startswith("AUBIO:"):
                    aubio_devices.append(i)
                elif dev.aliases[0].startswith("NET:"):
                    net_devices[dev.name] = i
                else:
                    int_devices.append(i)
        if int_devices:
            self.list_data.append((None, None, "Internal Devices"))
            for i in int_devices:
                append_port(i)

        if usb_devices:
            self.list_data.append((None, None, "USB Devices"))
            for x in sorted(usb_devices, key=natural_keys):
                append_port(x[1])

        if self.chain is None or ble_devices:
            self.list_data.append((None, None, "Bluetooth Devices"))
            if zynthian_gui_config.bluetooth_enabled:
                if self.chain is None:
                    self.list_data.append(("stop_bluetooth", None, "\u2612 BLE MIDI"))
                for x in sorted(ble_devices, key=natural_keys):
                    append_port(x[1])
            elif self.chain is None:
                self.list_data.append(("start_bluetooth", None, "\u2610 BLE MIDI"))

        if not self.chain or net_devices:
            self.list_data.append((None, None, "Network Devices"))
            if self.chain:
                for i in net_devices.values():
                    append_port(i)
            else:
                if os.path.isfile("/usr/local/bin/jacknetumpd"):
                    if "jacknetumpd:netump_in" in net_devices:
                        append_service_device("jacknetumpd", net_devices["jacknetumpd:netump_in"])
                    elif "jacknetumpd:netump_out" in net_devices:
                        append_service_device("jacknetumpd", net_devices["jacknetumpd:netump_out"])
                    else:
                        append_service_device("jacknetumpd", "NetUMP: MIDI 2.0")

                if os.path.isfile("/usr/local/bin/jackrtpmidid"):
                    if "jackrtpmidid:rtpmidi_in" in net_devices:
                        append_service_device("jackrtpmidid", net_devices["jackrtpmidid:rtpmidi_in"])
                    elif "jackrtpmidid:rtpmidi_out" in net_devices:
                        append_service_device("jackrtpmidid", net_devices["jackrtpmidid:rtpmidi_out"])
                    else:
                        append_service_device("jackrtpmidid", "RTP-MIDI")

                if os.path.isfile("/usr/local/bin/qmidinet"):
                    if "QmidiNet:in_1" in net_devices:
                        append_service_device("QmidiNet", net_devices["QmidiNet:in_1"])
                    elif "QmidiNet:out_1" in net_devices:
                        append_service_device("QmidiNet", net_devices["QmidiNet:out_1"])
                    else:
                        append_service_device("QmidiNet", "QmidiNet")

                if os.path.isfile("/zynthian/venv/bin/touchosc2midi"):
                    if "RtMidiIn Client:TouchOSC Bridge" in net_devices:
                        append_service_device("touchosc", net_devices["RtMidiIn Client:TouchOSC Bridge"])
                    elif "RtMidiOut Client:TouchOSC Bridge" in net_devices:
                        append_service_device("touchosc", net_devices["RtMidiOut Client:TouchOSC Bridge"])
                    else:
                        append_service_device("touchosc", "TouchOSC Bridge")

        if self.input:
            if not self.chain or zynthian_gui_config.midi_aubionotes_enabled:
                self.list_data.append((None, None, "Aubionotes Audio\u2794MIDI"))
                if self.chain:
                    for i in aubio_devices:
                        append_port(i)
                else:
                    if aubio_devices:
                        append_service_device("aubionotes", aubio_devices[0])
                    else:
                        append_service_device("aubionotes", "Aubionotes")

        if not self.input and self.chain:
            self.list_data.append((None, None, "> Chain inputs"))
            for i, chain_id in enumerate(self.zyngui.chain_manager.ordered_chain_ids):
                chain = self.zyngui.chain_manager.get_chain(chain_id)
                if chain and chain.is_midi() and chain != self.chain:
                    if self.zyngui.chain_manager.will_midi_howl(self.zyngui.chain_manager.active_chain_id, chain_id):
                        prefix = "∞ "
                    else:
                        prefix = ""
                    if chain_id in self.chain.midi_out:
                        self.list_data.append((chain_id, None, f"\u2612 {prefix}{chain.get_name()}"))
                    else:
                        self.list_data.append((chain_id, None, f"\u2610 {prefix}{chain.get_name()}"))

        super().fill_list()

    def select_action(self, i, t='S'):
        if t == 'S':
            action = self.list_data[i][0]
            wait = 2  # Delay after starting service to allow jack ports to update
            if action == "stop_jacknetumpd":
                self.zyngui.state_manager.stop_netump(wait=wait)
            elif action == "start_jacknetumpd":
                self.zyngui.state_manager.start_netump(wait=wait)
            elif action == "stop_jackrtpmidid":
                self.zyngui.state_manager.stop_rtpmidi(wait=wait)
            elif action == "start_jackrtpmidid":
                self.zyngui.state_manager.start_rtpmidi(wait=wait)
            elif action == "stop_QmidiNet":
                self.zyngui.state_manager.stop_qmidinet(wait=wait)
            elif action == "start_QmidiNet":
                self.zyngui.state_manager.start_qmidinet(wait=wait)
            elif action == "stop_touchosc":
                self.zyngui.state_manager.stop_touchosc2midi(wait=wait)
            elif action == "start_touchosc":
                self.zyngui.state_manager.start_touchosc2midi(wait=wait)
            elif action == "stop_aubionotes":
                self.zyngui.state_manager.stop_aubionotes(wait=wait)
            elif action == "start_aubionotes":
                self.zyngui.state_manager.start_aubionotes(wait=wait)
            elif action == "stop_bluetooth":
                self.zyngui.state_manager.stop_bluetooth(wait=wait)
            elif action == "start_bluetooth":
                self.zyngui.state_manager.start_bluetooth(wait=wait)
            # Route/Unroute
            elif self.chain:
                idev = self.list_data[i][1]
                if self.input:
                    if not self.zyngui.state_manager.ctrldev_manager.is_input_device_available_to_chains(idev):
                        return
                    lib_zyncore.zmop_set_route_from(self.chain.zmop_index, idev, not lib_zyncore.zmop_get_route_from(self.chain.zmop_index, idev))
                else:
                    try:
                        if idev is not None:
                            dev_id = zynautoconnect.get_midi_out_dev(idev).aliases[0]
                            self.chain.toggle_midi_out(dev_id)
                        elif isinstance(action, int):
                            self.chain.toggle_midi_out(action)
                    except Exception as e:
                        logging.error(e)
                self.update_list()

        # Change mode
        elif t == 'B':
            idev = self.list_data[i][1]
            if idev is None:
                return
            try:
                options = {}
                if self.input:
                    options["MIDI Input Mode"] = None
                    if zynautoconnect.get_midi_in_dev_mode(idev):
                        options[f'\u2610 {ZMIP_MODE_ACTIVE} Multitimbral mode '] = "MULTI"
                    else:
                        options[f'\u2612 {ZMIP_MODE_MULTI} Multitimbral mode '] = "ACTI"

                    options["Configuration"] = None
                    dev_id = zynautoconnect.get_midi_in_devid(idev)
                    if dev_id in self.zyngui.state_manager.ctrldev_manager.available_drivers:
                        # TODO: Offer list of profiles
                        if idev in self.zyngui.state_manager.ctrldev_manager.drivers:
                            options[f"\u2612 {ZMIP_MODE_CONTROLLER} Controller driver"] = "UNLOAD_DRIVER"
                        else:
                            options[f"\u2610 {ZMIP_MODE_CONTROLLER} Controller driver"] = "LOAD_DRIVER"
                    port = zynautoconnect.devices_in[idev]
                else:
                    port = zynautoconnect.devices_out[idev]
                if self.list_data[i][0].startswith("AUBIO:") or self.list_data[i][0].endswith("aubionotes"):
                    options["Select aubio inputs"] = "AUBIO_INPUTS"
                options[f"Rename port '{port.aliases[0]}'"] = port
                #options[f"Reset name to '{zynautoconnect.build_midi_port_name(port)[1]}'"] = port
                self.zyngui.screens['option'].config("MIDI Input Device", options, self.menu_cb)
                self.zyngui.show_screen('option')
            except:
                pass  # Port may have disappeared whilst building menu

    def menu_cb(self, option, params):
        try:
            if option.startswith("Rename port"):
                self.zyngui.show_keyboard(self.rename_device, params.aliases[1])
                return
            elif option.startswith("Reset name"):
                zynautoconnect.set_port_friendly_name(params)
            elif params == "LOAD_DRIVER":
                self.zyngui.state_manager.ctrldev_manager.load_driver(self.list_data[self.index][1], True)
            elif params == "UNLOAD_DRIVER":
                self.zyngui.state_manager.ctrldev_manager.unload_driver(self.list_data[self.index][1], True)
            elif params == "AUBIO_INPUTS":
                ain = aubio_inputs(self.zyngui.state_manager)
                self.zyngui.screens['audio_in'].set_chain(ain)
                self.zyngui.show_screen('audio_in')
            elif self.input:
                idev = self.list_data[self.index][1]
                lib_zyncore.zmip_set_flag_active_chain(idev, params == "ACTI")
                zynautoconnect.update_midi_in_dev_mode(idev)
            self.update_list()
        except:
            pass  # Ports may have changed since menu opened

    def process_dynamic_ports(self):
        """Process dynamically added/removed MIDI devices"""

        if self.input:
            last_fingerprint = zynautoconnect.get_hw_src_ports()
        else:
            last_fingerprint = zynautoconnect.get_hw_dst_ports()

        while self.midi_scan:
            if self.input:
                fingerprint = zynautoconnect.get_hw_src_ports()
            else:
                fingerprint = zynautoconnect.get_hw_dst_ports()
            if last_fingerprint != fingerprint:
                last_fingerprint = fingerprint
                self.update_list()
            
            sleep(2)  # Repeat every 2s

    def rename_device(self, name):
        """Set the friendly name of selected
        
        name : New friendly name
        """

        if self.input:
            port = zynautoconnect.devices_in[self.list_data[self.index][1]]
        else:
            port = zynautoconnect.devices_out[self.list_data[self.index][1]]
        zynautoconnect.set_port_friendly_name(port, name)
        self.update_list()

    def set_select_path(self):
        if self.chain:
            if self.input:
                self.select_path.set(f"Capture MIDI from...")
            else:
                self.select_path.set(f"Send MIDI to ...")
        else:
            if self.input:
                self.select_path.set(f"MIDI Input Devices")
            else:
                self.select_path.set(f"MIDI Output Devices")

# ------------------------------------------------------------------------------
