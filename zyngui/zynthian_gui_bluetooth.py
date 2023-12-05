#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Bluetooth config
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

import os
import re
import logging
import pexpect
import itertools
from time import sleep
#from time import monotonic
from threading import Thread

# Zynthian specific modules
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector
import zynautoconnect

# ------------------------------------------------------------------------------
# Zynthian Bluetooth config GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_bluetooth(zynthian_gui_selector):

    def __init__(self):
        self.ble_enabled = None
        super().__init__('Bluetooth', True)
        self.proc = None
        self.detect_flag = False
        self.detect_thread = None
        self.devices = {}
        #self.set_title("Bluetooth")
        self.remove_colour_re = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        control_chars = ''.join(map(chr, itertools.chain(range(0x00, 0x20), range(0x7f, 0xa0))))
        self.remove_ctrl_chars_re = re.compile('[%s]' % re.escape(control_chars))

    def fill_list(self):
        self.list_data = []
        if self.ble_enabled is None:
            self.list_data.append((None, 0, "Checking status ..."))
        elif self.ble_enabled:
            self.list_data.append((self.toggle_enable, 0, "[X] BLE MIDI"))
            self.list_data.append((None, 0, "> Detected devices"))
            for uuid in self.devices:
                name, trusted, connected = self.devices[uuid]
                if connected:
                    name = f"\uf293 {name}"
                if trusted:
                    self.list_data.append((self.select_device, uuid, f"[X] {name}"))
                else:
                    self.list_data.append((self.select_device, uuid, f"[  ] {name}"))
        else:
            self.list_data.append((self.toggle_enable, 0, "[  ] BLE MIDI"))
        super().fill_list()

    def select_action(self, i, t='S'):
        if self.list_data[i][0]:
            self.last_action = self.list_data[i][0]
            self.last_action(self.list_data[i][1], t)

    def toggle_enable(self, unused, t='S'):
        if self.proc and self.proc.isalive():
            self.ble_enabled = not self.ble_enabled
            self.zyngui.state_manager.start_busy("toggle bluetoothctl")
            if self.ble_enabled:
                # Bluetoothd often crashes so lets restart service here
                #os.system("systemctl restart bluetooth")
                self.proc.sendline("power on")
                self.set_uuid_filter()
                self.proc.sendline("scan on")
            else:
                self.proc.sendline("scan off")
                self.proc.sendline("power off")
            self.zyngui.state_manager.end_busy("toggle bluetoothctl")
            self.fill_list()

    def select_device(self, uuid, t='S'):
        if self.proc and self.proc.isalive():
            try:
                if t == 'B':
                    # Bold press to remove from list
                    # Clear jack port uid aliases
                    alsa_name = uuid
                    ports =zynautoconnect.get_ports(f"^a2j:{alsa_name} \[.*{alsa_name}$")
                    for port in ports:
                        for alias in port.aliases:
                            port.unset_alias(alias)

                    self.proc.sendline(f"untrust {uuid}")
                    self.proc.sendline(f"disconnect {uuid}")
                    self.proc.sendline(f"remove {uuid}")
                    del(self.devices[uuid])
                else:
                    if self.devices[uuid][1]:
                        self.proc.sendline(f"disconnect {uuid}")
                        self.proc.sendline(f"untrust {uuid}")
                        self.devices[uuid][1] = False
                    else:
                        self.proc.sendline(f"pair {uuid}")
                        self.proc.sendline(f"trust {uuid}")
                        self.proc.sendline(f"connect {uuid}")
                        self.devices[uuid][1] = True
                self.fill_list()
            except:
                pass

    def detect(self):
        parsing_device = 1
        devices = {}
        device = None
        dirty = False
        while self.detect_flag:
            if self.proc and self.proc.isalive():
                #now = monotonic()
                try:
                    line = self.proc.readline().decode('utf-8')
                    line = self.remove_colour_re.sub('', line)  # Remove colour
                    line = self.remove_ctrl_chars_re.sub('', line)  # Remove non printable chars
                    if "]#" in line:
                        line = line.split('#')[1]
                    parts = line.split()
                    #logging.debug(f"BLUTOOTHCTL LINE: {parts}")
                    if parts[0] == "Waiting":
                        # Server seems to have stopped! It does that a lot!!!
                        os.system("systemctl restart bluetooth")
                    elif parts[0] == 'Version':
                        if parsing_device == 1:
                            parsing_device = 2
                            for device in self.devices:
                                if device not in list(devices):
                                    del(self.devices[device])
                            for device in devices:
                                self.proc.sendline(f"info {device}")
                            dirty = False
                    elif parts[0] == 'Device':
                        device = parts[1]
                        if parsing_device == 1:
                            # Phase 1 of device detection
                            if device not in devices:
                                devices[device] = [device, False, False]
                        elif parsing_device == 2:
                            # Phase 2 of device detection
                            parsing_device = device
                    elif parts[0] == 'Name:':
                        devices[parsing_device][0] = line[6:]
                    elif parts[0] == 'Trusted:':
                        devices[parsing_device][1] = (parts[1] == "yes")
                    elif parts[0] == 'Connected:':
                        devices[parsing_device][2] = (parts[1] == "yes")
                        if devices[parsing_device][2] and not devices[parsing_device][1]:
                            # Should not allow connection if device not trusted (bluetoothd bug)
                            self.proc.sendline(f"disconnect {parsing_device}")
                        elif devices[parsing_device][2] and devices[parsing_device][1]:
                            # Set jack port uid aliases
                            name = devices[parsing_device][0]
                            ports =zynautoconnect.get_ports(f"^a2j:{name} \[.*{name} Bluetooth$")
                            for port in ports:
                                if not port.aliases:
                                    if port.is_input:
                                        port.set_alias(f"BLE:{parsing_device}_out")
                                        port.set_alias(f"{name} OUT")
                                    else:
                                        port.set_alias(f"BLE:{parsing_device}_in")
                                        port.set_alias(f"{name} IN")
                        parsing_device = 2
                        if device not in self.devices or self.devices[device] != devices[device]:
                            self.devices[device] = devices.pop(device)
                            dirty = True
                        if len(devices) == 0:
                            # Last device
                            if dirty:
                                self.fill_list()
                            dirty = False
                            parsing_device = 1
                    elif parts[0] == "Powered:":
                        new_state = (line.split()[1] == "yes")
                        if new_state != self.ble_enabled:
                            self.ble_enabled = new_state
                            if self.ble_enabled:
                                self.proc.sendline("scan on")
                            self.fill_list()
                    elif parts[0] == "[CHG]" and "RSSI:" not in line:
                        if parts[1] == "Device":
                            parts = line.split()
                            device = parts[2]
                            if device in self.devices:
                                if parts[3] == "Trusted:":
                                    value = (parts[4] == "yes")
                                    if self.devices[device][1] != value:
                                        self.devices[device][1] = value
                                        self.fill_list()
                                elif parts[3] == "Connected:":
                                    value = (parts[4] == "yes")
                                    if self.devices[device][2] != value:
                                        self.devices[device][2] = value
                                        self.fill_list()
                        self.proc.timeout = 1

                except pexpect.TIMEOUT:
                    # No messages received for a while so scan for devices
                    self.proc.timeout = 5
                    devices = {}
                    parsing_device = 1
                    self.proc.sendline("devices")
                    self.proc.sendline("version")

                except:
                    pass
            else:
                sleep(0.2)

    # Filter only BLE MIDI devices based on uuid profile
    def set_uuid_filter(self):
        try:
            self.proc.sendline("menu scan")
            self.proc.sendline("uuids 03B80E5A-EDE8-4B33-A751-6CE34EC4C700")
            self.proc.sendline("back")
        except:
            logging.warning("Failed to set BLE MIDI filter")

    # Show display
    def show(self):
        super().show()
        self.zyngui.state_manager.start_busy("start bluetoothctl")
        self.proc = pexpect.spawn("/usr/bin/bluetoothctl", echo=False, timeout=5)
        self.proc.delaybeforesend = 0.2
        self.set_uuid_filter()
        self.detect_flag = True
        self.detect_thread = Thread(target=self.detect, args=(), daemon=True)
        self.detect_thread.name = "Bluetooth"
        self.detect_thread.start()
        self.proc.sendline("show")
        if self.ble_enabled:
            self.proc.sendline("scan on")
        self.zyngui.state_manager.end_busy("start bluetoothctl")

    def hide(self):
        self.zyngui.state_manager.start_busy("stop bluetoothctl")
        self.detect_flag = False
        self.ble_enabled = None
        sleep(0.2)
        if self.proc and self.proc.isalive():
            self.proc.sendline("scan off")
            self.proc.sendline("exit")
            self.proc.close()
            self.proc = None
        self.zyngui.state_manager.end_busy("stop bluetoothctl")
        super().hide()

    def set_select_path(self):
        self.select_path.set("Bluetooth")

# ------------------------------------------------------------------------------
