#!/usr/bin/python3
# -*- coding: utf-8 -*-
# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
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
import glob
import logging
import importlib
from pathlib import Path

# Zynthian specific modules
import zynautoconnect
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
        self.driver_classes = {} # Dictionary of driver classes indexed by module name
        self.available_drivers = {}  # Dictionary of lists of available driver classes indexed by device ID
        self.drivers = {}  # Map of device driver instances indexed by zmip
        self.disabled_devices = []  # List of device uid disabled from loading driver
        self.update_available_drivers()

    def update_available_drivers(self, reload_modules=False):
        """Update map of available driver names"""

        if reload_modules:
            self.driver_classes = {}

        # Find and load new driver modules
        ctrldev_drivers_path = f"/zynthian/zynthian-ui/zyngine/ctrldev"
        for module_path in glob.glob(f"{ctrldev_drivers_path}/*.py"):
            module_name = Path(module_path).stem
            if not module_name.startswith("__") and not module_name.startswith("zynthian_ctrldev_base") and module_name not in self.driver_classes:
                try:
                    spec = importlib.util.spec_from_file_location(module_name, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                except Exception as e:
                    logging.error(f"Can't load ctrldev driver module '{module_name}' => {e}")
                    continue
                try:
                    self.driver_classes[module_name] = getattr(module, module_name)
                    logging.debug(f"Loaded ctrldev driver class '{module_name}'")
                except:
                    logging.error(f"Ctrldev driver class '{module_name}' not found in module '{module_name}'")

        # Regenerate available drivers dict
        self.available_drivers = { "*": [] }
        for module_name, driver_class in self.driver_classes.items():
            for dev_id in driver_class.dev_ids:
                logging.info(f"Found ctrldev driver '{module_name}' for devices with ID '{dev_id}'")
                if dev_id in self.available_drivers:
                    self.available_drivers[dev_id].append(driver_class)
                else:
                    self.available_drivers[dev_id] = [driver_class]

    def load_driver(self, izmip, driver_name=None):
        """Loads a device driver

        izmip : Index of zmip to attach driver
        driver_name: Name of driver to load and attach to izmip or None to load first autoload driver
        returns : True if new driver loaded
        """

        if driver_name == "":
            return False

        # Get ID for the device attached to izmip
        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        uid = zynautoconnect.get_midi_in_uid(izmip)

        driver_class = None
        if driver_name is None:  # Autoload
            if izmip in self.drivers or dev_id not in self.available_drivers:
                return False  # Don't autoload already loaded or generic driver
            for cls in self.available_drivers[dev_id]:
                if cls.get_autoload_flag():
                    driver_class = cls
                    break
        else:
            try:
                driver_class = self.driver_classes[driver_name]
            except:
                logging.warning("Requested driver is not available")

        if driver_class is None:
            return False

        # If a driver is already loaded for this device ...
        if izmip in self.drivers:
            # If it's the requested driver ...
            if isinstance(self.drivers[izmip], driver_class):
                return False
            # Unload the current driver if requested a different one
            else:
                self.unload_driver(izmip)

        # Load requested driver
        izmop = zynautoconnect.dev_in_2_dev_out(izmip)
        try:
            # Create the driver instance
            self.drivers[izmip] = driver_class(self.state_manager, izmip, izmop)
            # Unroute from chains if driver want it
            if self.drivers[izmip].unroute_from_chains:
                lib_zyncore.zmip_set_route_chains(izmip, 0)
            # Initialize the driver after creating the instance to enable driver MIDI handler
            self.drivers[izmip].init() #TODO: Why not call this in the driver _init_()?
            if uid in self.disabled_devices:
                self.disabled_devices.remove(uid)
            logging.info(f"Loaded ctrldev driver '{driver_class.get_driver_name()}' for '{dev_id}'.")
            return True
        except Exception as e:
            logging.error(f"Can't load ctrldev driver '{driver_class.get_driver_name()}' for '{dev_id}' => {e}")
            return False

    def unload_driver(self, izmip, disable=False):
        """Unloads a device driver

        izmip : Index of zmip to detach driver
        disable : True to disable driver for this device (Default: False)
        returns : True if existing driver detached
        """

        # If driver is loaded, unload it!
        if izmip in self.drivers:
            dev_id = zynautoconnect.get_midi_in_devid(izmip)
            uid = zynautoconnect.get_midi_in_uid(izmip)
            # Restore route to chains
            if self.drivers[izmip].unroute_from_chains:
                lib_zyncore.zmip_set_route_chains(izmip, 1)
            # Terminate driver instance
            self.drivers[izmip].end()
            # Drop from the list => Unload driver!
            logging.info(f"Unloaded ctrldev driver '{self.drivers[izmip].get_driver_name()}' for '{dev_id}'.")
            self.drivers.pop(izmip)
            if disable and uid not in self.disabled_devices:
                self.disabled_devices.append(uid)
            return True
        return False

    def unload_all_drivers(self):
        for izmip in list(self.drivers):
            self.unload_driver(izmip)

    def get_disabled_driver(self, uid):
        return uid in self.disabled_devices

    def get_driver_class_name(self, izmip):
        try:
            return self.drivers[izmip].__class__.__name__
        except:
            return ""

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
            izmip = zynautoconnect.get_midi_in_devid_by_uid(
                uid, zynthian_gui_config.midi_usb_by_port)
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
