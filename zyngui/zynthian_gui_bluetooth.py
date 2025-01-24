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
from subprocess import Popen, PIPE

# Zynthian specific modules
from zyngui.zynthian_gui_selector_info import zynthian_gui_selector_info
from zyngui import zynthian_gui_config
import zynconf

# ------------------------------------------------------------------------------
# Zynthian hotplug hardware config GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_bluetooth(zynthian_gui_selector_info):

    def __init__(self):
        self.proc = None
        self.update = False
        self.scan_paused = False
        # Map of Bluetooth controllers, indexed by controller address
        self.ble_controllers = {}
        self.ble_devices = {}           # Map of BLE devices, indexed by device address
        self.pending_actions = []       # List of BLE commands to queue
        super().__init__('Bluetooth')
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
            self.list_data.append(
                ("stop_bluetooth", None, "\u2612 Enable Bluetooth", ["Bluetooth is enabled.\n\nSelect to disable Bluetooth.", "bluetooth.png"]))
            if len(self.ble_controllers) == 0:
                self.list_data.append(
                    (None, None, "No Bluetooth controllers detected!", ["There are not Bluetooth controllers attached to zynthian. You may connect a Bluetooth USB device.", "bluetooth.png"]))
                super().fill_list()
                return
            for ctrl in sorted(self.ble_controllers.keys()):
                chk = "\u2612" if self.ble_controllers[ctrl]["enabled"] else "\u2610"
                self.list_data.append(
                    ("enable_controller", ctrl, f"  {chk} {self.ble_controllers[ctrl]['alias']}", ["Enable/disable Bluetooth controller.\n\nOnly enable a single controller. It is advised to use a USB Bluetooth adapter because the Raspberry Pi onboard adapter has poor range.", "bluetooth.png"]))
            self.list_data.append((None, None, "Devices"))
            for addr, data in self.ble_devices.items():
                # [name, paired, trusted, connected, is_midi]
                if data[2]:
                    title = "\u2612 "
                else:
                    title = "\u2610 "
                if data[3]:
                    title += "\uf293 "
                title += data[0]
                self.list_data.append((f"BLE:{addr}", addr, title, ["Enable/disable this USB device.\n\nEnabling a device will pair it with zynthian. This state will be remembered.", "bluetooth.png"]))
        else:
            self.list_data.append(
                ("start_bluetooth", None, "\u2610 Enable Bluetooth", ["Bluetooth is disabled.\n\nSelect to enable Bluetooth.", "bluetooth.png"]))

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
                if self.list_data[i][1] == zynthian_gui_config.ble_controller and self.list_data[i][2].startswith("  ☒"):
                    return
                self.zyngui.state_manager.start_busy("Enabling BLE Controller")
                self.send_ble_cmd("scan off")
                self.zyngui.state_manager.select_bluetooth_controller(
                    self.list_data[i][1])
                self.send_ble_cmd(
                    f"select {zynthian_gui_config.ble_controller}")
                self.ble_devices = {}
                sleep(1)
                self.send_ble_cmd("scan on")
                self.zyngui.state_manager.end_busy("Enabling BLE Controller")
                for ctrl in self.ble_controllers:
                    self.send_ble_cmd(f"show {ctrl}")
            else:
                self.toggle_ble_trust(self.list_data[i][0][4:])

        # Change mode
        elif t == 'B':
            if self.list_data[i][0].startswith("BLE:"):
                # Bluetooth device
                self.zyngui.show_confirm(
                    f"Remove Bluetooth device?\n{self.list_data[i][2][2:]}\n{self.list_data[i][0]}", self.remove_ble, self.list_data[i][0][4:])
            elif self.list_data[i][0] == "enable_controller":
                self.rename_ctrl = self.list_data[i][1]
                self.zyngui.show_keyboard(
                    self.rename_controller, self.list_data[i][2][4:])

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
            self.proc = Popen(["bluetoothctl", "--agent", "DisplayOnly"],
                              stdin=PIPE, stdout=PIPE, stderr=PIPE, encoding='utf-8')
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
                self.send_ble_cmd("scan on")
                self.send_ble_cmd("devices")
                while self.pending_actions:
                    self.send_ble_cmd(self.pending_actions.pop())
            self.update = True

    def process_dynamic_ports(self):
        """Process dynamically added/removed BLE devices"""
        cur_ctrl = None
        cur_dev = None

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
                    if result[1].count(":") != 5:
                        continue
                    cur_ctrl = result[1]
                    if cur_ctrl not in self.ble_controllers:
                        self.ble_controllers[cur_ctrl] = {
                            "enabled": None, "alias": f"Controller {cur_ctrl}"}
                        self.send_ble_cmd(f"show {cur_ctrl}")
                    if result[2] == "Powered:":
                        enabled = result[3] == "yes"
                        if cur_ctrl not in self.ble_controllers:
                            self.ble_controllers[cur_ctrl] = {
                                "enabled": None, "alias": f"Controller {cur_ctrl}"}
                        self.update_controller_power(cur_ctrl, enabled)
                elif result[0] == "Device":
                    if result[1].count(":") != 5:
                        continue
                    addr = result[1]
                    if result[2] == "RSSI:":
                        # TODO: Do we want to display RSSI? (I don't think so)
                        continue
                    elif "91mDEL\x1b" in line or line.endswith("not available"):
                        # Device has been removed
                        self.ble_devices.pop(addr)
                        self.refresh = True
                    elif result[2] in ("(random)", "(public)"):
                        cur_dev = addr
                    elif addr not in self.ble_devices and result[2] not in ("Trusted:", "Connected:", "Paired:"):
                        self.ble_devices[addr] = [addr, None, None, None, None]
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
                            # BLE MIDI device has "Vender specific" UUID with value 03b80e5a-ede8-4b33-a751-6ce34ec4c700
                            self.ble_devices[addr][4] = True
                            self.update = True
                elif parsing and cur_ctrl:
                    if result[0] == "Powered:":
                        enabled = result[1] == "yes"
                        self.update_controller_power(cur_ctrl, enabled)
                    if result[0] == "Alias:" and self.ble_controllers[cur_ctrl] != result[1]:
                        self.ble_controllers[cur_ctrl]["alias"] = " ".join(
                            result[1:])
                        self.update = True
                elif parsing and cur_dev:
                    # self.ble_devices[addr] is a list: [alias, paired, trusted, connected, is_midi]
                    config = self.ble_devices[cur_dev]
                    if result[0] == "Alias:":
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
                    elif result[0] == "Battery" and result[2] == "Percentage":
                        battery_value = int(result[2], 16)
                        # TODO: Do we want to record battery level
                    # if cur_dev and self.ble_devices[cur_dev][3] == "yes" and self.ble_devices[cur_dev][2] != "yes":
                        # Do not let an untrusted device remain connected
                        # self.send_ble_cmd(f"disconnect {cur_dev}")
                    self.update |= config != self.ble_devices[cur_dev]
            except Exception as e:
                # Accept occasional error instead of checking length of result many times.
                pass

    def toggle_ble_trust(self, addr):
        """Toggle trust of BLE device

        addr - BLE address
        """
        self.zyngui.state_manager.start_busy("Toggle BLE Device")
        try:
            """
            If a device is paired, it needs to be removed but that will also remove it from the list until it is detected again
            If a device is trusted and connected, it may ask for pairing and authentication.
            """
            if self.ble_devices[addr][1] or self.ble_devices[addr][2]:
                self.send_ble_cmd(f"untrust {addr}")
                self.send_ble_cmd(f"disconnect {addr}")
                self.send_ble_cmd(f"remove {addr}")
                self.ble_devices.pop(addr)
                self.update_list()
            elif self.ble_devices[addr][2]:
                self.send_ble_cmd(f"untrust {addr}")
                self.send_ble_cmd(f"disconnect {addr}")
            else:
                self.send_ble_cmd(f"trust {addr}")
                self.send_ble_cmd(f"pair {addr}")
        except Exception as e:
            logging.warning(
                f"Failed to complete toggle BLE device action: {e}")
            self.update = True
        sleep(2)
        self.zyngui.state_manager.end_busy("Toggle BLE Device")

    def remove_ble(self, addr):
        """Remove the Bluetooth device

        addr : BLE address
        """
        try:
            # self.ble_devices.pop(addr)
            self.pending_actions.insert(0, f"remove {addr}")
        except:
            pass

# ------------------------------------------------------------------------------
