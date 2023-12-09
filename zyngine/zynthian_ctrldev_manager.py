#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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
import logging
import sys
from threading import Thread
from time import sleep

# Zynthian specific modules
import zynautoconnect
from zyngine.ctrldev import *
from zyncoder.zyncore import lib_zyncore

# ------------------------------------------------------------------------------
# Zynthian Control Device Manager Class
# ------------------------------------------------------------------------------


class zynthian_ctrldev_manager():

    ctrldev_dpath = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui") + "/zyngui/ctrldev"

    # Function to initialise class
    def __init__(self, state_manager):
        """Initialise ctrldev_manager
        
        state_manager : State manager object
        """

        self.state_manager = state_manager
        self.available_drivers = {}  # Map of driver classes indexed by device type name
        self.drivers = {}  # Map of device driver objects indexed by zmip
        self.update_available_drivers()
        self.seq_queue = None
        self.thread = Thread(target=self.thread_task)
        self.thread.name = "Control Device Manager"
        self.thread.daemon = True  # thread dies with the program
        self.thread.start()

    def thread_task(self):
        """Thread to update device status"""

        while not self.state_manager.exit_flag:
            if self.seq_queue and not self.seq_queue.empty():
                bank, seq, state, mode = self.seq_queue.get(timeout=1)
                for driver in self.drivers.values():
                    if driver.dev_zynpad:
                        driver.update_pad(seq, state, mode)
            else:
                sleep(0.01)

    def update_available_drivers(self):
        """Update map of available driver names"""

        self.available_drivers = {}
        for module_name in list(sys.modules):
            if module_name.startswith("zyngine.ctrldev.zynthian_ctrldev_"):
                class_name = module_name[16:]
                dev_class = getattr(sys.modules[module_name], class_name)
                for dev_id in dev_class.dev_ids:
                    logging.info(f"Ctrldev driver '{class_name}' for devices with ID '{dev_id}'")
                    self.available_drivers[dev_id] = dev_class

    def load_driver(self, izmip):
        """Loads a device driver
        
        izmip : Index of zmip to attach driver
        returns : True if new driver loaded
        """

        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        if dev_id not in self.available_drivers:
            return False
        if izmip in self.drivers:
            return False #TODO: Should check if driver differs
        izmop = zynautoconnect.dev_in_2_dev_out(izmip)
        try:
            lib_zyncore.zmip_set_route_extdev(izmip, 0)
            self.drivers[izmip] = self.available_drivers[device_type](self.state_manager, izmip, izmop)
            if self.seq_queue is None and self.drivers[izmip].dev_zynpad:
                self.seq_queue = self.state_manager.register_seq()
            logging.info(f"Loaded ctrldev driver {device_type}.")
            return True
        except Exception as e:
            logging.error(f"Can't load ctrldev driver {device_type} => {e}")
            return False

    def unload_driver(self, izmip):
        """Unloads a device driver
        
        izmip : Index of zmip to detach driver
        returns : True if existing driver detached
        """

        if izmip in self.drivers:
            if self.drivers[izmip].dev_zynpad:
                found = False
                for driver in self.drivers.values():
                    if driver.dev_zynpad:
                        found = True
                        break
                if not found:
                    self.state_manager.unregister_seq(self.seq_queue)
                    self.seq_queue = None

            self.drivers[izmip].end()
            self.drivers.pop(izmip)
            lib_zyncore.zmip_set_route_extdev(izmip, 1)
            return True
        return False

    def sleep_on(self):
        """Enable sleep state"""

        for dev in self.drivers.values():
            dev.sleep_on()

    def sleep_off(self):
        """Disable sleep state"""

        for dev in self.drivers.values():
            dev.sleep_off()

    def midi_event(self, ev):
        """Process MIDI event from zynmidirouter
        
        ev - 32-bit MIDI event: device cmd val1 val2
        """
        
        idev = ((ev & 0xFF000000) >> 24) - 1

        # Try device driver ...
        if idev in self.drivers:
            return self.drivers[idev].midi_event(ev)

        return False

# -----------------------------------------------------------------------------------------
