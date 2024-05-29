#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
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
import logging
import sys

# Zynthian specific modules
import zynautoconnect
from zyngine.ctrldev import *
from zyngui import zynthian_gui_config
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
        self.disabled_devices = []  # List of device uid disabled from loading driver
        self.update_available_drivers()

    def update_available_drivers(self):
        """Update map of available driver names"""

        self.available_drivers = {}
        for module_name in list(sys.modules):
            if module_name.startswith("zyngine.ctrldev.zynthian_ctrldev_"):
                class_name = module_name[16:]
                dev_class = getattr(sys.modules[module_name], class_name, None)
                if dev_class is None:
                    continue
                for dev_id in dev_class.dev_ids:
                    logging.info(f"Ctrldev driver '{class_name}' for devices with ID '{dev_id}'")
                    self.available_drivers[dev_id] = dev_class

    def load_driver(self, izmip, enable=False):
        """Loads a device driver
        
        izmip : Index of zmip to attach driver
        enable : Enable driver for this input
        returns : True if new driver loaded
        """

        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        if dev_id not in self.available_drivers:
            return False
        uid = zynautoconnect.get_midi_in_uid(izmip)
        if enable and uid in self.disabled_devices:
            self.disabled_devices.remove(uid)
        if izmip in self.drivers or uid in self.disabled_devices:
            return False  # TODO: Should check if driver differs
        izmop = zynautoconnect.dev_in_2_dev_out(izmip)
        try:
            # Load driver
            self.drivers[izmip] = self.available_drivers[dev_id](self.state_manager, izmip, izmop)
            # Unroute from chains if driver want it
            if self.drivers[izmip].unroute_from_chains:
                lib_zyncore.zmip_set_route_chains(izmip, 0)
            # Initialize the driver after creating the instance, so MIDI answer messages can be processed
            self.drivers[izmip].init()
            logging.info(f"Loaded ctrldev driver {dev_id}.")
            return True
        except Exception as e:
            logging.error(f"Can't load ctrldev driver {dev_id} => {e}")
            return False

    def unload_driver(self, izmip, disable=False):
        """Unloads a device driver
        
        izmip : Index of zmip to detach driver
        disable : True to disable device from loading driver (Default: False)
        returns : True if existing driver detached
        """

        if disable and zynautoconnect.get_midi_in_devid(izmip) in self.available_drivers:
            uid = zynautoconnect.get_midi_in_uid(izmip)
            if uid is not None and uid not in self.disabled_devices:
                self.disabled_devices.append(uid)
        if izmip in self.drivers:
            # Restore route to chains
            if self.drivers[izmip].unroute_from_chains:
                lib_zyncore.zmip_set_route_chains(izmip, 1)
            # Unload driver
            self.drivers[izmip].end()
            self.drivers.pop(izmip)
            return True

        return False

    def unload_all_drivers(self):
        for izmip in list(self.drivers):
            self.unload_driver(izmip)

    def is_input_device_available_to_chains(self, idev):
        if idev in self.drivers and self.drivers[idev].unroute_from_chains:
            return False
        else:
            return True

    def get_state_drivers(self):
        state = {}
        for izmip in self.drivers:
            try:
                uid = zynautoconnect.get_midi_in_uid(izmip)
                dstate = self.drivers[izmip].get_state()
                if dstate:
                    state[uid] = dstate
            except Exception as e:
                logging.error(f"Driver error while getting state for '{uid}' => {e}")
        return state

    def set_state_drivers(self, state):
        for uid, dstate in state.items():
            izmip = zynautoconnect.get_midi_in_devid_by_uid(uid, zynthian_gui_config.midi_usb_by_port)
            if izmip is not None and izmip in self.drivers:
                try:
                    self.drivers[izmip].set_state(dstate)
                except Exception as e:
                    logging.error(f"Driver error while restoring state for '{uid}' => {e}")
            else:
                logging.warning(f"Can't restore state for '{uid}'. Device not connected or driver not loaded.")

    def sleep_on(self):
        """Enable sleep state"""

        for dev in self.drivers.values():
            dev.sleep_on()

    def sleep_off(self):
        """Disable sleep state"""

        for dev in self.drivers.values():
            dev.sleep_off()

    def midi_event(self, idev, ev):
        """Process MIDI event from zynmidirouter

        idev - device index
        ev - bytes with MIDI message data
        """
        
        # Try device driver ...
        if idev in self.drivers:
            return self.drivers[idev].midi_event(ev)

        return False

# -----------------------------------------------------------------------------------------
