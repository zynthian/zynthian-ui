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

    ctrldev_dpath = os.environ.get(
        'ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui") + "/zyngui/ctrldev"

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
                    logging.info(
                        f"Ctrldev driver '{class_name}' for devices with ID '{dev_id}'")
                    self.available_drivers[dev_id] = dev_class

    def load_driver(self, izmip, force=False):
        """Loads a device driver

        izmip : Index of zmip to attach driver
        force : Enable driver ignoring autoload_flag / disabled list
        returns : True if new driver loaded
        """

        # Check if driver does exist
        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        if dev_id not in self.available_drivers:
            return False
        # If force => remove driver from disabled list
        uid = zynautoconnect.get_midi_in_uid(izmip)
        autoload_flag = self.available_drivers[dev_id].get_autoload_flag()
        if uid in self.disabled_devices:
            if force:
                self.disabled_devices.remove(uid)
        # if not force nor autoload flag, add driver to disabled list
        else:
            if not (force or autoload_flag):
                self.disabled_devices.append(uid)

        # If driver already loaded ...
        # TODO: Should check if driver differs?
        if izmip in self.drivers:
            # Unload driver if it's in disabled list
            if uid in self.disabled_devices:
                self.unload_driver(izmip)
            return False

        # If driver is not loaded ...
        else:
            # Don't load if it's in disabled list
            if uid in self.disabled_devices:
                return False
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
        disable : True to disable driver for this device (Default: False)
        returns : True if existing driver detached
        """

        # Check if driver does exist and must be added to disabled list
        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        if disable and dev_id in self.available_drivers and self.available_drivers[dev_id].get_autoload_flag():
            self.set_disabled_driver(zynautoconnect.get_midi_in_uid(izmip), True)
        # If driver is loaded, unload it!
        if izmip in self.drivers:
            # Restore route to chains
            if self.drivers[izmip].unroute_from_chains:
                lib_zyncore.zmip_set_route_chains(izmip, 1)
            # Unload driver
            self.drivers[izmip].end()
            self.drivers.pop(izmip)
            logging.info(f"Unloaded ctrldev driver {dev_id}.")
            return True

        return False

    def unload_all_drivers(self):
        for izmip in list(self.drivers):
            self.unload_driver(izmip)

    def set_disabled_driver(self, uid, disable_state):
        if uid is not None:
            if uid not in self.disabled_devices:
                if disable_state:
                    self.disabled_devices.append(uid)
            else:
                if not disable_state:
                    self.disabled_devices.remove(uid)

    def get_disabled_driver(self, uid):
        return uid in self.disabled_devices

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
                logging.error(
                    f"Driver error while getting state for '{uid}' => {e}")
        return state

    def set_state_drivers(self, state):
        for uid, dstate in state.items():
            izmip = zynautoconnect.get_midi_devid_by_uid(
                uid, zynthian_gui_config.midi_usb_by_port)
            if izmip is not None and izmip in self.drivers:
                try:
                    self.drivers[izmip].set_state(dstate)
                except Exception as e:
                    logging.error(
                        f"Driver error while restoring state for '{uid}' => {e}")
            else:
                logging.warning(
                    f"Can't restore state for '{uid}'. Device not connected or driver not loaded.")

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
