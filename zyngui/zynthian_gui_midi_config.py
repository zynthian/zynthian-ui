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
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info
from zyngui import zynthian_gui_config
import zynconf

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

ZMIP_MODE_SYS = "♣" # \u1
ZMIP_MODE_SYS_RT = "⏱" # \u23F1
#ZMIP_MODE_SYS_RT = "⌛" # \u231B
ZMIP_MODE_CONTROLLER = "⌨"  # \u2328
ZMIP_MODE_ACTIVE = "⇥"  # \u21e5
ZMIP_MODE_MULTI = "⇶"  # \u21f6
SERVICE_ICONS = {
    "aubionotes": "midi_audio.png"
}


class zynthian_gui_midi_config(zynthian_gui_selector_info):

    def __init__(self):
        self.chain = None      # Chain object
        self.input = True      # True to process MIDI inputs, False for MIDI outputs
        self.thread = None
        super().__init__('Menu')

    def build_view(self):
        # Enable background scan for MIDI devices
        self.midi_scan = True
        self.thread = Thread(
            target=self.process_dynamic_ports, name="MIDI port scan")
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
            """Get input mode prefix"""
            mode_str = ""
            if idev is None:
                return mode_str
            if self.input:
                if zynautoconnect.get_midi_in_dev_mode(idev):
                    mode_str += ZMIP_MODE_ACTIVE
                else:
                    mode_str += ZMIP_MODE_MULTI
                if lib_zyncore.zmip_get_flag_system(idev):
                    mode_str += f" {ZMIP_MODE_SYS}"
                if lib_zyncore.zmip_get_flag_system_rt(idev):
                    mode_str += f" {ZMIP_MODE_SYS_RT}"
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
                input_mode_info = f"\n\n{ZMIP_MODE_ACTIVE} Active mode\n"
                input_mode_info += f"{ZMIP_MODE_MULTI} Multitimbral mode\n"
                input_mode_info += f"{ZMIP_MODE_SYS} System messages\n"
                input_mode_info += f"{ZMIP_MODE_SYS_RT} Transport messages\n"
                input_mode_info += f"{ZMIP_MODE_CONTROLLER} Driver loaded"
                if self.chain is None:
                    self.list_data.append((port.aliases[0], idev, f"{mode}{port.aliases[1]}",
                                           [f"Bold select to show options for '{port.aliases[1]}'.{input_mode_info}", "midi_input.png"]))
                elif not self.zyngui.state_manager.ctrldev_manager.is_input_device_available_to_chains(idev):
                    self.list_data.append((port.aliases[0], idev, f"    {mode}{port.aliases[1]}",
                                           [f"Bold select to show options '{port.aliases[1]}'.{input_mode_info}", "midi_input.png"]))
                else:
                    if lib_zyncore.zmop_get_route_from(self.chain.zmop_index, idev):
                        self.list_data.append((port.aliases[0], idev, f"\u2612 {mode}{port.aliases[1]}",
                                               [f"'{port.aliases[1]}' connected to chain's MIDI input.\nBold select to show more options.{input_mode_info}", "midi_input.png"]))
                    else:
                        self.list_data.append((port.aliases[0], idev, f"\u2610 {mode}{port.aliases[1]}",
                                               [f"'{port.aliases[1]}' disconnected from chain's MIDI input.\nBold select to show more options.{input_mode_info}", "midi_input.png"]))
            else:
                port = zynautoconnect.devices_out[idev]
                if self.chain is None:
                    self.list_data.append((port.aliases[0], idev, f"{port.aliases[1]}",
                                           [f"Bold select to show options for '{port.aliases[1]}'.", "midi_output.png"]))
                elif port.aliases[0] in self.chain.midi_out:
                    self.list_data.append((port.aliases[0], idev, f"\u2612 {port.aliases[1]}",
                                           [f"Chain's MIDI output connected to '{port.aliases[1]}'.\nBold select to show more options.", "midi_output.png"]))
                else:
                    self.list_data.append((port.aliases[0], idev, f"\u2610 {port.aliases[1]}",
                                           [f"Chain's MIDI output disconnected from '{port.aliases[1]}'.\nBold select to show more options.", "midi_output.png"]))

        def append_service(service, name, help_info=""):
            if service in SERVICE_ICONS:
                icon = SERVICE_ICONS[service]
            else:
                icon = "midi_logo.png"
            try:
                idev = net_devices[name]
            except:
                idev = None
            if zynconf.is_service_active(service):
                mode = get_mode_str(idev)
                self.list_data.append((f"stop_{service}", idev, f"\u2612 {mode}{name}", [f"Disable {help_info}", icon]))
            else:
                self.list_data.append((f"start_{service}", idev, f"\u2610 {name}", [f"Enable {help_info}", icon]))

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
        if self.input:
            devs = zynautoconnect.devices_in
        else:
            devs = zynautoconnect.devices_out
        for i, dev in enumerate(devs):
            if dev and len(dev.aliases) > 1:
                if dev.aliases[0].startswith("USB:"):
                    usb_devices.append((dev.aliases[1], i))
                elif dev.aliases[0].startswith("BLE:"):
                    ble_devices.append((dev.aliases[1], i))
                elif dev.aliases[0].startswith("AUBIO:"):
                    aubio_devices.append(i)
                elif dev.aliases[0].startswith("NET:"):
                    # net_devices[dev.name] = i
                    port = zynautoconnect.devices_in[i]
                    puid, name = zynautoconnect.build_midi_port_name(port)
                    net_devices[name] = i
                else:
                    int_devices.append(i)

        self.list_data.append((None, None, "Internal Devices"))
        nint = len(self.list_data)

        for i in int_devices:
            append_port(i)

        if self.input:
            if not self.chain or zynthian_gui_config.midi_aubionotes_enabled:
                if self.chain:
                    for i in aubio_devices:
                        append_port(i)
                else:
                    append_service("aubionotes", "Aubionotes (Audio \u2794 MIDI)",
                                   "Aubionotes. Converts audio input to MIDI note on/off commands.")

        # Remove "Internal Devices" title if section is empty
        if len(self.list_data) == nint:
            self.list_data.pop()

        if usb_devices:
            self.list_data.append((None, None, "USB Devices"))
            for x in sorted(usb_devices, key=natural_keys):
                append_port(x[1])

        if self.chain is None or ble_devices:
            self.list_data.append((None, None, "Bluetooth Devices"))
            if self.chain is None:
                append_service("bluetooth", "BLE MIDI", "Bluetooth MIDI.")
            for x in sorted(ble_devices, key=natural_keys):
                append_port(x[1])

        if not self.chain or net_devices:
            self.list_data.append((None, None, "Network Devices"))
            if self.chain:
                for i in net_devices.values():
                    append_port(i)
            else:
                if os.path.isfile("/usr/local/bin/jacknetumpd"):
                    append_service("jacknetumpd", "NetUMP",
                                   "NetUMP. Provides MIDI over an IP connection using NetUMP protocol (MIDI 2.0).")

                if os.path.isfile("/usr/local/bin/jackrtpmidid"):
                    append_service("jackrtpmidid", "RTP MIDI",
                                   "RTP-MIDI. Provides MIDI over an IP connection using RTP-MIDI protocol (AppleMIDI).")

                if os.path.isfile("/usr/local/bin/qmidinet"):
                    append_service("qmidinet", "QmidiNet",
                                   "QmidiNet. Provides MIDI over an IP connection using UDP/IP multicast (ipMIDI).")

                if os.path.isfile("/zynthian/venv/bin/touchosc2midi"):
                    append_service("touchosc2midi", "TouchOSC",
                                   "Interface with Hexler TouchOSC modular control surface.")

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
                        self.list_data.append((chain_id, None, f"\u2612 {prefix}{chain.get_name()}",
                                              [f"Chain's MIDI output connected to chain '{prefix}{chain.get_name()}'.",
                                               "midi_output.png"]))
                    else:
                        self.list_data.append((chain_id, None, f"\u2610 {prefix}{chain.get_name()}",
                                              [f"Chain's MIDI output disconnected from chain '{prefix}{chain.get_name()}'.",
                                               "midi_output.png"]))

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
            elif action == "stop_qmidinet":
                self.zyngui.state_manager.stop_qmidinet(wait=wait)
            elif action == "start_qmidinet":
                self.zyngui.state_manager.start_qmidinet(wait=wait)
            elif action == "stop_touchosc2midi":
                self.zyngui.state_manager.stop_touchosc2midi(wait=wait)
            elif action == "start_touchosc2midi":
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
                    lib_zyncore.zmop_set_route_from(
                        self.chain.zmop_index, idev, not lib_zyncore.zmop_get_route_from(self.chain.zmop_index, idev))
                else:
                    try:
                        if idev is not None:
                            dev_id = zynautoconnect.get_midi_out_dev(
                                idev).aliases[0]
                            self.chain.toggle_midi_out(dev_id)
                        elif isinstance(action, int):
                            self.chain.toggle_midi_out(action)
                    except Exception as e:
                        logging.error(e)
                self.update_list()

        # Change mode
        elif t == 'B':
            self.show_options()

    def show_options(self):
        try:
            idev = self.list_data[self.index][1]
            if idev is None:
                return
            options = {}
            if self.input:
                options["MIDI Input Mode"] = None
                mode_info = "Toggle input mode.\n\n"
                if zynautoconnect.get_midi_in_dev_mode(idev):
                    title = f"{ZMIP_MODE_ACTIVE} Active mode"
                    if lib_zyncore.get_active_midi_chan():
                        mode_info += f"{title}. Translate MIDI channel. Send to chains matching active chain's MIDI channel."
                    else:
                        mode_info += f"{title}. Translate MIDI channel. Send to active chain only."
                    options[title] = ["MULTI", [mode_info, "midi_input.png"]]
                else:
                    title = f"{ZMIP_MODE_MULTI} Multitimbral mode"
                    mode_info += f"{title}. Don't translate MIDI channel. Send to chains matching device's MIDI channel."
                    options[title] = ["ACTI", [mode_info, "midi_input.png"]]

                options["MIDI System Messages"] = None
                mode_info = "Route non real-time system messages from this device.\n\n"
                if lib_zyncore.zmip_get_flag_system(idev):
                    title = f"\u2612 {ZMIP_MODE_SYS} Non real-time"
                    options[title] = ["SYSTEM/OFF", [mode_info, "midi_input.png"]]
                else:
                    title = f"\u2610 {ZMIP_MODE_SYS} Non real-time"
                    options[title] = ["SYSTEM/ON", [mode_info, "midi_input.png"]]

                mode_info = "Route real-time system messages from this device.\n\n"
                if lib_zyncore.zmip_get_flag_system_rt(idev):
                    title = f"\u2612 {ZMIP_MODE_SYS_RT} Transport"
                    options[title] = ["SYSTEM_RT/OFF", [mode_info, "midi_input.png"]]
                else:
                    title = f"\u2610 {ZMIP_MODE_SYS_RT} Transport"
                    options[title] = ["SYSTEM_RT/ON", [mode_info, "midi_input.png"]]

                # Reload drivers => Hot reload the driver classes!
                #self.zyngui.state_manager.ctrldev_manager.update_available_drivers(reload_modules=False)
                # Get driver list for the device (dev_id) connected to this slot (idev)
                dev_id = zynautoconnect.get_midi_in_devid(idev)
                available_drivers = self.zyngui.state_manager.ctrldev_manager.available_drivers
                loaded_drivers = self.zyngui.state_manager.ctrldev_manager.drivers
                # Get available drivers for this device ...
                device_drivers = []
                # Specific drivers
                try:
                    device_drivers += available_drivers[dev_id]
                except:
                    pass
                # Generic drivers
                if idev < lib_zyncore.zmip_get_seq_index():
                    try:
                        device_drivers += available_drivers["*"]
                    except:
                        pass
                driver_options = {}
                for i, driver_class in enumerate(device_drivers):
                    driver_name = driver_class.get_driver_name()
                    driver_description = driver_class.get_driver_description()
                    if not driver_description:
                        driver_description = "Device driver integrating UI functions and customized workflow."
                    if idev in loaded_drivers and isinstance(loaded_drivers[idev], driver_class):
                        driver_options[f"\u2612 {ZMIP_MODE_CONTROLLER} {driver_name}"] = [
                            ["UNLOAD_DRIVER", driver_class.__name__], [driver_description, "midi_input.png"]]
                    else:
                        driver_options[f"\u2610 {ZMIP_MODE_CONTROLLER} {driver_name}"] = [
                            ["LOAD_DRIVER", driver_class.__name__], [driver_description, "midi_input.png"]]
                if driver_options:
                    options["Controller Drivers"] = None
                    options.update(driver_options)

                port = zynautoconnect.devices_in[idev]

            else:
                port = zynautoconnect.devices_out[idev]

            options["Configuration"] = None
            if self.list_data[self.index][0].startswith("AUBIO:") or self.list_data[self.index][0].endswith("aubionotes"):
                options["Select aubio inputs"] = ["AUBIO_INPUTS", ["Select audio inputs to be analized and converted to MIDI.", "midi_audio.png"]]
            options[f"Rename port '{port.aliases[0]}'"] = [port, ["Rename the MIDI port.\nClear name to reset to default name.",  "midi_input.png"]]
            # options[f"Reset name to '{zynautoconnect.build_midi_port_name(port)[1]}'"] = port

            self.zyngui.screens['option'].config("MIDI Input Device", options, self.menu_cb, False, False, None)
            self.zyngui.show_screen('option')
        except Exception as e:
            #logging.error(e)
            pass  # Port may have disappeared whilst building menu

    def menu_cb(self, option, params):
        try:
            if option.startswith("Rename port"):
                self.zyngui.show_keyboard(self.rename_device, params.aliases[1])
                return
            elif option.startswith("Reset name"):
                zynautoconnect.set_port_friendly_name(params)
            elif isinstance(params, list):
                idev = self.list_data[self.index][1]
                if params[0] == "LOAD_DRIVER":
                    #logging.debug(f"LOAD DRIVER FOR {idev}")
                    self.zyngui.state_manager.ctrldev_manager.load_driver(idev, params[1])
                elif params[0] == "UNLOAD_DRIVER":
                    #logging.debug(f"UNLOAD DRIVER FOR {idev}")
                    self.zyngui.state_manager.ctrldev_manager.unload_driver(idev,True)
            elif isinstance(params, str):
                if params == "AUBIO_INPUTS":
                    ain = aubio_inputs(self.zyngui.state_manager)
                    self.zyngui.screens['audio_in'].set_chain(ain)
                    self.zyngui.show_screen('audio_in')
                    return
                elif self.input:
                    idev = self.list_data[self.index][1]
                    match params:
                        case "SYSTEM/ON":
                            lib_zyncore.zmip_set_flag_system(idev, True)
                        case "SYSTEM/OFF":
                            lib_zyncore.zmip_set_flag_system(idev, False)
                        case "SYSTEM_RT/ON":
                            lib_zyncore.zmip_set_flag_system_rt(idev, True)
                        case "SYSTEM_RT/OFF":
                            lib_zyncore.zmip_set_flag_system_rt(idev, False)
                        case "ACTI":
                            lib_zyncore.zmip_set_flag_active_chain(idev, True)
                            zynautoconnect.update_midi_in_dev_mode(idev)
                        case "MULTI":
                            lib_zyncore.zmip_set_flag_active_chain(idev, False)
                            zynautoconnect.update_midi_in_dev_mode(idev)
            self.show_options()
            self.update_list()
        except Exception as e:
            #logging.error(e)
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
        self.zyngui.close_screen("option")

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
