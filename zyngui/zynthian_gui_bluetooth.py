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
        self.proc = None
        self.ble_controllers = {} # Map of Bluetooth controllers, indexed by controller address
        self.ble_devices = {} # Map of BLE devices, indexed by device address
        self.update = False
        self.pending_actions = [] # List of BLE commands to queue
        super().__init__('Bluetooth', True)
        self.select_path.set("Bluetooth")

    def build_view(self):
        if zynthian_gui_config.bluetooth_enabled:
            self.enable_bg_task()
        return super().build_view()

    def hide(self):
        if self.shown:
            self.disable_bg_task()
            super().hide()

    def refresh_status(self):
        if self.update:
            self.update = False
            self.update_list()
        super().refresh_status()

    def fill_list(self):
        self.list_data = []

        if zynthian_gui_config.bluetooth_enabled:
            self.list_data.append(("stop_bluetooth", None, "\u2612 Enable Bluetooth"))
            for ctrl in sorted(self.ble_controllers.keys()):
                chk = "\u2612" if self.ble_controllers[ctrl]["enabled"] else "\u2610"
                self.list_data.append(("enable_controller", ctrl, f"  {chk} {self.ble_controllers[ctrl]['alias']}"))
            self.list_data.append((None, None, "Devices"))
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
                self.disable_bg_task()
                self.zyngui.state_manager.stop_bluetooth(wait=wait)
            elif action == "start_bluetooth":
                self.zyngui.state_manager.start_bluetooth(wait=wait)
                self.enable_bg_task()
            elif action == "enable_controller":
                self.scan_paused = True # Avoid updates and interference from scan thread
                # Disable all unselected devices
                for ctrl in self.ble_controllers:
                    if ctrl != self.list_data[i][1]:
                        self.send_ble_cmd(f"select {ctrl}")
                        self.send_ble_cmd("power off")
                # Enable selected device
                self.send_ble_cmd(f"select {self.list_data[i][1]}")
                self.send_ble_cmd("power on")
                self.ble_devices = {}
                self.scan_paused = False
                for ctrl in self.ble_controllers:
                    self.send_ble_cmd(f"show {ctrl}")
            else:
                self.toggle_ble_trust(self.list_data[i][0][4:])

        # Change mode
        elif t == 'B':
            if self.list_data[i][0].startswith("BLE:"):
                # Bluetooth device
                self.zyngui.show_confirm(f"Remove Bluetooth device?\n{self.list_data[i][2][2:]}\n{self.list_data[i][0]}", self.remove_ble, self.list_data[i][0][4:])
            elif self.list_data[i][0] == "enable_controller":
                self.rename_ctrl = self.list_data[i][1]
                self.zyngui.show_keyboard(self.rename_controller, self.list_data[i][2][4:])

    def rename_controller(self, title):
        self.send_ble_cmd(f"select {self.rename_ctrl}")
        self.send_ble_cmd(f'system-alias "{title}"')
        sleep(1)
        self.send_ble_cmd(f'show {self.rename_ctrl}')

    def enable_bg_task(self):
        """Start background task"""

        self.scan_paused = False
        if self.proc is None:
            # Start scanning and processing bluetooth
            self.proc = Popen('bluetoothctl', stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf-8')
            # Enable background scan for MIDI devices
            Thread(target=self.process_dynamic_ports, name="BLE scan").start()
            self.ble_controllers = {}
            self.ble_devices = {}
            self.send_ble_cmd('list')

    def disable_bg_task(self):
        """Stop background taks"""

        self.ble_controllers = {}
        self.ble_devices = {}
        if self.proc:
            # Stop bluetooth scanning
            self.send_ble_cmd("scan off")
            self.send_ble_cmd("exit")
            self.proc.terminate()
            self.proc = None

    def send_ble_cmd(self, cmd):
        if self.proc:
            self.proc.stdin.write(f"{cmd}\n")
            self.proc.stdin.flush()

    def update_controller_power(self, ctrl, enable):
        changed = self.ble_controllers[ctrl]["enabled"] != enable
        if changed:
            self.ble_controllers[ctrl]["enabled"] = enable
            if enable:
                self.send_ble_cmd(f"select {ctrl}")
                self.send_ble_cmd("agent off")
                self.send_ble_cmd("agent NoInputNoOutput")
                self.send_ble_cmd("scan on")
                self.send_ble_cmd("devices")
                while self.pending_actions:
                    self.send_ble_cmd(self.pending_actions.pop())
            self.update = True

    def process_dynamic_ports(self):
        """Process dynamically added/removed BLE devices"""
		
        # Device config: [name, paired, trusted, connected, is_midi]
        cur_ctrl = None
        cur_dev = None
        parsing = False

        while self.proc:
            try:
                line = self.proc.stdout.readline()
                if self.scan_paused:
                    continue
                result = line.strip().split()
                if line.startswith("\t"):
                    parsing = True
                else:
                    parsing = False
                    cur_ctrl = None
                    cur_dev = None
                while len(result) > 1 and '\x1b' in result[0]:
                    result = result[1:]
                if len(result) == 0:
                    continue

                if result[0] == "Controller":
                    cur_ctrl = result[1]
                    if cur_ctrl not in self.ble_controllers:
                        self.ble_controllers[cur_ctrl] = {"enabled":None, "alias":f"Controller {cur_ctrl}"}
                        self.send_ble_cmd(f"show {cur_ctrl}")
                    if result[2] == "Powered:":
                        enabled = result[3] == "yes"
                        if cur_ctrl not in self.ble_controllers:
                            self.ble_controllers[cur_ctrl] = {"enabled":None, "alias":f"Controller {cur_ctrl}"}
                        self.update_controller_power(cur_ctrl, enabled)
                elif result[0] == "Device":
                    addr = result[1]
                    if result[2] == "RSSI:":
                        #TODO: Do we want to display RSSI? (I don't think so)
                        continue
                    elif "91mDEL\x1b" in line:
                        # Device has been removed
                        self.ble_devices.pop(addr)
                        self.refresh = True
                    elif result[2] in ("(random)", "(public)"):
                        cur_dev = addr
                    elif len(result) == 3:
                        if addr not in self.ble_devices:
                            self.ble_devices[addr] = [result[2], False, False, False, False]
                            self.update = True
                        self.send_ble_cmd(f"info {result[1]}")
                    
                    if addr in self.ble_devices:
                        if result[2] == "Paired:":
                            self.ble_devices[addr][1] = result[3] == "yes"
                            self.update = True
                        elif result[2] == "Trusted:":
                            self.ble_devices[addr][2] = result[3] == "yes"
                            self.update = True
                        elif result[2] == "Connected:":
                            self.ble_devices[addr][3] = result[3] == "yes"
                            self.update = True
                        elif result[2] == "UUID:" and result[3] == "Vendor" and result[4] == "specific" and result[-1] == "03b80e5a-ede8-4b33-a751-6ce34ec4c700)":
                            self.ble_devices[addr][4] = True
                            self.update = True
                elif parsing and cur_ctrl:
                    if result[0] == "Powered:":
                        enabled = result[1] == "yes"
                        self.update_controller_power(cur_ctrl, enabled)
                    if result[0] == "Alias:" and self.ble_controllers[cur_ctrl] != result[1]:
                        self.ble_controllers[cur_ctrl]["alias"] = " ".join(result[1:])
                        self.update = True
                elif parsing and cur_dev:
                    config = self.ble_devices[cur_dev]
                    if result[0] == "Name:":
                        name = " ".join(result[1:])
                        self.ble_devices[cur_dev][0] = name
                    elif result[0] == "Paired:":
                        self.ble_devices[cur_dev][1] = result[1] == "yes"
                    elif result[0] == "Trusted:":
                        self.ble_devices[cur_dev][2] = result[1] == "yes"
                    elif result[0] == "Connected:":
                        self.ble_devices[cur_dev][3] = result[1] == "yes"
                    elif result[0] == "UUID:" and result[1] == "Vendor" and result[2] == "specific" and result[-1] == "03b80e5a-ede8-4b33-a751-6ce34ec4c700)":
                        self.ble_devices[cur_dev][4] = True
                    #if cur_dev and self.ble_devices[cur_dev][3] == "yes" and self.ble_devices[cur_dev][2] != "yes":
                        # Do not let an untrusted device remain connected
                        #self.send_ble_cmd(f"disconnect {cur_dev}")
                    self.update |=  config != self.ble_devices[cur_dev]
            except Exception as e:
                logging.warning(e)

    def toggle_ble_trust(self, addr):
        """Toggle trust of BLE device
        
        addr - BLE address
        """

        try:
            if self.ble_devices[addr][2]:
                #self.send_ble_cmd(f"remove {addr}")
                self.send_ble_cmd(f"untrust {addr}")
                self.send_ble_cmd(f"disconnect {addr}")
            else:
                self.send_ble_cmd(f"trust {addr}")
                self.send_ble_cmd(f"pair {addr}")
                self.send_ble_cmd(f"connect {addr}")
        except Exception as e:
            logging.warning(f"Failed to complete toggle BLE device action: {e}")

    def remove_ble(self, addr):
        """Remove the Bluetooth device
        
        addr : BLE address
        """

        try:
            #self.ble_devices.pop(addr)
            self.pending_actions.insert(0, f"remove {addr}")
        except:
            pass

# ------------------------------------------------------------------------------
