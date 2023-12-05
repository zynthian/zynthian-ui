#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian Control Device Manager Class
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
#                         Brian Walton <brian@riban.co.uk>
#
#******************************************************************************
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
#******************************************************************************

import os
import logging
import importlib
from pathlib import Path
from os.path import isfile, join
from glob import glob
import sys

# Zynthian specific modules
import zynautoconnect
from zyngine.ctrldev import *

#------------------------------------------------------------------------------
# Zynthian Control Device Manager Class
#------------------------------------------------------------------------------

class zynthian_ctrldev_manager():

	ctrldev_dpath = os.environ.get('ZYNTHIAN_UI_DIR', "/zynthian/zynthian-ui") + "/zyngui/ctrldev"

	# Function to initialise class
	def __init__(self):
		self.available_drivers = {} # Map of driver classes indexed by device type name
		self.drivers = {} # Map of device driver objects indexed by zmip

		self.update_available_drivers()
		#self.drivers_ids = self.get_drivers_ids() # Map of drivers indexed by device type name
		#self.zynpad_drivers_ids = self.get_zynpad_drivers_ids() # Map of pad drivers indexed by device type name
		#self.zynmixer_drivers_ids = self.get_zynmixer_drivers_ids() # Map of mixer drivers indexed by device type name
		#self.ctrldevs = [] # List of connected and configured devices (index in zynautoconnect.devices_in)
		self.mixer_devs = {} # Map of mixer device objects indexed by zmip index
		self.zynpad_devs = {} # Map of zynpad device objects indexed by zmip index


	def update_available_drivers(self):
		"""Get a map of available driver names
		
		returns : Map of driver names, indexed by device names
		"""

		self.available_drivers = {}
		for module_name in list(sys.modules):
			if module_name.startswith("zyngine.ctrldev.zynthian_ctrldev_"):
				class_name = module_name[16:]
				dev_class = getattr(sys.modules[module_name], class_name)
				for dev_id in dev_class.dev_ids:
					self.available_drivers[dev_id] = dev_class


	def load_driver(self, izmip):
		"""Loads a device driver
		
		izmip : Index of zmip to attach driver
		returns : True if new driver loaded
		"""

		device_type = zynautoconnect.get_midi_in_devid(izmip)
		if device_type not in self.available_drivers:
			return False
		if izmip in self.drivers:
			return False #TODO: Should check if driver differs
		try:
			self.drivers[izmip] = self.available_drivers[device_type]()
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
			self.drivers.pop(izmip)
			return True
		return False


	def get_drivers_ids(self):
		res = {}
		for driver in self.drivers.values():
			for dev_id in driver.dev_ids:
				res[dev_id] = driver
		return res


	def get_zynpad_drivers_ids(self):
		res = {}
		for driver in self.drivers.values():
			if driver.dev_zynpad:
				for dev_id in driver.dev_ids:
					res[dev_id] = driver
		return res


	def get_zynmixer_drivers_ids(self):
		res = {}
		for driver in self.drivers.values():
			if driver.dev_zynmixer:
				for dev_id in driver.dev_ids:
					res[dev_id] = driver
		return res


	def init_mixer_device(self, idev):
		if self.mixer_devs[idev]:
			if self.mixer_devs[idev] == zynautoconnect.devices_in[idev]:
				return
			self.end_device(idev)
		self.drivers[idev] = self.init_device(idev)
				

	def init_zynpad_device(self, idev):
		if self.zynpad_devs[idev]:
			if self.aynpad_devs[idev] == zynautoconnect.devices_in[idev]:
				return
			self.end_device(idev)
		self.zynpad_devs[idev] = self.init_device(idev)


	def end_device(self, idev):
		if idev in self.drivers:
			self.drivers[idev].release()
			self.drivers.remove(idev)


	def refresh_device(self, idev, force=False):
		for dev in self.drivers.values():
			dev.refresh(force)


	def end_all(self):
		for id in list(self.drivers):
			self.end_device(id)


	def refresh_all(self, force=False):
		for dev in self.drivers.values():
			dev.refresh(force)


	def sleep_on(self):
		for dev in self.drivers.values():
			dev.sleep_on()

	def sleep_off(self):
		for dev in self.drivers.values():
			dev.sleep_off()

	def set_device(self, idev, enable):
		if enable:
			self.init_device(idev)
		else:
			self.end_device(idev)

	def set_mixer_ctrl(self, idev, enable):
		if enable:
			self.init_mixer_device(idev)
		else:
			self.end_mixer_device(idev)

	def set_zynpad_ctrl(self, idev, enable):
		if enable:
			self.init_zynpad_device(idev)
		else:
			self.end_zynpad_device(idev)

	def is_mixer_ctrl(self, idev):
		return idev in self.mixer_devs

	def is_zynpad_ctrl(self, idev):
		return idev in self.zynpad_devs


	def zynpad_ctrldev_autoconfig(self):
		return #TODO: Implement zynpad_ctrldev_autoconfig
		zynpad = self.zyngui.screens['zynpad']
		if not zynpad.ctrldev_idev and zynpad.ctrldev_id:
			try:
				if zynpad.ctrldev_id in self.zynpad_drivers_ids.keys():
					driver = self.init_device_by_id(zynpad.ctrldev_id)
					if driver:
						zynpad.ctrldev = driver
						zynpad.ctrldev_idev = driver.idev
			except Exception as err:
				# logging.debug(err)
				pass
		if not zynpad.ctrldev_idev:
			try:
				for dev_id in self.zynpad_drivers_ids.keys():
					driver = self.init_device_by_id(dev_id)
					if driver:
						zynpad.ctrldev = driver
						zynpad.ctrldev_id = dev_id
						zynpad.ctrldev_idev = driver.idev
						break
			except Exception as err:
				# logging.debug(err)
				pass
		return zynpad.ctrldev_idev


	def zynmixer_ctrldev_autoconfig(self):
		return #TODO: implement zynmixer_ctrldev_autoconfig
		zynmixer = self.zyngui.screens['audio_mixer']
		if not zynmixer.ctrldev_idev and zynmixer.ctrldev_id:
			try:
				if zynmixer.ctrldev_id in self.zynmixer_drivers_ids.keys():
					driver = self.init_device_by_id(zynmixer.ctrldev_id)
					if driver:
						zynmixer.ctrldev = driver
						zynmixer.ctrldev_idev = driver.idev
			except Exception as err:
				# logging.debug(err)
				pass
		if not zynmixer.ctrldev_idev:
			try:
				for dev_id in self.zynmixer_drivers_ids.keys():
					driver = self.init_device_by_id(dev_id)
					if driver:
						zynmixer.ctrldev = driver
						zynmixer.ctrldev_id = dev_id
						zynmixer.ctrldev_idev = driver.idev
						break
			except Exception as err:
				# logging.debug(err)
				pass
		return zynmixer.ctrldev_idev


	def refresh_device_list(self):
		return #TODO: Implement in autoconnect
		# Remove disconnected devices
		logging.debug("Refreshing control device list...")
		for idev in range(1, 16):
			dev_id = zynautoconnect.devices_in[idev - 1]
			if not dev_id:
				# If zynmixer device got disconnected ...
				if self.zyngui.screens['audio_mixer'].ctrldev_idev == idev:
					#logging.debug("Releasing mixer control device...")
					self.zyngui.screens['audio_mixer'].ctrldev_idev = 0
				# If zynpad device got disconnected ...
				if self.zyngui.screens['zynpad'].ctrldev_idev == idev:
					#logging.debug("Releasing zynpad control device...")
					self.zyngui.screens['zynpad'].ctrldev_idev = 0
					self.zyngui.screens['zynpad'].ctrldev = None
				# Release device if it's active
				if self.ctrldevs[idev]:
					self.end_device(idev)

		# Autoconfig devices
		self.zynmixer_ctrldev_autoconfig()
		self.zynpad_ctrldev_autoconfig()


	def midi_event(self, ev):
		idev = ((ev & 0xFF000000) >> 24)

		# Try device driver ...
		if idev in self.drivers:
			return self.drivers[idev].midi_event(ev)

		# else, try zynpad
		"""TODO: Handle in state / not ui
		elif idev == self.zyngui.screens['zynpad'].ctrldev_idev:
			return self.zyngui.screens['zynpad'].midi_event(ev)
		"""

		return False
