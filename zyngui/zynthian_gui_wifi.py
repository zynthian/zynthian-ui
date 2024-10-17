#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI WIFI config screen Class
#
# Copyright (C) 2015-2024 Fernando Moyano <jofemodo@zynthian.org>
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
from time import sleep
from threading import Thread
from subprocess import check_output

# Zynthian specific modules
import zynconf
from zyngui import zynthian_gui_config
from zyngui.zynthian_gui_selector import zynthian_gui_selector

# ------------------------------------------------------------------------------
# Zynthian WIFI config GUI Class
# ------------------------------------------------------------------------------


class zynthian_gui_wifi(zynthian_gui_selector):

    sys_dir = os.environ.get('ZYNTHIAN_SYS_DIR', "/zynthian/zynthian-sys")

    def __init__(self):
        super().__init__('Connection', True)
        self.config_wifi_name = None
        self.state_manager = self.zyngui.state_manager
        self.scan_thread = None
        self.wifi_scan = False
        self.wifi_data = []
        self.list_data = []

    def build_view(self):
        if not self.scan_thread:
            self.wifi_scan = True
            self.scan_thread = Thread(
                target=self.scan_wifi_task, name="wifi_scan")
            self.scan_thread.start()
        return super().build_view()

    def hide(self):
        self.wifi_scan = False
        self.scan_thread = None
        super().hide()

    def scan_wifi_task(self):
        while self.wifi_scan:
            data = zynconf.get_wifi_list()
            if data != self.wifi_data:
                self.wifi_data = data
                self.update_list()
            sleep(1)

    def fill_list(self):
        wifi_status_code = zynconf.get_nwdev_status_code("wlan0")
        if wifi_status_code == 20:
            self.list_data = [
                (self.enable_wifi, None, "\u2610 Wi-Fi is disabled", False, False)]
        elif wifi_status_code in (30, 50, 100):
            self.list_data = [
                (self.disable_wifi, None, "\u2612 Wi-Fi is enabled", False, False)]
            if not self.wifi_data:
                self.list_data.append(
                    (None, None, "Scanning Wi-Fi Networks...", False, False))
            else:
                self.list_data.append(
                    (None, None, "Wi-Fi Networks", False, False))
                self.list_data += self.wifi_data
        else:
            self.list_data = [
                (None, None, f"Wi-Fi doesn't work! ({wifi_status_code})", False, False)]
        super().fill_list()

    def enable_wifi(self):
        self.state_manager.start_busy("wifi_enable", f"Enabling Wi-Fi")
        try:
            check_output(["nmcli", "--terse", "radio",
                         "wifi", "on"], encoding='utf-8')
            res = True
            sleep(2)
        except Exception as e:
            res = False
            self.state_manager.set_busy_error(f"Can't enable wifi", str(e))
            sleep(3)
        self.state_manager.end_busy("wifi_enable")
        return res

    def disable_wifi(self):
        self.state_manager.start_busy("wifi_disable", f"Disabling Wi-Fi")
        try:
            check_output(["nmcli", "--terse", "radio",
                         "wifi", "off"], encoding='utf-8')
            res = True
        except Exception as e:
            res = False
            self.state_manager.set_busy_error(f"Can't disable wifi", str(e))
            sleep(3)
        self.state_manager.end_busy("wifi_disable")
        return res

    def enable_wifi_nw(self, name):
        self.state_manager.start_busy(
            "wifi_enable_nw", f"Connecting to {name}")
        try:
            output = check_output(
                ["nmcli", "--terse", "con", "up", name], encoding='utf-8')
            if "Connection successfully activated" in output:
                res = True
                self.state_manager.set_busy_success(f"Connected to {name}")
                sleep(2)
            else:
                res = False
                logging.debug(f"{output}")
                self.state_manager.set_busy_error(output)
                sleep(2)
        except Exception as e:
            res = False
            self.state_manager.set_busy_error(
                f"Can't enable network {name}", str(e))
            sleep(2)
        self.state_manager.end_busy("wifi_enable_nw")
        if not res:
            self.reconfigure_wifi_nw(name)
        return res

    def disable_wifi_nw(self, name):
        self.state_manager.start_busy(
            "wifi_disable_nw", f"Disconnecting from {name}")
        try:
            output = check_output(
                ["nmcli", "--terse", "con", "down", name], encoding='utf-8')
            if "successfully deactivated" in output:
                res = True
                self.state_manager.set_busy_success(
                    f"Disconnected from {name}")
                sleep(2)
            else:
                res = False
                logging.debug(f"{output}")
                self.state_manager.set_busy_error(output)
                sleep(3)
        except Exception as e:
            res = False
            self.state_manager.set_busy_error(
                f"Can't disable network {name}", str(e))
            sleep(3)
        self.state_manager.end_busy("wifi_disable_nw")
        return res

    def configure_wifi_nw(self, name):
        self.config_wifi_name = name
        self.zyngui.show_keyboard(self.configure_wifi_nw_cb, "")

    def configure_wifi_nw_cb(self, passwd):
        self.state_manager.start_busy(
            "wifi_config_nw", f"Connecting to {self.config_wifi_name}")
        try:
            output = check_output(["nmcli", "dev", "wifi", "connect",
                                  self.config_wifi_name, "password", passwd], encoding='utf-8')
            if "successfully activated" in output:
                res = True
                self.state_manager.set_busy_success(
                    f"Connected to {self.config_wifi_name}")
                self.config_wifi_name = None
                sleep(2)
            else:
                res = False
                logging.debug(f"{output}")
                self.state_manager.set_busy_error(output)
                sleep(2)
        except Exception as e:
            res = False
            logging.debug(f"{e}")
            self.state_manager.set_busy_error(
                f"Can't configure network {self.config_wifi_name}", str(e))
            sleep(2)
        self.state_manager.end_busy("wifi_config_nw")
        if not res:
            self.reconfigure_wifi_nw(self.config_wifi_name)
        return res

    def delete_wifi_nw(self, name):
        try:
            output = check_output(
                ["nmcli", "con", "del", name], encoding='utf-8')
            res = True
        except Exception as e:
            res = False
            logging.error(f"Can't delete connection {name}")
        return res

    def reconfigure_wifi_nw(self, name):
        self.config_wifi_name = name
        self.zyngui.show_keyboard(self.reconfigure_wifi_nw_cb, "")

    def reconfigure_wifi_nw_cb(self, passwd):
        if self.delete_wifi_nw(self.config_wifi_name):
            self.configure_wifi_nw_cb(passwd)

    def select_action(self, i, t='S'):
        if callable(self.list_data[i][0]):
            self.list_data[i][0]()
        elif self.list_data[i][3]:
            if not self.list_data[i][4]:
                logging.info(f"Connecting to {self.list_data[i][0]}...")
                self.enable_wifi_nw(self.list_data[i][0])
            else:
                logging.info(f"Disconnecting from {self.list_data[i][0]}...")
                self.disable_wifi_nw(self.list_data[i][0])
        else:
            logging.info("Wi-Fi network not configured. Configuring...")
            self.configure_wifi_nw(self.list_data[i][0])

    def set_select_path(self):
        self.select_path.set("Wi-Fi Networks")

# ------------------------------------------------------------------------------
