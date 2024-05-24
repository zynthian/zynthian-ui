#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
# 
# Zynthian GUI Bluetooth config Class
# 
# Copyright (C) 2024 Fernando Moyano <jofemodo@zynthian.org>
#                    Brian Walton <brian@riban.co.uk>
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
from threading import Thread
from subprocess import check_output, Popen, PIPE

# Zynthian specific modules
from zyngui.zynthian_gui_selector import zynthian_gui_selector
from zyngui import zynthian_gui_config

# ------------------------------------------------------------------------------
# Zynthian hotplug hardware config GUI Class
# ------------------------------------------------------------------------------

class zynthian_gui_bluetooth(zynthian_gui_selector):

    def __init__(self):
        self.ble_devices = {}  # Map of BLE device configs indexed by BLE address. Config: [name, paired, trusted, connected, is_midi]
        self.ble_scan_proc = None
        super().__init__('Bluetooth Devices', True)

    def build_view(self):
        return super().build_view()

    def build_view(self):
        if zynthian_gui_config.bluetooth_enabled:
            self.enable_ble_scan()
        return super().build_view()

    def hide(self):
        if self.shown:
            self.disable_ble_scan()
            super().hide()

    def fill_list(self):
        self.list_data = []

        if zynthian_gui_config.bluetooth_enabled:
            self.list_data.append(("stop_bluetooth", None, "\u2612 Enable Bluetooth"))
            self.list_data.append((None, None, "Bluetooth Devices"))
            for addr, data in self.ble_devices.items():
                #[name, paired, trusted, connected, is_midi]
                if data[2]:
                    title = "\u2612 "
                else:
                    title = "\u2610 "
                if data[3]:
                    title += "\uf293 "
                title += data[0]
                self.list_data.append((f"BLE:{addr}", addr, title))
        else:
            self.list_data.append(("start_bluetooth", None, "\u2610 Enable Bluetooth"))

        super().fill_list()

    def select_action(self, i, t='S'):
        if t == 'S':
            action = self.list_data[i][0]
            wait = 2  # Delay after starting service to allow jack ports to update
            if action == "stop_bluetooth":
                self.disable_ble_scan()
                self.zyngui.state_manager.stop_bluetooth(wait=wait)
            elif action == "start_bluetooth":
                self.zyngui.state_manager.start_bluetooth(wait=wait)
                self.enable_ble_scan()
            else:
                self.toggle_ble_trust(self.list_data[i][0][4:])

        # Change mode
        elif t == 'B':
            if self.list_data[i][0].startswith("BLE:"):
                # Bluetooth device
                addr = self.list_data[i][0][4:]
                if addr not in self.ble_devices or not self.ble_devices[addr][2]:
                    # Not trusted so offer to remove
                    self.zyngui.show_confirm(f"Remove Bluetooth device?\n{self.list_data[i][0]}", self.remove_ble, self.list_data[i][0][4:])
                return

    def enable_ble_scan(self):
        """Enable scanning for Bluetooth devices"""

        if self.ble_scan_proc is None:
            # Start scanning and processing bluetooth
            self.ble_scan_proc = Popen('bluetoothctl', stdin=PIPE, stdout=PIPE, encoding='utf-8')
            self.ble_scan_proc.stdin.write('menu scan\nuuids 03B80E5A-EDE8-4B33-A751-6CE34EC4C700 00001812-0000-1000-8000-00805f9b34fb\nback\nscan on\n')
            self.ble_scan_proc.stdin.flush()
            # Enable background scan for MIDI devices
            Thread(target=self.process_dynamic_ports, name="BLE scan").start()

    def disable_ble_scan(self):
        """Stop scanning for Bluetooth devices"""

        if self.ble_scan_proc:
            # Stop bluetooth scanning
            self.ble_scan_proc.stdin.write('scan off\nexit\n')
            self.ble_scan_proc.stdin.flush()
            self.ble_scan_proc.terminate()
            self.ble_scan_proc = None

    def process_dynamic_ports(self):
        """Process dynamically added/removed BLE devices"""

        while self.ble_scan_proc:
            update = False
            try:
                # Get list of available BLE Devices
                devices = check_output(['bluetoothctl', 'devices'], encoding='utf-8', timeout=1.0).split('\n')
                for device in devices:
                    if not device.startswith("Device "):
                        continue
                    is_midi = False
                    addr = device.split()[1]
                    name = device[25:]
                    info = check_output(['bluetoothctl', 'info', addr], encoding='utf-8', timeout=0.5).split('\n')
                    for line in info:
                        if line.startswith('\tName:'):
                            name = line[7:]
                        if line.startswith('\tPaired:'):
                            paired = line[9:] == "yes"
                        if line.startswith('\tTrusted:'):
                            trusted = line[10:] == "yes"
                        if line.startswith('\tConnected:'):
                            connected = line[12:] == "yes"
                        if line.startswith("\tUUID: Vendor specific") and line.endswith("03b80e5a-ede8-4b33-a751-6ce34ec4c700)"):
                            is_midi = True
                    if addr not in self.ble_devices or self.ble_devices[addr] != [name, paired, trusted, connected, is_midi]:
                        self.ble_devices[addr] = [name, paired, trusted, connected, is_midi]
                        update = True
                    if connected and not trusted:
                        # Do not let an untrusted device remain connected
                        check_output(['bluetoothctl', 'disconnect', addr], encoding='utf-8', timeout=5)
            except Exception as e:
                logging.warning(e)

            if update:
                self.update_list()
            
        sleep(2) # Repeat every 2s

    def toggle_ble_trust(self, addr):
        """Toggle trust of BLE device
        
        addr - BLE address
        """

        try:
            if self.ble_devices[addr][2]:
                self.zyngui.state_manager.start_busy("trust_ble", f"Untrusting Bluetooth device\n{addr}")
                check_output(['bluetoothctl', 'untrust', addr], encoding='utf-8', timeout=1)
                check_output(['bluetoothctl', 'disconnect', addr], encoding='utf-8', timeout=5)
                self.ble_devices[addr][3] = False
                self.ble_devices[addr][2] = False
            else:
                self.zyngui.state_manager.start_busy("trust_ble", f"Trusting Bluetooth device\n{addr}")
                check_output(['bluetoothctl', 'trust', addr], encoding='utf-8', timeout=1)
                check_output(['bluetoothctl', 'pair', addr], encoding='utf-8', timeout=1)
                check_output(['bluetoothctl', 'connect', addr], encoding='utf-8', timeout=5)
                self.ble_devices[addr][2] = True
        except Exception as e:
            logging.warning(f"Failed to complete toggle BLE device action: {e}")

        self.update_list()
        self.zyngui.state_manager.end_busy("trust_ble")

    def remove_ble(self, addr):
        """Remove the Bluetooth device
        
        addr : BLE address
        """
        
        self.zyngui.state_manager.start_busy("remove_ble", f"Removing Bluetooth device\n{addr}")
        try:
            self.ble_devices.pop(addr)
            check_output(['bluetoothctl', 'remove', addr], encoding='utf-8', timeout=1)
        except:
            pass
        self.zyngui.state_manager.end_busy("remove_ble")


    def set_select_path(self):
        self.select_path.set("Bluetooth Devices")
        self.set_title("Bluetooth Devices") #TODO: Should not need to set title and select_path!

# ------------------------------------------------------------------------------
