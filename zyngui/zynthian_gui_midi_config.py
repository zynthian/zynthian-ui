#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI MIDI-In Selector Class
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
from collections import OrderedDict
from threading import Timer
from subprocess import check_output, Popen, PIPE
from time import sleep

# Zynthian specific modules
import zynconf
import zynautoconnect
from zyncoder.zyncore import lib_zyncore
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian MIDI-In Selection GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_midi_config(zynthian_gui_selector):

    def __init__(self):
        self.chain = None # Chain object
        self.idev = None # Index of midi device in autoconnect devices
        self.ble_devices = {} # Map of BLE MIDI device configs indexed by BLE address
        self.input = True # True to process MIDI inputs, False for MIDI outputs
        super().__init__('MIDI Devices', True)

    def set_chain(self, chain):
        self.chain = chain
        self.set_select_path()
        try:
            #TODO: This looks wrong!
            self.idev = int(chain.chain_id) - 1
        except:
            self.idev = None

    def fill_list(self):
        self.list_data = []

        def get_mode(i):
            # Check mode (Acti/Omni/Multi)
            if not self.input:
                return ""
            if i in self.zyngui.state_manager.ctrldev_manager.drivers:
                return "↻ " #\u21bb
            elif lib_zyncore.zmip_get_flag_active_chan(i):
                return "↦ " #\u2a16
            elif lib_zyncore.zmip_get_flag_omni_chan(i):
                return "∈ " #\u2208
            else:
                return "⇶ " #\u21f6

        def append_device(i):
            if self.input:
                port = zynautoconnect.devices_in[i]
                mode = get_mode(i)
                if self.chain is None:
                    self.list_data.append((port.aliases[0], i, f"{mode}{port.aliases[1]}", port))
                elif i in self.zyngui.state_manager.ctrldev_manager.drivers:
                    self.list_data.append((port.aliases[0], i, f"    {mode}{port.aliases[1]}", port))
                else:
                    if lib_zyncore.zmop_get_route_from(self.idev , i):
                        self.list_data.append((port.aliases[0], i, f"\u2612 {mode}{port.aliases[1]}", port))
                    else:
                        self.list_data.append((port.aliases[0], i, f"\u2610 {mode}{port.aliases[1]}", port))
            else:
                port = zynautoconnect.devices_out[i]
                if self.chain is None:
                    self.list_data.append((port.aliases[0], i, f"{port.aliases[1]}", port))
                elif port.name in self.chain.midi_out:
                    self.list_data.append((port.name, i, f"\u2612 {port.aliases[1]}", port))
                else:
                    self.list_data.append((port.name, i, f"\u2610 {port.aliases[1]}", port))

        def append_service_device(dev_name, obj):
            if isinstance(obj, int):
                if self.input:
                    port = zynautoconnect.devices_in[obj]
                else:
                    port = zynautoconnect.devices_out[obj]
                if port:
                    mode = get_mode(obj)
                    self.list_data.append((f"stop_{dev_name}", True, f"\u2612 {mode}{port.aliases[1]}", port))
            else:
                self.list_data.append((f"start_{dev_name}", None, f"\u2610 {obj}"))

        int_devices = []
        usb_devices = []
        ble_devices = []
        aubio_devices = []
        net_devices = {}
        for i in range(zynautoconnect.max_num_devs):
            if self.input:
                dev = zynautoconnect.devices_in[i]
            else:
                dev = zynautoconnect.devices_out[i]
            if dev and dev.aliases:
                if dev.aliases[0].startswith("USB:"):
                    usb_devices.append(i)
                elif dev.aliases[0].startswith("BLE:"):
                    ble_devices.append(i)
                elif dev.aliases[0].startswith("AUBIO:"):
                    aubio_devices.append(i)
                elif dev.aliases[0].startswith("NET:"):
                    net_devices[dev.name] = i
                else:
                    int_devices.append(i)
        if int_devices:
            self.list_data.append((None, None, "Internal Devices"))
            for i in int_devices:
                append_device(i)

        if usb_devices:
            self.list_data.append((None, None, "USB Devices"))
            for i in usb_devices:
                append_device(i)

        if not self.chain or zynthian_gui_config.bluetooth_enabled and ble_devices:
            self.list_data.append((None, None, "Bluetooth Devices"))
            if zynthian_gui_config.bluetooth_enabled:
                if not self.chain:
                    self.list_data.append(("stop_bluetooth", None, "\u2612 BLE MIDI"))
                if self.chain:
                    for i in ble_devices:
                        append_device(i)
                else:
                    for addr, data in self.ble_devices.items():
                        #[name, paired, trusted, connected]
                        if data[2]:
                            title = "\u2612 "
                        else:
                            title = "\u2610 "
                        if data[3]:
                            title += "\uf293 "
                        title += data[0]
                        self.list_data.append(("ble_device", addr, title))
            elif not self.chain:
                self.list_data.append(("start_bluetooth", None, "\u2610 BLE MIDI"))

        if not self.chain or net_devices:
            self.list_data.append((None, None, "Network Devices"))
            if self.chain:
                for i in net_devices.values():
                    append_device(i)
            else:
                if "jackrtpmidid:rtpmidi_in" in net_devices:
                    append_service_device("jackrtpmidid", net_devices["jackrtpmidid:rtpmidi_in"])
                elif "jackrtpmidid:rtpmidi_out" in net_devices:
                    append_service_device("jackrtpmidid", net_devices["jackrtpmidid:rtpmidi_out"])
                else:
                    append_service_device("jackrtpmidid", "RTP-MIDI")

                if "QmidiNet:in_1" in net_devices:
                    append_service_device("QmidiNet", net_devices["QmidiNet:in_1"])
                elif "QmidiNet:out_1" in net_devices:
                    append_service_device("QmidiNet", net_devices["QmidiNet:out_1"])
                else:
                    append_service_device("QmidiNet", "QmidiNet")

                if "RtMidiIn Client:TouchOSC Bridge" in net_devices:
                    append_service_device("touchosc", net_devices["RtMidiIn Client:TouchOSC Bridge"])
                elif "RtMidiOut Client:TouchOSC Bridge" in net_devices:
                    append_service_device("touchosc", net_devices["RtMidiOut Client:TouchOSC Bridge"])
                else:
                    append_service_device("touchosc", "TouchOSC Bridge")

        if self.input:
            if not self.chain or zynthian_gui_config.midi_aubionotes_enabled:
                self.list_data.append((None, None, "Aubionotes Audio=>MIDI"))
                if self.chain:
                    for i in aubio_devices:
                        append_device(i)
                else:
                    if aubio_devices:
                        append_service_device("aubionotes", aubio_devices[0])
                    else:
                        append_service_device("aubionotes", "Aubionotes")

        if not self.input and self.chain:
            self.list_data.append((None, None, "Chain inputs"))
            for chain_id, chain in self.zyngui.chain_manager.chains.items():
                if chain.is_midi() and chain != self.chain:
                    if self.zyngui.chain_manager.will_route_howl(self.zyngui.chain_manager.active_chain_id, chain_id):
                        prefix = "∞"
                    else:
                        prefix = ""
                    if chain_id in self.chain.midi_out:
                        self.list_data.append((chain_id, None, f"\u2612 {prefix}Chain {chain_id}"))
                    else:
                        self.list_data.append((chain_id, None, f"\u2610 {prefix}Chain {chain_id}"))

        super().fill_list()


    def select_action(self, i, t='S'):
        if t == 'S':
            if self.list_data[i][0] == "stop_jackrtpmidid":
                self.zyngui.state_manager.stop_rtpmidi()
            elif self.list_data[i][0] == "start_jackrtpmidid":
                self.zyngui.state_manager.start_rtpmidi()
            elif self.list_data[i][0] == "stop_QmidiNet":
                self.zyngui.state_manager.stop_qmidinet()
            elif self.list_data[i][0] == "start_QmidiNet":
                self.zyngui.state_manager.start_qmidinet()
            elif self.list_data[i][0] in ("stop_RtMidiIn Client:TouchOSC Bridge", "stop_touchosc"):
                self.zyngui.state_manager.stop_touchosc2midi()
            elif self.list_data[i][0] in ("start_RtMidiIn Client:TouchOSC Bridge", "start_touchosc"):
                self.zyngui.state_manager.start_touchosc2midi()
            elif self.list_data[i][0] == "stop_aubionotes":
                self.zyngui.state_manager.stop_aubionotes()
            elif self.list_data[i][0] == "start_aubionotes":
                self.zyngui.state_manager.start_aubionotes()
            elif self.list_data[i][0] == "stop_bluetooth":
                self.zyngui.state_manager.stop_bluetooth()
            elif self.list_data[i][0] == "start_bluetooth":
                self.zyngui.state_manager.start_bluetooth()
                self.check_ble()
            elif self.list_data[i][0] == "ble_device":
                self.toggle_ble_device(self.list_data[i][1])
            # Route/Unroute
            elif self.chain:
                if self.input:
                    dev_i = self.list_data[i][1]
                    if dev_i in self.zyngui.state_manager.ctrldev_manager.drivers:
                        return
                    lib_zyncore.zmop_set_route_from(self.idev, dev_i, not lib_zyncore.zmop_get_route_from(self.idev, dev_i))
                else:
                    try:
                        self.zyngui.chain_manager.get_active_chain().toggle_midi_out(self.list_data[i][0])
                    except Exception as e:
                        logging.error(e)
                self.fill_list()

        # Change mode
        elif t == 'B' and self.list_data[i][1] is not None:
            # Check mode (Acti/Omni/Multi)
            dev_i = self.list_data[i][1]
            if self.list_data[i][0] == "ble_device":
                try:
                    check_output(['bluetoothctl', 'untrust', dev_i], encoding='utf-8', timeout=5)
                    check_output(['bluetoothctl', 'disconnect', dev_i], encoding='utf-8', timeout=5)
                    self.ble_devices.pop(dev_i)
                except:
                    pass
                self.fill_list()
                return
            options = OrderedDict()
            if self.input:
                if lib_zyncore.zmip_get_flag_active_chan(dev_i):
                    mode = 0
                elif lib_zyncore.zmip_get_flag_omni_chan(dev_i):
                    mode = 1
                else:
                    mode = 2

                options["MIDI Input Mode"] = None
                if mode == 0:
                    options[f'\u25C9 ↦ Active channel'] = "ACTI"
                else:
                    options[f'\u25CE ↦ Active channel'] = "ACTI"
                if mode == 1:
                    options[f'\u25C9 ∈ Omni mode'] = "OMNI"
                else:
                    options[f'\u25CE ∈ Omni mode'] = "OMNI"
                if mode == 2:
                    options[f'\u25C9 ⇶ Multitimbral mode '] = "MULTI"
                else:
                    options[f'\u25CE ⇶ Multitimbral mode'] = "MULTI"
                options["Configuration"] = None
                if zynautoconnect.get_midi_in_devid(dev_i) in self.zyngui.state_manager.ctrldev_manager.available_drivers:
                    #TODO: Offer list of profiles
                    if dev_i in self.zyngui.state_manager.ctrldev_manager.drivers:
                        options[f"\u2612 ↻ Enable controller driver"] = "UNLOAD_DRIVER"
                    else:
                        options[f"\u2610 ↻ Enable controller driver"] = "LOAD_DRIVER"
            options[f'Rename port {self.list_data[i][3].aliases[0]}'] = "RENAME"
            self.zyngui.screens['option'].config("MIDI Input Device", options, self.menu_cb)
            self.zyngui.show_screen('option')


    def menu_cb(self, option, params):
        if params == "RENAME":
            self.zyngui.show_keyboard(self.rename_device, self.list_data[self.index][3].aliases[1])
            return
        elif params == "LOAD_DRIVER":
            self.zyngui.state_manager.ctrldev_manager.load_driver(self.list_data[self.index][1])
        elif params == "UNLOAD_DRIVER":
            self.zyngui.state_manager.ctrldev_manager.unload_driver(self.list_data[self.index][1])
        elif self.input:
            dev_i = self.list_data[self.index][1]
            flags_acti = params == "ACTI"
            flags_omni = params == "OMNI"
            lib_zyncore.zmip_set_flag_active_chan(dev_i, flags_acti)
            lib_zyncore.zmip_set_flag_omni_chan(dev_i, flags_omni)

        self.fill_list()

    def toggle_ble_device(self, addr):
        try:
            if self.ble_devices[addr][2]:
                check_output(['bluetoothctl', 'untrust', addr], encoding='utf-8', timeout=1)
                check_output(['bluetoothctl', 'disconnect', addr], encoding='utf-8', timeout=5)
                self.ble_devices[addr][3] = False
                self.ble_devices[addr][2] = False
            else:
                check_output(['bluetoothctl', 'trust', addr], encoding='utf-8', timeout=1)
                check_output(['bluetoothctl', 'connect', addr], encoding='utf-8', timeout=5)
                self.ble_devices[addr][2] = True
            self.fill_list()
        except Exception as e:
            pass

    def check_ble(self):
        if zynthian_gui_config.bluetooth_enabled:
            try:
                proc = Popen('bluetoothctl', stdin=PIPE, stdout=PIPE, encoding='utf-8')
                proc.stdin.write('menu scan\nuuids 03B80E5A-EDE8-4B33-A751-6CE34EC4C700\nback\nscan on\n')
                proc.stdin.flush()
                sleep(5)
                proc.stdin.write('scan off\n')
                proc.stdin.flush()
            except:
                pass
            try:
                devices = check_output(['bluetoothctl', 'devices'], encoding='utf-8', timeout=0.1).split('\n')
                for device in devices:
                    if not device:
                        continue
                    addr = device.split()[1]
                    name = device[25:]
                    info = check_output(['bluetoothctl', 'info', addr], encoding='utf-8', timeout=0.1).split('\n')
                    for line in info:
                        if line.startswith('\tName:'):
                            name = line[7:]
                        if line.startswith('\tPaired:'):
                            paired = line[9:] == "yes"
                        if line.startswith('\tTrusted:'):
                            trusted = line[10:] == "yes"
                        if line.startswith('\tConnected:'):
                            connected = line[12:] == "yes"
                    self.ble_devices[addr] = [name, paired, trusted, connected]
                    if connected:
                        if trusted:
                            ports =zynautoconnect.get_ports(f"^a2j:{name} \[.*{name} Bluetooth$")
                            update = False
                            for port in ports:
                                if not port.aliases:
                                    update = True
                                    if port.is_input:
                                        port.set_alias(f"BLE:{addr}_out")
                                        port.set_alias(f"{name} OUT")
                                        logging.info(f"Adding BLE Device {addr} with name {name} OUT")
                                    else:
                                        port.set_alias(f"BLE:{addr}_in")
                                        port.set_alias(f"{name} IN")
                                        logging.info(f"Adding BLE Device {addr} with name {name} IN")
                            if update:
                                self.fill_list()
                    else:
                        check_output(['bluetoothctl', 'disconnect', addr], encoding='utf-8', timeout=5)

            except:
                pass
            Timer(2, self.check_ble).start()


    def rename_device(self, name):
        zynautoconnect.set_port_friendly_name(self.list_data[self.index][3], name)
        self.fill_list()


    def set_select_path(self):
        if self.chain:
            if self.input:
                self.select_path.set(f"Chain {self.chain.chain_id} MIDI Input")
            else:
                self.select_path.set(f"Chain {self.chain.chain_id} MIDI Output")
        else:
            if self.input:
                self.select_path.set(f"MIDI Input Devices")
            else:
                self.select_path.set(f"MIDI Output Devices")

# ------------------------------------------------------------------------------
