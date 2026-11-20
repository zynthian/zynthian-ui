# ******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2025 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <riban@zynthian.org>
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
import traceback
from pathlib import Path
from time import monotonic

# Zynthian specific modules
import zynautoconnect
from zyngui import zynthian_gui_config
from zyncoder.zyncore import lib_zyncore

# SysEx Identity Request (Universal Non-Realtime, General Information), to any device ID
SYSEX_ID_REQUEST = bytes.fromhex("F0 7E 7F 06 01 F7")
IDENTITY_RETRY_SECS = 5  # Least time between identity requests to a device that has not answered

# TODO! GET TO WORK DYNAMIC MODULE LOADING
DRIVER_DEVELOPMENT = False
#DRIVER_DEVELOPMENT = True

# ------------------------------------------------------------------------------
# Zynthian Control Device Manager Class
# ------------------------------------------------------------------------------


class zynthian_ctrldev_manager():

    ctrldev_path_base = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui") + "/zyngine"
    ctrldev_dirnames = ["ctrldev_user", "ctrldev"]

    # Function to initialise class
    def __init__(self, state_manager):
        """Initialise ctrldev_manager

        state_manager : State manager object
        """

        self.state_manager = state_manager
        self.driver_classes = {}  # Dictionary of driver classes indexed by module name
        self.available_drivers = {}  # Dictionary of lists of available driver classes indexed by device ID
        self.drivers = {}  # Map of device driver instances indexed by zmip
        self.disabled_devices = []  # List of device uid disabled from loading driver
        self.sysex_drivers = []  # List of (SysEx identity prefix, driver class)
        self.identities = {}  # SysEx identity of the device on each zmip (bytes from the manufacturer ID to the version), indexed by zmip
        self.identity_asked = {}  # Time of the last identity request to each zmip, indexed by zmip
        self.update_available_drivers()

    def update_available_drivers(self, reload_modules=False):
        """Update map of available driver names"""

        self.available_drivers = {"*": []}
        self.sysex_drivers = []
        if reload_modules:
            self.driver_classes = {}

        # Find and load new driver modules
        for dirname in self.ctrldev_dirnames:
            for module_path in glob.glob(f"{self.ctrldev_path_base}/{dirname}/*.py"):
                module_name = Path(module_path).stem
                if not module_name.startswith("__") and not module_name.startswith("zynthian_ctrldev_base") and module_name not in self.driver_classes:
                    try:
                        #spec = importlib.util.spec_from_file_location(module_name, module_path)
                        #module = importlib.util.module_from_spec(spec)
                        #spec.loader.exec_module(module)
                        module = importlib.import_module(f"zyngine.{dirname}.{module_name}")
                        if reload_modules:
                            module = importlib.reload(module)
                    except Exception as e:
                        logging.error(f"Can't load ctrldev driver module '{module_name}' => {e}")
                        continue
                    try:
                        self.driver_classes[module_name] = getattr(module, module_name)
                        logging.debug(f"Loaded ctrldev driver class '{module_name}'")
                    except:
                        logging.error(f"Ctrldev driver class '{module_name}' not found in module '{module_name}'")

        # Regenerate available drivers dict
        for module_name, driver_class in self.driver_classes.items():
            for dev_id in driver_class.dev_ids:
                logging.info(f"Found ctrldev driver '{module_name}' for devices with ID '{dev_id}'")
                if dev_id in self.available_drivers:
                    self.available_drivers[dev_id].append(driver_class)
                else:
                    self.available_drivers[dev_id] = [driver_class]
            for sysex_id in getattr(driver_class, "sysex_ids", []):
                try:
                    prefix = bytes.fromhex(sysex_id) if isinstance(sysex_id, str) else bytes(sysex_id)
                except Exception as e:
                    logging.error(f"Bad SysEx identity '{sysex_id}' in ctrldev driver '{module_name}' => {e}")
                    continue
                logging.info(f"Found ctrldev driver '{module_name}' for devices with SysEx identity '{prefix.hex(' ')}'")
                self.sysex_drivers.append((prefix, driver_class))

    # --------------------------------------------------------------------------
    # SysEx device identity
    # --------------------------------------------------------------------------

    @staticmethod
    def is_external(izmip):
        """True if izmip is a device port (not the sequencer or another internal port)"""

        try:
            return izmip is not None and 0 <= izmip < lib_zyncore.zmip_get_seq_index()
        except Exception:
            return False

    def request_identity(self, izmip, force=False):
        """Ask the device on a port for its SysEx identity. Its reply (handled by midi_event) may
        autoload a driver. Called when it is needed (a new device without a driver for its ID, the
        MIDI input menu), never periodically.

        izmip : Index of zmip
        force : True to ask even if the identity is known or was asked for recently
        returns : True if the request was sent
        """

        if not self.is_external(izmip):
            return False
        if not force:
            if izmip in self.identities:
                return False
            if izmip in self.identity_asked and monotonic() < self.identity_asked[izmip] + IDENTITY_RETRY_SECS:
                return False
        izmop = zynautoconnect.dev_in_2_dev_out(izmip)
        if izmop is None:
            return False
        self.identity_asked[izmip] = monotonic()
        try:
            lib_zyncore.dev_send_midi_event(izmop, SYSEX_ID_REQUEST, len(SYSEX_ID_REQUEST))
        except Exception as e:
            logging.warning(f"Can't send identity request to MIDI device {izmip} => {e}")
            return False
        return True

    def forget_identity(self, izmip):
        """Forget the identity of the device on a port (disconnected)"""

        self.identities.pop(izmip, None)
        self.identity_asked.pop(izmip, None)

    def get_identity(self, izmip):
        """Get the SysEx identity of the device on a port

        returns : bytes from the manufacturer ID to the version, or None if unknown
        """

        return self.identities.get(izmip)

    def get_identity_str(self, izmip):
        """Get the SysEx identity of the device on a port as text, or None if unknown"""

        identity = self.identities.get(izmip)
        if identity is None:
            return None
        n = 3 if identity[0] == 0 else 1
        manufacturer = identity[:n].hex(" ").upper()
        rest = identity[n:]
        return (f"manufacturer {manufacturer}, family {rest[0:2].hex(' ').upper()}, "
                f"model {rest[2:4].hex(' ').upper()}, version {rest[4:8].hex(' ').upper()}")

    def get_identity_drivers(self, izmip):
        """Get the driver classes matching the SysEx identity of the device on a port"""

        identity = self.identities.get(izmip)
        if identity is None:
            return []
        result = []
        for prefix, driver_class in self.sysex_drivers:
            if identity.startswith(prefix) and driver_class not in result:
                result.append(driver_class)
        return result

    def get_device_drivers(self, izmip):
        """Get the driver classes available for the device on a port: those for its device ID,
        those for its SysEx identity, then the generic ones (external devices only)"""

        result = []
        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        candidates = list(self.available_drivers.get(dev_id, [])) if dev_id != "*" else []
        candidates += self.get_identity_drivers(izmip)
        if self.is_external(izmip):
            candidates += self.available_drivers.get("*", [])
        for driver_class in candidates:
            if driver_class not in result:
                result.append(driver_class)
        return result

    def on_identity(self, izmip, ev):
        """Handle a SysEx identity reply, asked for or not (a device announcing itself at power-on)

        izmip : Index of zmip it came from
        ev : The SysEx message (F0 7E <device> 06 02 <manufacturer> <family> <model> <version> F7)
        """

        identity = bytes(ev[5:-1] if ev[-1] == 0xF7 else ev[5:])
        if len(identity) < 1:
            return
        if self.identities.get(izmip) != identity:
            self.identities[izmip] = identity
            logging.info(f"MIDI device {izmip} identity: {self.get_identity_str(izmip)}")
        # Autoload a driver for it, unless one is loaded or the user disabled drivers for it
        if izmip in self.drivers:
            return
        uid = zynautoconnect.get_midi_in_uid(izmip)
        if uid in self.disabled_devices:
            return
        for driver_class in self.get_identity_drivers(izmip):
            if driver_class.get_sysex_autoload():
                self.load_driver(izmip, driver_class.__name__)
                return

    def load_driver(self, izmip, driver_name=None):
        """Loads a device driver

        izmip : Index of zmip to attach driver
        driver_name: Name of driver to load and attach to izmip or None to load first autoload driver
        returns : True if new driver loaded
        """

        if driver_name == "":
            return False

        if DRIVER_DEVELOPMENT:
            self.update_available_drivers()

        # Get ID for the device attached to izmip
        dev_id = zynautoconnect.get_midi_in_devid(izmip)
        uid = zynautoconnect.get_midi_in_uid(izmip)

        driver_class = None
        if driver_name is None:  # Autoload
            if izmip in self.drivers:
                return False  # Don't autoload already loaded driver
            if dev_id != "*":  # Never autoload a generic driver by device ID
                for cls in self.available_drivers.get(dev_id, []):
                    if cls.get_autoload_flag():
                        driver_class = cls
                        break
            if driver_class is None:
                for cls in self.get_identity_drivers(izmip):
                    if cls.get_sysex_autoload():
                        driver_class = cls
                        break
            if driver_class is None:
                # Ask the device who it is: a driver for its identity loads when it answers
                self.request_identity(izmip)
                return False
        else:
            try:
                driver_class = self.driver_classes[driver_name]
            except:
                logging.warning(f"Requested driver {driver_name} is not available")

        if driver_class is None:
            return False

        # If a driver is already loaded for this device ...
        if izmip in self.drivers:
            # If it's the requested driver ...
            if type(self.drivers[izmip]) is driver_class:
                return False
            # Unload the current driver if requested a different one
            else:
                self.unload_driver(izmip)

        # Load requested driver
        izmop = zynautoconnect.dev_in_2_dev_out(izmip)
        try:
            # Create the driver instance
            driver = driver_class(self.state_manager, izmip, izmop)
            # Unroute from chains if driver want it
            if driver.unroute_from_chains:
                if isinstance(driver.unroute_from_chains, bool):
                    lib_zyncore.zmip_set_ui_midi_chans(izmip, 0xFFFF)
                elif isinstance(driver.unroute_from_chains, int):
                    lib_zyncore.zmip_set_ui_midi_chans(izmip, driver.unroute_from_chains)
            else:
                lib_zyncore.zmip_set_ui_midi_chans(izmip, 0)
            # Enable driver's MIDI handler before initializing, so we can manage SysEX responses while initializing!
            self.drivers[izmip] = driver
            # Initialize the driver
            driver.init()
            if uid in self.disabled_devices:
                self.disabled_devices.remove(uid)
            logging.info(f"Loaded ctrldev driver '{driver_class.get_driver_name()}' for '{dev_id}'.")
            return True
        except Exception as e:
            try:
                self.drivers.pop(izmip)
            except:
                pass
            logging.error(f"Can't load ctrldev driver '{driver_class.get_driver_name()}' for '{dev_id}' => {e}")
            logging.exception(traceback.format_exc())
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
            # Drop the driver instance from the list
            driver = self.drivers[izmip]
            self.drivers.pop(izmip)
            # Restore route to chains
            if driver.unroute_from_chains:
                lib_zyncore.zmip_set_ui_midi_chans(izmip, 0)
            # Terminate driver instance
            driver.end()
            logging.info(f"Unloaded ctrldev driver '{driver.get_driver_name()}' for '{dev_id}'.")
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
            unroute_from_chains = self.drivers[idev].unroute_from_chains
            if (isinstance(unroute_from_chains, bool) and unroute_from_chains) or unroute_from_chains == 0xFFFF:
                return False
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

    def need_wsled_state(self):
        """Return True if some driver needs the wsled state"""
        for dev in self.drivers.values():
            if dev.need_wsled_state:
                return True
        return False

    def sleep_on(self):
        """Enable sleep state"""

        for dev in list(self.drivers.values()):
            dev.sleep_on()

    def sleep_off(self):
        """Disable sleep state"""

        for dev in list(self.drivers.values()):
            dev.sleep_off()

    def midi_event(self, idev, ev):
        """Process MIDI event from zynmidirouter

        idev - device index
        ev - bytes with MIDI message data
        """

        # SysEx identity reply (asked for or not): note it, maybe autoload a driver for it
        if len(ev) >= 6 and ev[0] == 0xF0 and ev[1] == 0x7E and ev[3] == 0x06 and ev[4] == 0x02:
            try:
                self.on_identity(idev, ev)
            except Exception as e:
                logging.error(f"Can't handle identity reply from MIDI device {idev} => {e}")

        # Try device driver ...
        if idev in self.drivers:
            return self.drivers[idev].midi_event(ev)

        return False

# -----------------------------------------------------------------------------------------
